export type ServerLiveEvent = any

function blobToBase64(blob: Blob): Promise<string> {
  // If the blob is a compressed container (webm/ogg/opus), decode in the
  // browser to raw PCM, resample to 16kHz, then base64-encode the PCM bytes.
  return new Promise(async (resolve, reject) => {
    try {
      const mt = (blob.type || '').toLowerCase()
      const shouldDecode = mt.includes('webm') || mt.includes('ogg') || mt.includes('opus')
      if (!shouldDecode) {
        const reader = new FileReader()
        reader.onload = () => {
          const result = reader.result as string
          const comma = result.indexOf(',')
          resolve(result.slice(comma + 1))
        }
        reader.onerror = reject
        reader.readAsDataURL(blob)
        return
      }

      const targetRate = 16000
      const arrayBuffer = await blob.arrayBuffer()
      const AudioCtx = (window.AudioContext || (window as any).webkitAudioContext)
      const OfflineAudioCtx = (window as any).OfflineAudioContext || (window as any).webkitOfflineAudioContext
      const decodeCtx = new (AudioCtx)()
      const audioBuffer = await decodeCtx.decodeAudioData(arrayBuffer.slice(0))

      let renderedBuffer = audioBuffer
      if (Math.round(audioBuffer.sampleRate) !== targetRate) {
        const length = Math.ceil(audioBuffer.duration * targetRate)
        const offline = new (OfflineAudioCtx)(1, length, targetRate)
        const src = offline.createBufferSource()
        src.buffer = audioBuffer
        src.connect(offline.destination)
        src.start(0)
        renderedBuffer = await offline.startRendering()
      } else if (audioBuffer.numberOfChannels > 1) {
        // mixdown to mono
        const mono = decodeCtx.createBuffer(1, audioBuffer.length, audioBuffer.sampleRate)
        const out = mono.getChannelData(0)
        for (let c = 0; c < audioBuffer.numberOfChannels; c++) {
          const ch = audioBuffer.getChannelData(c)
          for (let i = 0; i < out.length; i++) out[i] += ch[i] / audioBuffer.numberOfChannels
        }
        renderedBuffer = mono
      }

      // convert Float32 to 16-bit PCM little endian
      const float32 = renderedBuffer.getChannelData(0)
      const buffer = new ArrayBuffer(float32.length * 2)
      const view = new DataView(buffer)
      let offset = 0
      for (let i = 0; i < float32.length; i++, offset += 2) {
        let s = Math.max(-1, Math.min(1, float32[i]))
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
      }

      // base64 encode in chunks to avoid stack limits
      const uint8 = new Uint8Array(buffer)
      let binary = ''
      const chunkSize = 0x8000
      for (let i = 0; i < uint8.length; i += chunkSize) {
        const sub = uint8.subarray(i, i + chunkSize)
        binary += String.fromCharCode.apply(null, Array.prototype.slice.call(sub))
      }
      try { decodeCtx.close && decodeCtx.close() } catch (e) {}
      resolve(btoa(binary))
    } catch (err) {
      reject(err)
    }
  })
}

export function createLiveAudioSocket(sessionId: string, onMessage: (ev: ServerLiveEvent) => void) {
  const apiBase = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8000'
  const wsBase = apiBase.replace(/^http/, 'ws')
  const wsUrl = `${wsBase}/ws/live/${sessionId}`

  const ws = new WebSocket(wsUrl)

  // promise that resolves when socket opens (or rejects on timeout)
  let openResolve: () => void
  let openReject: (err?: any) => void
  const openPromise: Promise<void> = new Promise((resolve, reject) => {
    openResolve = resolve
    openReject = reject
  })
  const openTimeout = setTimeout(() => {
    try {
      openReject && openReject(new Error('WebSocket open timeout'))
    } catch (e) {}
  }, 5000)

  ws.addEventListener('open', () => {
    clearTimeout(openTimeout)
    openResolve && openResolve()
    onMessage({ type: 'socket.open' })
  })

  ws.addEventListener('message', (ev) => {
    try {
      const data = JSON.parse(ev.data)
      onMessage(data)
    } catch (e) {
      onMessage({ type: 'raw', data: ev.data })
    }
  })

  ws.addEventListener('close', () => onMessage({ type: 'socket.closed' }))
  ws.addEventListener('error', (err) => onMessage({ type: 'socket.error', error: err }))

  async function ensureOpen(): Promise<void> {
    if (ws.readyState === WebSocket.OPEN) return
    if (ws.readyState === WebSocket.CLOSED) throw new Error('WebSocket already closed')
    return openPromise
  }

  async function sendAudioChunk(sequence: number, blob: Blob) {
    await ensureOpen()
    // convert to PCM16@16k and send as raw PCM to avoid server decode errors
    const base64 = await blobToBase64(blob)
    const msg = {
      type: 'audio.chunk',
      payload: {
        sequence,
        mimeType: 'audio/pcm',
        sampleRate: 16000,
        dataBase64: base64,
      },
    }
    ws.send(JSON.stringify(msg))
  }

  async function sendSessionStart() {
    await ensureOpen()
    ws.send(JSON.stringify({ type: 'session.start', payload: { mimeType: 'audio/pcm' } }))
  }

  async function sendSessionStop() {
    try {
      await ensureOpen()
      ws.send(JSON.stringify({ type: 'session.stop', payload: {} }))
    } catch (e) {
      // ignore
    }
  }

  return { ws, sendAudioChunk, sendSessionStart, sendSessionStop, close: () => ws.close() }
}
