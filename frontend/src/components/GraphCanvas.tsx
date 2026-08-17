import React, { useEffect, useRef, useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { extractTopicsFromText, extractTopicsFromSegments, slugify } from '../graph/topicExtractor'
import { forceManyBody, forceLink, forceCenter, forceCollide } from 'd3-force'

type TopicNode = { id: string; label: string; __added?: number; timestamps?: number[]; x?: number; y?: number }
type TopicLink = { source: string; target: string; id?: string; value?: number }

function hueFromColor(color: string) {
  const match = /hsl\(([-\d.]+),\s*([\d.]+)%?,\s*([\d.]+)%?\)/i.exec(color)
  return match ? Number(match[1]) : 200
}

function nodeColorToLinkColor(sourceColor: string, targetColor: string) {
  const sourceHue = hueFromColor(sourceColor)
  const targetHue = hueFromColor(targetColor)
  const hue = Math.round((sourceHue + targetHue) / 2)
  return `hsla(${hue}, 72%, 62%, 0.34)`
}

export default function GraphCanvas() {
  const fgRef = useRef<any>(null)
  const [dimensions, setDimensions] = useState({ width: typeof window !== 'undefined' ? window.innerWidth : 800, height: typeof window !== 'undefined' ? window.innerHeight : 600 })
  const nodesMap = useRef<Map<string, TopicNode>>(new Map())
  const linksMap = useRef<Map<string, { source: string; target: string; value: number }>>(new Map())
  const [graphData, setGraphData] = useState<{ nodes: TopicNode[]; links: TopicLink[] }>({ nodes: [], links: [] })
  const colorMapRef = useRef<Map<string, string>>(new Map())
  const neighborMapRef = useRef<Map<string, Set<string>>>(new Map())
  const degreeMapRef = useRef<Map<string, number>>(new Map())
  // Persists backend UUID -> frontend label-based id across multiple graph.patch messages
  const backendIdMapRef = useRef<Map<string, string>>(new Map())
  const [hoverNode, setHoverNode] = useState<any>(null)
  const [selectedNode, setSelectedNode] = useState<any>(null)
  const batchingRef = useRef<boolean>(false)

  useEffect(() => {
    const onBatch = (ev: any) => {
      batchingRef.current = !!(ev?.detail?.active)
    }
    window.addEventListener('yap:graph:batching', onBatch)
    return () => window.removeEventListener('yap:graph:batching', onBatch)
  }, [])

  useEffect(() => {
    const onResize = () => setDimensions({ width: window.innerWidth, height: window.innerHeight })
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // expose graph data for debugging/tests and emit update event for session recording
  useEffect(() => {
    try {
      ;(window as any).__graphData__ = graphData
      window.dispatchEvent(new CustomEvent('yap:graph:update', {
        detail: {
          nodes: graphData.nodes.map(n => ({ id: n.id, label: n.label, timestamps: n.timestamps })),
          links: graphData.links.map(l => ({
            source: typeof l.source === 'object' ? (l.source as any).id : l.source,
            target: typeof l.target === 'object' ? (l.target as any).id : l.target,
            value: (l as any).value || 1
          }))
        }
      }))
    } catch (e) {}
  }, [graphData])

  useEffect(() => {
    const handler = (ev: any) => {
      const msg = ev.detail
      if (!msg || !msg.type) return

      // NOTE: We intentionally do NOT create graph nodes from raw 'transcript.final'
      // text here anymore. Node creation is driven exclusively by backend 'graph.patch'
      // events, which use semantic embedding-based topic clustering (TopicManager) and
      // DB-level fuzzy merging (graph_store.py). Having the frontend independently
      // extract naive n-gram "topics" from every final segment caused a flood of
      // near-duplicate, unclustered, disconnected nodes.

      if (msg.type === 'graph.patch') {
        const patch = msg.payload || {}
        const added = patch.nodesAdded || []
        // Map backend node IDs (UUIDs from DB) → frontend label-based IDs.
        // Persisted across messages (ref) so edges referencing nodes added in
        // earlier patches still resolve correctly.
        const backendIdMap = backendIdMapRef.current
        const isUUIDLike = (v: string) => /[0-9a-f]{8}-[0-9a-f]{4}/i.test(v) || /^[0-9a-f]{10,}$/i.test(v.replace(/-/g, ''))
        // Reject labels that are clearly system/mock noise
        const isMockOrNoise = (label: string) => {
          if (/\(mock/i.test(label)) return true
          if (/transcribed?\s+\d+\s+bytes?/i.test(label)) return true
          if (/^\s*\d[\d\s,]+\s*(bytes?|kb|mb)?\s*$/i.test(label)) return true
          if (/(partial|final)\s+(transcri|chunk)/i.test(label)) return true
          return false
        }
        for (const bn of added) {
          const label = (bn.label || '').toString()
          if (!label || label.split(/\s+/).length > 6) continue
          // Skip UUID-as-label (backend segment IDs or node DB IDs used as labels)
          if (isUUIDLike(label)) continue
          // Skip mock/system noise labels
          if (isMockOrNoise(label)) continue
          const id = 'topic:' + slugify(label)
          const timestamps = Array.isArray(bn.timestamps) ? bn.timestamps.map((t: any) => Number(t)).filter((t: number) => Number.isFinite(t)) : []
          const existing = nodesMap.current.get(id)
          if (!existing) nodesMap.current.set(id, { id, label, __added: Date.now(), timestamps, x: 0, y: 0 })
          else if (timestamps.length) existing.timestamps = Array.from(new Set([...(existing.timestamps || []), ...timestamps])).sort((a, b) => a - b)
          // Record mapping from backend UUID → frontend label-based ID
          if (bn.id) backendIdMap.set(String(bn.id), id)
        }

        const edges = patch.edgesAdded || []
        for (const be of edges) {
          let rawS = (be.source || '').toString()
          let rawT = (be.target || '').toString()
          // Resolve backend UUID IDs to frontend label-based IDs
          if (backendIdMap.has(rawS)) rawS = backendIdMap.get(rawS)!
          if (backendIdMap.has(rawT)) rawT = backendIdMap.get(rawT)!
          // Skip if still UUID-like (unresolvable node reference)
          if (isUUIDLike(rawS) || isUUIDLike(rawT)) continue
          const s = rawS.startsWith('topic:') ? rawS : 'topic:' + slugify(rawS)
          const t = rawT.startsWith('topic:') ? rawT : 'topic:' + slugify(rawT)
          // Only add edges between existing nodes (never create phantom UUID nodes)
          if (!nodesMap.current.has(s) || !nodesMap.current.has(t)) continue
          const key = [s, t].sort().join('__')
          const prev = linksMap.current.get(key)
          if (prev) prev.value = Math.max(prev.value, be.value || be.weight || 1)
          else linksMap.current.set(key, { source: s, target: t, value: be.value || be.weight || 1 })
        }

        // Handle removals from reanalysis/reclustering passes on the backend
        // (merged-away or pruned clusters). Nodes may be referenced either by
        // backend UUID or by frontend label-based id.
        const removedNodes = patch.nodesRemoved || []
        for (const rn of removedNodes) {
          const rawId = (typeof rn === 'string' ? rn : rn?.id || '').toString()
          if (!rawId) continue
          const resolved = backendIdMap.get(rawId) || rawId
          nodesMap.current.delete(resolved)
          backendIdMap.delete(rawId)
          // drop any links referencing the removed node
          for (const [key, l] of Array.from(linksMap.current.entries())) {
            if (l.source === resolved || l.target === resolved) linksMap.current.delete(key)
          }
        }

        const removedEdges = patch.edgesRemoved || []
        for (const re of removedEdges) {
          let rawS = (re.source || '').toString()
          let rawT = (re.target || '').toString()
          if (backendIdMap.has(rawS)) rawS = backendIdMap.get(rawS)!
          if (backendIdMap.has(rawT)) rawT = backendIdMap.get(rawT)!
          const s = rawS.startsWith('topic:') ? rawS : 'topic:' + slugify(rawS)
          const t = rawT.startsWith('topic:') ? rawT : 'topic:' + slugify(rawT)
          const key = [s, t].sort().join('__')
          linksMap.current.delete(key)
        }

        setGraphData({ nodes: Array.from(nodesMap.current.values()), links: Array.from(linksMap.current.values()) })

        // center & fit
        try {
          if (fgRef.current) {
            fgRef.current.centerAt(0, 0, 300)
            fgRef.current.zoomToFit(300, 40)
          }
        } catch (e) {}
      }
    }

    window.addEventListener('yap:ws:event', handler)
    return () => window.removeEventListener('yap:ws:event', handler)
  }, [])

  useEffect(() => {
    const id = setTimeout(() => {
      try {
        if (fgRef.current && graphData.nodes.length > 0) fgRef.current.zoomToFit(200, 400)
      } catch (e) {}
    }, 300)
    return () => clearTimeout(id)
  }, [graphData.nodes.length])

  // derive neighbors, degrees and component colors whenever graph changes
  useEffect(() => {
    // build neighbor map and degree map
    const neigh = new Map<string, Set<string>>()
    const deg = new Map<string, number>()
    for (const n of graphData.nodes) {
      neigh.set(n.id, new Set())
      deg.set(n.id, 0)
    }
    for (const l of graphData.links) {
      const s = typeof l.source === 'object' ? (l.source as any).id : l.source
      const t = typeof l.target === 'object' ? (l.target as any).id : l.target
      if (!neigh.has(s)) neigh.set(s, new Set())
      if (!neigh.has(t)) neigh.set(t, new Set())
      neigh.get(s)!.add(t)
      neigh.get(t)!.add(s)
      deg.set(s, (deg.get(s) || 0) + (l.value || 1))
      deg.set(t, (deg.get(t) || 0) + (l.value || 1))
    }
    neighborMapRef.current = neigh
    degreeMapRef.current = deg

    // compute color mapping: prefer time-based hue (earlier -> cool, later -> warm)
    let minTime = Infinity
    let maxTime = -Infinity
    for (const n of graphData.nodes) {
      const ts = (n as any).timestamps || []
      if (ts && ts.length) {
        const localMin = Math.min(...ts)
        const localMax = Math.max(...ts)
        if (localMin < minTime) minTime = localMin
        if (localMax > maxTime) maxTime = localMax
      }
    }

    const nodeColor = new Map<string, string>()
    if (isFinite(minTime) && isFinite(maxTime) && maxTime > minTime) {
      for (const n of graphData.nodes) {
        const ts = (n as any).timestamps || []
        if (ts && ts.length) {
          const avg = ts.reduce((a: number, b: number) => a + b, 0) / ts.length
          const normTime = (avg - minTime) / (maxTime - minTime)
          const hue = Math.round(260 - normTime * 220) // 260 (blue) -> 40 (red)
          nodeColor.set(n.id, `hsl(${hue},72%,55%)`)
        } else {
          // fallback color
          nodeColor.set(n.id, 'hsl(200,60%,60%)')
        }
      }
    } else {
      // fallback to degree-based hue
      let minDeg = Infinity
      let maxDeg = 0
      deg.forEach((v) => {
        if (v < minDeg) minDeg = v
        if (v > maxDeg) maxDeg = v
      })
      if (minDeg === Infinity) {
        minDeg = 1
        maxDeg = 1
      }
      for (const n of graphData.nodes) {
        const d = deg.get(n.id) || 1
        const norm = (d - minDeg) / (Math.max(1, maxDeg - minDeg))
        const hue = Math.round(220 - norm * 200) // 220 (blue) -> 20 (red)
        nodeColor.set(n.id, `hsl(${hue},70%,55%)`)
      }
    }
    colorMapRef.current = nodeColor
  }, [graphData])

  // configure d3 forces with tighter clustering, better spacing, and smoother layout
  useEffect(() => {
    try {
      if (!fgRef.current) return
      
      // Better link force: responsive distance based on connection strength
      const linkForce = forceLink()
        .id((d: any) => d.id)
        .distance((d: any) => {
          const v = d.value || 1
          // Stronger connections have shorter distances (pull closer)
          return Math.max(25, 100 / Math.sqrt(v))
        })
        .strength(1.0) // Stronger attraction

      // Stronger repulsion to prevent overcrowding
      const charge = forceManyBody().strength(-80).minDistance(10).maxDistance(500)
      
      // Better collision detection: larger radius for bigger nodes
      const collide = forceCollide()
        .radius((d: any) => {
          const id = d.id
          const deg = degreeMapRef.current.get(id) || 1
          const base = 8 + Math.sqrt(deg) * 7
          return base * 1.3 // Increased padding to prevent overlap
        })
        .strength(1.0)
        .iterations(3) // Multiple iterations for better stability

      fgRef.current.d3Force('link', linkForce)
      fgRef.current.d3Force('charge', charge)
      fgRef.current.d3Force('collision', collide)
      fgRef.current.d3Force('center', forceCenter(0, 0).strength(0.1))
      fgRef.current.d3ReheatSimulation()
    } catch (e) {}
  }, [graphData])

  function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
    const min = Math.min(w / 2, h / 2, r)
    ctx.beginPath()
    ctx.moveTo(x + min, y)
    ctx.arcTo(x + w, y, x + w, y + h, min)
    ctx.arcTo(x + w, y + h, x, y + h, min)
    ctx.arcTo(x, y + h, x, y, min)
    ctx.arcTo(x, y, x + w, y, min)
    ctx.closePath()
  }

  const drawNode = (node: TopicNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const id = node.id
    const degree = Math.max(1, degreeMapRef.current.get(id) || 1)
    const baseSize = 4 + Math.sqrt(degree) * 4
    const size = baseSize / Math.max(0.5, globalScale)
    const color = colorMapRef.current.get(id) || 'hsl(200,60%,60%)'
    const isHovered = (hoverNode && hoverNode.id === id)
    const isSelected = (selectedNode && selectedNode.id === id)

    ctx.save()
    
    // Main node circle with glow effect
    if (isHovered || isSelected) {
      // Strong glow for hovered/selected
      ctx.beginPath()
      ctx.shadowBlur = 16
      ctx.shadowColor = color
      ctx.globalAlpha = 0.4
      ctx.fillStyle = color
      ctx.arc(node.x, node.y, size * 1.5, 0, Math.PI * 2, false)
      ctx.fill()
    }
    
    ctx.shadowBlur = 0
    ctx.globalAlpha = 1.0
    ctx.beginPath()
    ctx.shadowBlur = 6
    ctx.shadowColor = color
    ctx.fillStyle = color
    ctx.arc(node.x, node.y, size, 0, Math.PI * 2, false)
    ctx.fill()

    // Highlight ring for interactive states
    ctx.lineWidth = (isHovered || isSelected) ? 3 : 1.5
    ctx.strokeStyle = isHovered ? 'rgba(255,255,255,0.8)' : (isSelected ? 'rgba(255,200,100,0.6)' : 'rgba(255,255,255,0.3)')
    ctx.beginPath()
    ctx.arc(node.x, node.y, size, 0, Math.PI * 2, false)
    ctx.stroke()

    // Label rendering: near-invisible by default, fully revealed on hover/select.
    // This declutters dense graphs — labels only "pop in" when the user is
    // actually interested in a specific node.
    const isImportantHub = degree >= 6 // always show a faint hint for major hub nodes
    const labelAlpha = isHovered || isSelected ? 1.0 : (isImportantHub ? 0.16 : 0.05)

    const baseFontSize = Math.max(11, (baseSize * 1.8) / Math.max(0.5, globalScale))
    const fontSize = isHovered || isSelected ? baseFontSize * 1.15 : baseFontSize
    const labelLines = node.label.length > 20 ? node.label.split(/\s+/).reduce((acc: string[], word: string) => {
      if (!acc.length) return [word]
      const lastLen = acc[acc.length - 1].length
      if (lastLen + word.length + 1 > 15) return [...acc, word]
      acc[acc.length - 1] += ' ' + word
      return acc
    }, []) : [node.label]
    
    ctx.shadowBlur = 0
    ctx.font = `bold ${fontSize}px Inter, Arial, sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    
    // Measure text to draw background
    const lineHeight = fontSize * 1.25
    const maxWidth = Math.max(...labelLines.map(line => ctx.measureText(line).width)) + 12
    const totalHeight = labelLines.length * lineHeight + 8
    const labelY = (node.y || 0) - size - 8 - (totalHeight / 2)
    
    // Draw semi-transparent background for text (only meaningful when visible)
    ctx.fillStyle = 'rgba(0, 0, 0, 0.65)'
    ctx.globalAlpha = labelAlpha
    roundRect(ctx, (node.x || 0) - maxWidth / 2, labelY - totalHeight / 2, maxWidth, totalHeight, 4)
    ctx.fill()
    
    // Draw border around label background
    ctx.strokeStyle = color
    ctx.lineWidth = 1
    ctx.globalAlpha = labelAlpha * 0.6
    ctx.stroke()
    
    // Draw text with better contrast
    ctx.fillStyle = '#fff'
    ctx.globalAlpha = labelAlpha
    for (let i = 0; i < labelLines.length; i++) {
      const yOffset = labelY - ((labelLines.length - 1) * lineHeight) / 2 + i * lineHeight
      ctx.fillText(labelLines[i], node.x, yOffset)
    }
    ctx.globalAlpha = 1.0

    ctx.restore()
  }

  const drawLink = (link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const source = typeof link.source === 'object' ? link.source : nodesMap.current.get(link.source)
    const target = typeof link.target === 'object' ? link.target : nodesMap.current.get(link.target)
    if (!source || !target) return

    const sourceColor = colorMapRef.current.get(source.id) || 'hsl(200,60%,60%)'
    const targetColor = colorMapRef.current.get(target.id) || sourceColor
    const gradient = ctx.createLinearGradient(source.x || 0, source.y || 0, target.x || 0, target.y || 0)
    gradient.addColorStop(0, sourceColor)
    gradient.addColorStop(1, targetColor)

    ctx.save()
    ctx.beginPath()
    ctx.strokeStyle = gradient
    // Better visibility: stronger connections are more opaque
    const linkStrength = link.value || 1
    ctx.globalAlpha = Math.min(0.6, 0.25 + Math.log(linkStrength + 1) * 0.15)
    ctx.lineWidth = Math.max(0.5, (0.5 + Math.log(linkStrength + 1) * 0.8) / Math.max(0.5, globalScale))
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.moveTo(source.x || 0, source.y || 0)
    ctx.lineTo(target.x || 0, target.y || 0)
    ctx.stroke()
    ctx.restore()
  }

  const handleNodeClick = (node: any) => {
    try {
      window.dispatchEvent(new CustomEvent('yap:graph:nodeClick', { detail: node }))
    } catch (e) {}
  }

  return (
    <div style={{ position: 'fixed', inset: 0, borderRadius: 10, overflow: 'hidden' }}>
      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        backgroundColor="#000000"
        nodeCanvasObject={drawNode}
        linkCanvasObject={drawLink}
        linkCanvasObjectMode={() => 'replace'}
        nodePointerAreaPaint={(node: any, color: any, ctx: CanvasRenderingContext2D) => {
          const id = node.id
          const size = Math.max(3, (Math.sqrt(Math.max(1, degreeMapRef.current.get(id) || 1)) * 3) / (fgRef.current ? fgRef.current.zoom() : 1))
          ctx.beginPath()
          ctx.arc(node.x, node.y, size, 0, Math.PI * 2, false)
          ctx.fillStyle = color
          ctx.fill()
        }}
        onNodeClick={(node) => {
          setSelectedNode(node)
          try {
            if (fgRef.current) {
              fgRef.current.centerAt(node.x, node.y, 400)
              fgRef.current.zoom(1.4, 300)
            }
          } catch (e) {}
          handleNodeClick(node)
        }}
        onNodeHover={(node) => setHoverNode(node)}
        linkWidth={(l: any) => 0}
        linkColor={(l: any) => 'rgba(0,0,0,0)'}
        linkDirectionalParticles={0}
        autoPauseRedraw={false}
        d3VelocityDecay={0.2}
        nodeRelSize={6}
        width={dimensions.width}
        height={dimensions.height}
        onEngineStop={() => {
          try {
            if (fgRef.current && graphData.nodes.length > 0) fgRef.current.zoomToFit(200, 400)
          } catch (e) {}
        }}
      />
    </div>
  )
}
