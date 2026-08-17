import React, { useCallback, useEffect, useRef, useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { forceManyBody, forceLink, forceCenter, forceCollide } from 'd3-force'
import { type YapSession, type GraphSnapshot } from '../services/sessionStore'

interface Props {
  session: YapSession
  onBack: () => void
}

function getSnapshotAt(snapshots: GraphSnapshot[], tsMs: number): GraphSnapshot | null {
  if (!snapshots.length) return null
  let best = snapshots[0]
  for (const s of snapshots) {
    if (s.ts <= tsMs) best = s
    else break
  }
  return best
}

function fmtTime(ms: number) {
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`
}

export default function GraphReplay({ session, onBack }: Props) {
  const fgRef = useRef<any>(null)
  const [currentTs, setCurrentTs] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(2)
  const [graphData, setGraphData] = useState<{ nodes: any[]; links: any[] }>({ nodes: [], links: [] })
  const [dims, setDims] = useState({ width: window.innerWidth, height: window.innerHeight })

  const colorMapRef = useRef<Map<string, string>>(new Map())
  const degreeMapRef = useRef<Map<string, number>>(new Map())
  const [hoverNode, setHoverNode] = useState<any>(null)
  const playRef = useRef(false)
  const rafRef = useRef(0)
  const lastRealRef = useRef(0)
  const speedRef = useRef(speed)
  useEffect(() => { speedRef.current = speed }, [speed])

  useEffect(() => {
    const onResize = () => setDims({ width: window.innerWidth, height: window.innerHeight })
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // Update graph data whenever scrubber moves
  useEffect(() => {
    const snap = getSnapshotAt(session.snapshots, currentTs)
    if (!snap) { setGraphData({ nodes: [], links: [] }); return }

    const deg = new Map<string, number>()
    for (const n of snap.nodes) deg.set(n.id, 0)
    for (const l of snap.links) {
      deg.set(l.source, (deg.get(l.source) || 0) + (l.value || 1))
      deg.set(l.target, (deg.get(l.target) || 0) + (l.value || 1))
    }
    degreeMapRef.current = deg

    // Timestamp-based hue
    let minT = Infinity, maxT = -Infinity
    for (const n of snap.nodes) {
      const ts = n.timestamps || []
      if (ts.length) { minT = Math.min(minT, ...ts); maxT = Math.max(maxT, ...ts) }
    }
    const colorMap = new Map<string, string>()
    for (const n of snap.nodes) {
      const ts = n.timestamps || []
      if (ts.length && isFinite(minT) && maxT > minT) {
        const avg = ts.reduce((a, b) => a + b, 0) / ts.length
        const hue = Math.round(260 - ((avg - minT) / (maxT - minT)) * 220)
        colorMap.set(n.id, `hsl(${hue},72%,55%)`)
      } else {
        colorMap.set(n.id, 'hsl(200,60%,55%)')
      }
    }
    colorMapRef.current = colorMap
    setGraphData({ nodes: snap.nodes.map(n => ({ ...n })), links: snap.links.map(l => ({ ...l })) })
  }, [currentTs, session])

  // D3 forces
  useEffect(() => {
    if (!fgRef.current) return
    try {
      fgRef.current.d3Force('link', forceLink().id((d: any) => d.id)
        .distance((d: any) => Math.max(30, 100 / Math.sqrt(d.value || 1))).strength(0.8))
      fgRef.current.d3Force('charge', forceManyBody().strength(-35))
      fgRef.current.d3Force('collision', forceCollide()
        .radius((d: any) => 8 + Math.sqrt(degreeMapRef.current.get(d.id) || 1) * 4).strength(0.8))
      fgRef.current.d3Force('center', forceCenter(0, 0))
    } catch {}
  }, [graphData])

  // Play / pause animation
  const togglePlay = useCallback(() => {
    const nowPlaying = !playRef.current
    playRef.current = nowPlaying
    setPlaying(nowPlaying)
    if (nowPlaying) {
      lastRealRef.current = performance.now()
      const tick = () => {
        if (!playRef.current) return
        const now = performance.now()
        const elapsed = now - lastRealRef.current
        lastRealRef.current = now
        setCurrentTs(prev => {
          const next = prev + elapsed * speedRef.current
          if (next >= session.duration) {
            playRef.current = false
            setPlaying(false)
            return session.duration
          }
          return next
        })
        rafRef.current = requestAnimationFrame(tick)
      }
      rafRef.current = requestAnimationFrame(tick)
    } else {
      cancelAnimationFrame(rafRef.current)
    }
  }, [session.duration])

  useEffect(() => () => { playRef.current = false; cancelAnimationFrame(rafRef.current) }, [])

  const drawNode = useCallback((node: any, ctx: CanvasRenderingContext2D, gs: number) => {
    const degree = Math.max(1, degreeMapRef.current.get(node.id) || 1)
    const base = 3 + Math.sqrt(degree) * 3
    const size = base / Math.max(0.5, gs)
    const color = colorMapRef.current.get(node.id) || 'hsl(200,60%,60%)'
    const isHovered = hoverNode && hoverNode.id === node.id
    ctx.save()
    ctx.shadowBlur = 8; ctx.shadowColor = color; ctx.fillStyle = color
    ctx.beginPath(); ctx.arc(node.x || 0, node.y || 0, size, 0, Math.PI * 2); ctx.fill()
    ctx.shadowBlur = 0
    if (isHovered) {
      ctx.lineWidth = 2.5
      ctx.strokeStyle = 'rgba(255,255,255,0.85)'
      ctx.beginPath(); ctx.arc(node.x || 0, node.y || 0, size, 0, Math.PI * 2); ctx.stroke()
    }

    // Labels stay nearly transparent until hovered, mirroring the live graph view.
    const isImportantHub = degree >= 6
    const labelAlpha = isHovered ? 1.0 : (isImportantHub ? 0.16 : 0.05)
    const fs = Math.max(11, (base * 1.6) / Math.max(0.6, gs)) * (isHovered ? 1.15 : 1)
    ctx.font = `${isHovered ? 'bold ' : ''}${fs}px Inter,Arial`
    ctx.textAlign = 'center'; ctx.textBaseline = 'bottom'
    ctx.globalAlpha = labelAlpha
    if (isHovered) {
      const label = node.label || node.id
      const w = ctx.measureText(label).width + 10
      const h = fs + 6
      ctx.fillStyle = 'rgba(0,0,0,0.65)'
      ctx.fillRect((node.x || 0) - w / 2, (node.y || 0) - size - 6 - h, w, h)
    }
    ctx.fillStyle = '#fff'
    ctx.fillText(node.label || node.id, node.x || 0, (node.y || 0) - size - 4)
    ctx.globalAlpha = 1.0
    ctx.restore()
  }, [hoverNode])

  const drawLink = useCallback((link: any, ctx: CanvasRenderingContext2D, gs: number) => {
    const src = link.source, tgt = link.target
    if (!src || !tgt || src.x == null || tgt.x == null) return
    const sc = colorMapRef.current.get(src.id) || 'hsl(200,60%,60%)'
    const tc = colorMapRef.current.get(tgt.id) || sc
    const grad = ctx.createLinearGradient(src.x, src.y, tgt.x, tgt.y)
    grad.addColorStop(0, sc); grad.addColorStop(1, tc)
    ctx.save()
    ctx.beginPath(); ctx.strokeStyle = grad; ctx.globalAlpha = 0.45
    ctx.lineWidth = Math.max(1, (0.4 + Math.log((link.value || 1) + 1) * 0.7) / gs)
    ctx.moveTo(src.x, src.y); ctx.lineTo(tgt.x, tgt.y); ctx.stroke()
    ctx.restore()
  }, [])

  const visTranscript = session.transcript.filter(t => t.ts <= currentTs).slice(-4)

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#000', overflow: 'hidden', zIndex: 10 }}>
      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        backgroundColor="#000"
        nodeCanvasObject={drawNode}
        linkCanvasObject={drawLink}
        linkCanvasObjectMode={() => 'replace'}
        linkWidth={() => 0}
        linkColor={() => 'rgba(0,0,0,0)'}
        onNodeHover={(node) => setHoverNode(node)}
        autoPauseRedraw={false}
        d3VelocityDecay={0.3}
        width={dims.width}
        height={dims.height}
      />

      {/* Top bar */}
      <div style={{
        position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)',
        display: 'flex', alignItems: 'center', gap: 12,
        background: 'rgba(0,0,0,0.75)', border: '1px solid rgba(255,255,255,0.14)',
        backdropFilter: 'blur(12px)', borderRadius: 12, padding: '10px 16px',
        color: '#fff', fontSize: 14, zIndex: 20, whiteSpace: 'nowrap',
      }}>
        <button
          onClick={onBack}
          style={{
            background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.18)',
            color: '#fff', borderRadius: 7, padding: '5px 12px', cursor: 'pointer', fontSize: 13,
          }}
        >← Sessions</button>
        <span style={{ fontWeight: 600, maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {session.title}
        </span>
        <span style={{ color: 'rgba(255,255,255,0.45)', fontSize: 12 }}>
          {session.snapshots[session.snapshots.length - 1]?.nodes?.length ?? 0} topics
        </span>
      </div>

      {/* Bottom controls */}
      <div style={{
        position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
        width: 'min(720px, calc(100vw - 32px))',
        background: 'rgba(0,0,0,0.82)', border: '1px solid rgba(255,255,255,0.13)',
        backdropFilter: 'blur(14px)', borderRadius: 16, padding: '14px 18px',
        color: '#fff', zIndex: 20,
      }}>
        {/* Scrubber row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
          <button
            onClick={togglePlay}
            style={{
              background: playing ? 'rgba(255,255,255,0.15)' : 'rgba(102,153,255,0.8)',
              border: 'none', color: '#fff', borderRadius: 999,
              width: 34, height: 34, cursor: 'pointer', fontSize: 15,
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}
          >{playing ? '⏸' : '▶'}</button>

          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.55)', minWidth: 38, textAlign: 'right' }}>
            {fmtTime(currentTs)}
          </span>
          <input
            type="range" min={0} max={session.duration} step={200} value={currentTs}
            onChange={e => {
              const v = Number(e.target.value)
              setCurrentTs(v)
              if (playRef.current) { playRef.current = false; setPlaying(false) }
            }}
            style={{ flex: 1, accentColor: '#6699ff', cursor: 'pointer' }}
          />
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.55)', minWidth: 38 }}>
            {fmtTime(session.duration)}
          </span>
          <select
            value={speed}
            onChange={e => setSpeed(Number(e.target.value))}
            style={{
              background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.18)',
              color: '#fff', borderRadius: 7, padding: '3px 6px', fontSize: 12, cursor: 'pointer',
            }}
          >
            <option value={1}>1×</option>
            <option value={2}>2×</option>
            <option value={5}>5×</option>
            <option value={10}>10×</option>
          </select>
        </div>

        {/* Transcript */}
        {visTranscript.length > 0 && (
          <div style={{
            fontSize: 12, color: 'rgba(255,255,255,0.6)', lineHeight: 1.5,
            maxHeight: 56, overflow: 'hidden',
          }}>
            {visTranscript.map((t, i) => <span key={i}>{t.text} </span>)}
          </div>
        )}
      </div>
    </div>
  )
}
