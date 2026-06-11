import React, { useEffect, useState } from 'react'
import { sessionStore, type YapSession } from '../services/sessionStore'

interface Props {
  onReplay: (session: YapSession) => void
  onBack: () => void
}

function fmtDuration(ms: number) {
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`
}

export default function SessionHistory({ onReplay, onBack }: Props) {
  const [sessions, setSessions] = useState<YapSession[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    sessionStore.list()
      .then(s => { setSessions(s); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    await sessionStore.delete(id).catch(() => {})
    setSessions(prev => prev.filter(s => s.id !== id))
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: '#06060e',
      overflowY: 'auto', padding: '28px 20px',
      color: '#fff', fontFamily: 'Inter, system-ui, Arial, sans-serif',
      zIndex: 20,
    }}>
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 28 }}>
          <button
            onClick={onBack}
            style={{
              background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.14)',
              color: '#fff', borderRadius: 9, padding: '8px 16px', cursor: 'pointer', fontSize: 14,
            }}
          >← Back</button>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: '-0.03em' }}>
            Saved Sessions
          </h1>
        </div>

        {loading && (
          <p style={{ color: 'rgba(255,255,255,0.4)', textAlign: 'center', marginTop: 40 }}>Loading…</p>
        )}

        {!loading && sessions.length === 0 && (
          <div style={{ textAlign: 'center', marginTop: 80, color: 'rgba(255,255,255,0.4)' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>🗂</div>
            <p style={{ fontSize: 16 }}>No saved sessions yet.</p>
            <p style={{ fontSize: 13 }}>Start a session and it will be saved here when you stop.</p>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {sessions.map(s => {
            const lastSnap = s.snapshots[s.snapshots.length - 1]
            const nodeCount = lastSnap?.nodes?.length ?? 0
            const topTopics = lastSnap?.nodes?.slice(0, 6).map(n => n.label).join(', ') ||
              s.transcript.slice(0, 2).map(t => t.text).join(' ').slice(0, 100)
            return (
              <div
                key={s.id}
                onClick={() => onReplay(s)}
                style={{
                  background: 'rgba(255,255,255,0.045)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 14, padding: '16px 18px',
                  cursor: 'pointer', transition: 'background 0.15s',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.045)')}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', marginBottom: 5 }}>
                    <span style={{ fontWeight: 600, fontSize: 15 }}>{s.title}</span>
                    <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12 }}>
                      {fmtDuration(s.duration)}
                    </span>
                    {nodeCount > 0 && (
                      <span style={{ color: 'rgba(102,153,255,0.8)', fontSize: 12 }}>
                        {nodeCount} topics
                      </span>
                    )}
                  </div>
                  {topTopics && (
                    <div style={{
                      color: 'rgba(255,255,255,0.45)', fontSize: 12,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {topTopics}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 8, marginLeft: 14, alignItems: 'center', flexShrink: 0 }}>
                  <button
                    onClick={e => handleDelete(s.id, e)}
                    style={{
                      background: 'rgba(255,50,50,0.12)', border: '1px solid rgba(255,50,50,0.25)',
                      color: '#ff6060', borderRadius: 7, padding: '5px 10px',
                      cursor: 'pointer', fontSize: 12,
                    }}
                  >Delete</button>
                  <span style={{ color: 'rgba(255,255,255,0.35)', fontSize: 22 }}>›</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
