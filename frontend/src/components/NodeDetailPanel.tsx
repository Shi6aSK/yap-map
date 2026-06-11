import React, { useEffect, useState } from 'react'

type Segment = { id: string; text: string; createdAt?: string }

export default function NodeDetailPanel() {
  const [selectedNode, setSelectedNode] = useState<any | null>(null)
  const [segmentsById, setSegmentsById] = useState<Record<string, Segment>>({})

  useEffect(() => {
    const onSegment = (ev: any) => {
      const seg = ev.detail
      setSegmentsById((s) => ({ ...s, [seg.id]: seg }))
    }

    const onNodeClick = (ev: any) => {
      setSelectedNode(ev.detail)
    }

    window.addEventListener('yap:transcript:final', onSegment)
    window.addEventListener('yap:graph:nodeClick', onNodeClick)
    return () => {
      window.removeEventListener('yap:transcript:final', onSegment)
      window.removeEventListener('yap:graph:nodeClick', onNodeClick)
    }
  }, [])

  if (!selectedNode) {
    return <div style={{ marginTop: 18 }}>Select a node to see details</div>
  }

  const segIds: string[] = selectedNode.segmentIds || []

  return (
    <div style={{ marginTop: 18, padding: 8, border: '1px solid #ddd', borderRadius: 6 }}>
      <h3>Node detail</h3>
      <div><strong>{selectedNode.label}</strong> <small>({selectedNode.type})</small></div>
      <div style={{ marginTop: 8 }}>
        <h4>Related transcript segments</h4>
        {segIds.length === 0 && <div><em>No linked segments</em></div>}
        {segIds.map((id) => {
          const s = segmentsById[id]
          if (!s) return <div key={id}>Loading segment {id}…</div>
          return (
            <div key={id} style={{ padding: 6, borderBottom: '1px solid #eee' }}>
              <div>{s.text}</div>
              <div style={{ fontSize: 12, color: '#666' }}>{s.createdAt}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
