export type RecorderHandle = {
  stop: () => void
}

export async function startMicRecording(onChunk: (chunk: Blob) => void): Promise<RecorderHandle> {
  // prefer AudioContext-based capture so we can emit raw PCM at 16kHz
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
    video: false,
  })

  const AudioCtx = (window.AudioContext || (window as any).webkitAudioContext)
  if (!AudioCtx) {
    stream.getTracks().forEach((t) => t.stop())
    throw new Error('Web Audio API not available')
  }

  const audioCtx = new (AudioCtx)()
  const source = audioCtx.createMediaStreamSource(stream)

  const bufferSize = 4096
  const processor = audioCtx.createScriptProcessor(bufferSize, source.channelCount || 1, 1)

  const targetRate = 16000
  const chunkDurationSec = 0.5
  const chunkSamples = Math.round(targetRate * chunkDurationSec)

  let accBuffers: Float32Array[] = []
  let accLen = 0

  processor.onaudioprocess = (evt: AudioProcessingEvent) => {
    const input = evt.inputBuffer
    const inRate = input.sampleRate || audioCtx.sampleRate
    const channels = input.numberOfChannels
    const len = input.length

    // mixdown to mono float32
    const mono = new Float32Array(len)
    for (let c = 0; c < channels; c++) {
      const ch = input.getChannelData(c)
      for (let i = 0; i < len; i++) mono[i] += ch[i] / channels
    }

    // resample to targetRate if necessary (linear interpolation)
    let resampled: Float32Array
    if (Math.round(inRate) === targetRate) {
      resampled = mono
    } else {
      const newLen = Math.round(mono.length * targetRate / inRate)
      resampled = new Float32Array(newLen)
      const ratio = inRate / targetRate
      for (let i = 0; i < newLen; i++) {
        const pos = i * ratio
        const i0 = Math.floor(pos)
        const i1 = Math.min(i0 + 1, mono.length - 1)
        const frac = pos - i0
        resampled[i] = mono[i0] + (mono[i1] - mono[i0]) * frac
      }
    }

    accBuffers.push(resampled)
    accLen += resampled.length

    // flush 0.5s chunks
    while (accLen >= chunkSamples) {
      const out = new Float32Array(chunkSamples)
      let filled = 0
      while (filled < chunkSamples) {
        const cur = accBuffers[0]
        const take = Math.min(cur.length, chunkSamples - filled)
        out.set(cur.subarray(0, take), filled)
        if (take === cur.length) accBuffers.shift()
        else accBuffers[0] = cur.subarray(take)
        filled += take
      }
      accLen -= chunkSamples

      // convert float32 -> 16-bit PCM little-endian
      const ab = new ArrayBuffer(out.length * 2)
      const dv = new DataView(ab)
      for (let i = 0; i < out.length; i++) {
        let s = Math.max(-1, Math.min(1, out[i]))
        dv.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
      }
      const blob = new Blob([ab], { type: 'audio/pcm' })
      try {
        onChunk(blob)
      } catch (e) {
        // swallow errors from consumer
      }
    }
  }

  // connect processor through a silent gain node to destination so it runs
  const zeroGain = audioCtx.createGain()
  zeroGain.gain.value = 0
  processor.connect(zeroGain)
  zeroGain.connect(audioCtx.destination)
  source.connect(processor)

  let stopped = false

  return {
    stop: () => {
      if (stopped) return
      stopped = true
      try {
        processor.disconnect()
        source.disconnect()
      } catch (e) {}
      try {
        zeroGain.disconnect()
      } catch (e) {}
      try {
        audioCtx.close().catch(() => {})
      } catch (e) {}
      stream.getTracks().forEach((t) => t.stop())
    },
  }
}
