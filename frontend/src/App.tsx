import React, { useState } from 'react'
import LiveSessionControls from './components/LiveSessionControls'
import TranscriptPanel from './components/TranscriptPanel'
import GraphCanvas from './components/GraphCanvas'
import SessionHistory from './components/SessionHistory'
import GraphReplay from './components/GraphReplay'
import { type YapSession } from './services/sessionStore'

type Page = 'live' | 'history' | 'replay'

export default function App() {
  const [page, setPage] = useState<Page>('live')
  const [replaySession, setReplaySession] = useState<YapSession | null>(null)

  const goHistory = () => setPage('history')
  const goReplay  = (s: YapSession) => { setReplaySession(s); setPage('replay') }
  const goLive    = () => setPage('live')

  if (page === 'history') return <SessionHistory onReplay={goReplay} onBack={goLive} />
  if (page === 'replay' && replaySession) return <GraphReplay session={replaySession} onBack={goHistory} />

  return (
    <div className="app-root" style={{ position: 'fixed', inset: 0, overflow: 'hidden' }}>
      <GraphCanvas />
      <div
        style={{
          position: 'absolute', left: '50%', bottom: 24,
          transform: 'translateX(-50%)',
          width: 'min(980px, calc(100vw - 32px))',
          pointerEvents: 'none', zIndex: 5,
        }}
      >
        <div
          style={{
            pointerEvents: 'auto',
            background: 'rgba(0,0,0,0.68)',
            border: '1px solid rgba(255,255,255,0.14)',
            boxShadow: '0 18px 60px rgba(0,0,0,0.45)',
            backdropFilter: 'blur(14px)',
            borderRadius: 20, padding: '16px 18px 14px',
          }}
        >
          <h1 style={{ margin: '0 0 10px', fontSize: 18, letterSpacing: '-0.03em' }}>YapMap</h1>
          <LiveSessionControls onShowHistory={goHistory} />
          <TranscriptPanel />
        </div>
      </div>
    </div>
  )
}
