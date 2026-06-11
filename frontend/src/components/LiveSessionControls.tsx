import React, { useRef, useState } from 'react'
import { createSession } from '../api/sessions'
import { startMicRecording, type RecorderHandle } from '../audio/micRecorder'
import { createLiveAudioSocket } from '../websocket/liveAudioSocket'
import { BatchTopicManager } from '../graph/BatchTopicManager'
import { injectedGraphPatch } from '../data/injectedGraphPatch'
import { sessionStore, type TranscriptSegment, type GraphSnapshot, type YapSession } from '../services/sessionStore'

interface Props {
  onShowHistory: () => void
}

export default function LiveSessionControls({ onShowHistory }: Props) {
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [recorder, setRecorder] = useState<RecorderHandle | null>(null)
  const socketRef = useRef<any | null>(null)
  const seqRef = useRef<number>(0)
  const batchRef = useRef<BatchTopicManager | null>(null)

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

  const start = async () => {
    setLoading(true)
    setStatus('Starting…')
    try {
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
          try { socket.sendAudioChunk(seqRef.current, chunk).catch(() => {}) } catch {}
        })
        setRecorder(r)
        try { const mgr = new BatchTopicManager({}); batchRef.current = mgr; mgr.start() } catch {}
        setStatus('Listening…')
      } catch (err: any) {
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
    try { batchRef.current?.stop() } catch {}
    batchRef.current = null
    const wasActive = sessionId !== null
    setSessionId(null)
    if (wasActive) stopRecording().catch(console.warn)
    else setStatus(null)
  }

  const isActive = !!sessionId

  return (
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
      {status && (
        <div style={{ color: 'rgba(255,255,255,0.6)', fontSize: 12, letterSpacing: '0.02em' }}>{status}</div>
      )}
    </div>
  )
}
