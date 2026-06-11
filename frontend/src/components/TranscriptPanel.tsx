import React, { useEffect, useState } from 'react'

type Segment = {
  id: string
  text: string
  createdAt?: string
}

export default function TranscriptPanel() {
  const [partial, setPartial] = useState<string | null>(null)

  useEffect(() => {
    const handler = (ev: any) => {
      const msg = ev.detail
      if (!msg || !msg.type) return

      if (msg.type === 'transcript.partial') {
        setPartial(msg.payload?.text ?? null)
      } else if (msg.type === 'transcript.final') {
        // clear partial when final arrives
        setPartial(null)
        // broadcast the finalized segment for graph building
        try {
          window.dispatchEvent(new CustomEvent('yap:transcript:final', { detail: msg.payload }))
        } catch (e) {
          // ignore
        }
      }
    }

    window.addEventListener('yap:ws:event', handler)
    return () => window.removeEventListener('yap:ws:event', handler)
  }, [])

  return (
    <div style={{ marginTop: 12 }}>
      <div className="live-caption-bar">
        <div className="live-dot" />
        <div className="live-text">{partial ?? 'waiting…'}</div>
      </div>
    </div>
  )
}
