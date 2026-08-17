import React, { useRef, useState } from 'react'
import { createSession } from '../api/sessions'
import { startMicRecording, type RecorderHandle } from '../audio/micRecorder'
import { createLiveAudioSocket } from '../websocket/liveAudioSocket'
import { injectedGraphPatch } from '../data/injectedGraphPatch'
import { sessionStore, type TranscriptSegment, type GraphSnapshot, type YapSession } from '../services/sessionStore'
import AudioUploadPanel from './AudioUploadPanel'

interface Props {
  onShowHistory: () => void
}

export default function LiveSessionControls({ onShowHistory }: Props) {
  const [mode, setMode] = useState<'mic' | 'upload'>('upload') // default to upload
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [recorder, setRecorder] = useState<RecorderHandle | null>(null)
  const socketRef = useRef<any | null>(null)
  const seqRef = useRef<number>(0)

  // Session recording
  const sessionStartRef = useRef<number>(0)
  const transcriptBufferRef = useRef<TranscriptSegment[]>([])
  const snapshotBufferRef = useRef<GraphSnapshot[]>([])
  const lastSnapshotTsRef = useRef<number>(0)
  const transcriptListenerRef = useRef<((ev: any) => void) | null>(null)
  const graphListenerRef = useRef<((ev: any) => void) | null>(null)

  const startRecording = () => {
    const startMs = Date.now()
    sessionStartRef.current = startMs
    transcriptBufferRef.current = []
    snapshotBufferRef.current = []
    lastSnapshotTsRef.current = 0

    const tListener = (ev: any) => {
      const msg = ev.detail
      if (!msg || msg.type !== 'transcript.final') return
      const seg = msg.payload
      if (!seg?.text) return
      transcriptBufferRef.current.push({ text: seg.text, ts: Date.now() - startMs })
    }
    transcriptListenerRef.current = tListener
    window.addEventListener('yap:ws:event', tListener)

    const gListener = (ev: any) => {
      const { nodes, links } = ev.detail || {}
      if (!nodes) return
      const relTs = Date.now() - startMs
      if (relTs - lastSnapshotTsRef.current < 5000) return // throttle to 1 per 5s
      lastSnapshotTsRef.current = relTs
      snapshotBufferRef.current.push({ ts: relTs, nodes: nodes.slice(), links: links.slice() })
    }
    graphListenerRef.current = gListener
    window.addEventListener('yap:graph:update', gListener)
  }

  const stopRecording = async () => {
    if (transcriptListenerRef.current) {
      window.removeEventListener('yap:ws:event', transcriptListenerRef.current)
      transcriptListenerRef.current = null
    }
    if (graphListenerRef.current) {
      window.removeEventListener('yap:graph:update', graphListenerRef.current)
      graphListenerRef.current = null
    }

    const duration = Date.now() - sessionStartRef.current
    const transcript = transcriptBufferRef.current.slice()
    const snapshots = snapshotBufferRef.current.slice()
    if (transcript.length === 0 && snapshots.length === 0) return

    const title = new Date(sessionStartRef.current).toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
    })
    const session: YapSession = {
      id: crypto.randomUUID(),
      title,
      createdAt: sessionStartRef.current,
      duration,
      transcript,
      snapshots,
    }
    try {
      await sessionStore.save(session)
      setStatus('Session saved ✓')
      setTimeout(() => setStatus(null), 3000)
    } catch (e) {
      console.warn('Failed to save session', e)
    }
  }

  const checkModelStatus = async () => {
    console.log('[Session] Checking model status...')
    try {
      const res = await fetch('http://localhost:8000/api/nlp/status')
      if (!res.ok) throw new Error('Status endpoint failed')
      const data = await res.json()
      return data
    } catch (e: any) {
      console.error('[Session] Failed to check model status:', e?.message)
      throw e
    }
  }

  const waitForModelsReady = async (maxWaitMs: number = 120000) => {
    const startTime = Date.now()
    setStatus('Checking if models are ready...')
    
    while (Date.now() - startTime < maxWaitMs) {
      try {
        const status = await checkModelStatus()
        console.log('[Session] Model status:', status)
        
        if (status.is_ready) {
          console.log('[Session] Models are ready!')
          setStatus('Models ready! ✓')
          setTimeout(() => setStatus(null), 1000)
          return true
        }
        
        if (status.status === 'loading') {
          setStatus('Loading models (this may take 30-60 seconds)...')
        } else if (status.status === 'failed') {
          throw new Error(`Model loading failed: ${status.error}`)
        }
        
        // Wait 2 seconds before checking again
        await new Promise(r => setTimeout(r, 2000))
      } catch (e: any) {
        console.error('[Session] Error checking model status:', e?.message)
        // Continue waiting even if there's an error
        await new Promise(r => setTimeout(r, 2000))
      }
    }
    
    throw new Error('Model loading timed out after 2 minutes')
  }

  const start = async () => {
    setLoading(true)
    setStatus('Starting…')
    try {
      // Wait for models to be ready
      try {
        await waitForModelsReady()
      } catch (e: any) {
        alert('Models failed to load: ' + (e?.message || e))
        setLoading(false)
        setStatus(null)
        return
      }

      const data = await createSession({ title: 'Live session', mode: 'live_mic' })
      setSessionId(data.id)
      startRecording()

      let socket
      try {
        socket = createLiveAudioSocket(data.id, (msg) => {
          try { window.dispatchEvent(new CustomEvent('yap:ws:event', { detail: msg })) } catch {}
        })
        socketRef.current = socket
        await socket.sendSessionStart()
      } catch (e: any) {
        alert('Failed to open websocket: ' + (e?.message || e))
        setLoading(false)
        return
      }

      try {
        const r = await startMicRecording((chunk) => {
          seqRef.current += 1
          const seq = seqRef.current
          console.log('[Session] Received audio chunk #' + seq + ' from mic, enqueueing for send')
          try { 
            socket.sendAudioChunk(seq, chunk).then(() => {
              console.log('[Session] Audio chunk #' + seq + ' sent successfully')
            }).catch((e: any) => {
              console.error('[Session] Failed to send audio chunk #' + seq + ':', e?.message || e)
            })
          } catch (e: any) {
            console.error('[Session] Error in audio chunk handler:', e?.message || e)
          }
        })
        setRecorder(r)
        console.log('[Session] Microphone recording started')
        // NOTE: BatchTopicManager (naive client-side n-gram topic extraction) is
        // intentionally NOT started. It used to inject its own unclustered
        // "graph.patch" events in parallel with the backend's semantic
        // embedding-based clustering, which caused the graph to fragment into
        // many disconnected near-duplicate nodes. The backend WS pipeline
        // (TopicManager + concept_extractor + graph_store fuzzy merge) is now
        // the single source of truth for graph nodes/edges.
        setStatus('Listening…')
      } catch (err: any) {
        console.error('[Session] Microphone error:', err?.message || err)
        alert('Microphone access failed: ' + (err?.message || err))
        try { socketRef.current?.sendSessionStop(); socketRef.current?.close() } catch {}
        socketRef.current = null
        setSessionId(null)
        setStatus(null)
        setLoading(false)
        return
      }
    } catch (err: any) {
      console.warn('Backend unavailable, using local demo graph:', err?.message)
      try {
        window.dispatchEvent(new CustomEvent('yap:ws:event', { detail: { type: 'graph.patch', payload: injectedGraphPatch } }))
        setSessionId('local-demo')
        setStatus('Demo mode — no backend')
        startRecording()
      } catch {}
    } finally {
      setLoading(false)
    }
  }

  const stop = () => {
    try { recorder?.stop() } catch {}
    setRecorder(null)
    try { socketRef.current?.sendSessionStop(); socketRef.current?.close() } catch {}
    socketRef.current = null
    const wasActive = sessionId !== null
    setSessionId(null)
    if (wasActive) stopRecording().catch(console.warn)
    else setStatus(null)
  }

  const handleUploadTranscript = async (transcript: string, concepts: any) => {
    // Process uploaded audio transcript
    setStatus('Processing transcript…')
    try {
      const data = await createSession({ title: 'Uploaded audio session', mode: 'upload_audio' })
      setSessionId(data.id)
      startRecording()

      // Emit the transcript as a final event for graph processing
      const segment = {
        id: crypto.randomUUID(),
        sessionId: data.id,
        speaker: 'Speaker',
        text: transcript,
        startTime: Date.now() / 1000,
        endTime: (Date.now() / 1000) + 1,
        index: 0,
        isFinal: true,
        createdAt: new Date().toISOString(),
      }

      // Dispatch event for graph processing
      try { window.dispatchEvent(new CustomEvent('yap:ws:event', { detail: { type: 'transcript.final', payload: segment } })) } catch {}

      // Simulate graph patch from concepts
      if (concepts) {
        const graphPatch = {
          sessionId: data.id,
          nodesAdded: concepts?.nodes || [],
          edgesAdded: concepts?.edges || [],
          nodesRemoved: [],
          edgesRemoved: [],
        }
        try { window.dispatchEvent(new CustomEvent('yap:ws:event', { detail: { type: 'graph.patch', payload: graphPatch } })) } catch {}
      }

      setStatus('Transcript processed ✓')
      setTimeout(() => {
        // Auto-stop after a moment
        setSessionId(null)
        stopRecording().catch(() => {})
        setStatus(null)
      }, 2000)
    } catch (err: any) {
      setStatus(`Error: ${err?.message || 'Failed to process'}`)
    }
  }

  const isActive = !!sessionId

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
      {/* Mode selector tabs */}
      <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
        <button
          onClick={() => setMode('upload')}
          style={{
            padding: '8px 14px',
            borderRadius: 8,
            border: mode === 'upload' ? '1px solid rgba(170,200,255,0.6)' : '1px solid rgba(255,255,255,0.14)',
            background: mode === 'upload' ? 'rgba(170,200,255,0.15)' : 'rgba(255,255,255,0.05)',
            color: mode === 'upload' ? 'rgba(170,200,255,0.9)' : 'rgba(255,255,255,0.5)',
            fontWeight: 600,
            fontSize: 12,
            cursor: 'pointer',
            transition: 'all 0.2s',
          }}
        >
          📁 Upload Audio
        </button>
        <button
          onClick={() => setMode('mic')}
          style={{
            padding: '8px 14px',
            borderRadius: 8,
            border: mode === 'mic' ? '1px solid rgba(102,200,255,0.6)' : '1px solid rgba(255,255,255,0.14)',
            background: mode === 'mic' ? 'rgba(102,200,255,0.15)' : 'rgba(255,255,255,0.05)',
            color: mode === 'mic' ? 'rgba(102,200,255,0.9)' : 'rgba(255,255,255,0.5)',
            fontWeight: 600,
            fontSize: 12,
            cursor: 'pointer',
            transition: 'all 0.2s',
          }}
        >
          🎤 Live Microphone
        </button>
      </div>

      {/* Mode-specific content */}
      {mode === 'upload' ? (
        <AudioUploadPanel
          onTranscript={handleUploadTranscript}
          onError={(msg) => setStatus(`Error: ${msg}`)}
          onComplete={() => setStatus(null)}
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {!isActive ? (
              <button
                onClick={start}
                disabled={loading}
                style={{
                  minWidth: 150, padding: '11px 18px', borderRadius: 999,
                  border: '1px solid rgba(255,255,255,0.16)',
                  background: loading ? 'rgba(255,255,255,0.12)' : 'linear-gradient(135deg,rgba(102,153,255,0.95),rgba(126,231,135,0.88))',
                  color: '#fff', fontWeight: 700, fontSize: 14, cursor: loading ? 'default' : 'pointer',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
                }}
              >
                {loading ? 'Starting…' : '● Start Mapping'}
              </button>
            ) : (
              <button
                onClick={stop}
                style={{
                  minWidth: 150, padding: '11px 18px', borderRadius: 999,
                  border: '1px solid rgba(255,80,80,0.35)', background: 'rgba(255,60,60,0.15)',
                  color: '#ff7070', fontWeight: 700, fontSize: 14, cursor: 'pointer',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
                }}
              >
                ■ Stop Mapping
              </button>
            )}
            <button
              onClick={onShowHistory}
              style={{
                padding: '11px 14px', borderRadius: 999,
                border: '1px solid rgba(255,255,255,0.14)', background: 'rgba(255,255,255,0.07)',
                color: 'rgba(255,255,255,0.75)', fontWeight: 600, fontSize: 13, cursor: 'pointer',
              }}
            >
              Sessions
            </button>
          </div>
        </div>
      )}

      {status && (
        <div style={{ color: 'rgba(255,255,255,0.6)', fontSize: 12, letterSpacing: '0.02em' }}>{status}</div>
      )}
    </div>
  )
}
