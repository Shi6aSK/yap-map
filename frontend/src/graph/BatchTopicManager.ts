import { extractTopicsFromText, extractTopicsFromSegments, slugify } from './topicExtractor'

type TranscriptSegment = { id: string; text: string; ts: number }

export class BatchTopicManager {
  initialDelaySeconds: number
  updateIntervalSeconds: number
  maxTopicsPerSeg: number

  private buffer: TranscriptSegment[] = []
  private listener: any = null
  private initialTimer: any = null
  private updateTimer: any = null
  private isActive = false
  private lastNodes = new Map<string, number>()
  private lastEdges = new Map<string, number>()

  constructor(opts?: { initialDelaySeconds?: number; updateIntervalSeconds?: number; maxTopicsPerSeg?: number }) {
    // default to 60s in production, shorter in DEV for faster iteration
    const devDefault = typeof import.meta !== 'undefined' && (import.meta as any).env && (import.meta as any).env.DEV
    this.initialDelaySeconds = opts?.initialDelaySeconds ?? (devDefault ? 6 : 60)
    this.updateIntervalSeconds = opts?.updateIntervalSeconds ?? 10
    this.maxTopicsPerSeg = opts?.maxTopicsPerSeg ?? 3
  }

  start() {
    if (this.isActive) return
    this.isActive = true
    this.buffer = []
    this.lastNodes = new Map()
    this.lastEdges = new Map()

    this.listener = (ev: any) => {
      const msg = ev.detail
      if (!msg || msg.type !== 'transcript.final') return
      const seg = msg.payload
      if (!seg || !seg.text) return
      this.buffer.push({ id: seg.id || `seg-${Date.now()}`, text: seg.text, ts: Date.now() })
    }

    window.addEventListener('yap:ws:event', this.listener)
    this.initialTimer = setTimeout(() => this._initialProcess(), this.initialDelaySeconds * 1000)
  }

  private _initialProcess() {
    this.processBuffer()
    this._callNLPBackend()
    this.updateTimer = setInterval(() => {
      this.processBuffer()
      this._callNLPBackend()
    }, this.updateIntervalSeconds * 1000)
  }

  private async _callNLPBackend() {
    if (this.buffer.length < 3) return
    const fullText = this.buffer.map(s => s.text).join(' ')
    if (fullText.trim().length < 50) return
    try {
      const apiBase = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE) || ''
      const url = apiBase ? `${apiBase}/api/nlp/extract` : '/api/nlp/extract'
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: fullText, top_n: 30 })
      })
      if (!resp.ok) return
      const result = await resp.json()
      const topics: Array<{ label: string; score: number }> = result.topics || []
      const edges: Array<{ source: string; target: string; value: number }> = result.edges || []
      if (topics.length === 0) return

      const nodesAdded = topics.map((t) => ({ id: 'topic:' + slugify(t.label), label: t.label }))
      const edgesAdded = edges.map((e) => ({
        source: 'topic:' + slugify(e.source),
        target: 'topic:' + slugify(e.target),
        value: e.value || 1
      }))
      window.dispatchEvent(new CustomEvent('yap:ws:event', {
        detail: { type: 'graph.patch', payload: { nodesAdded, edgesAdded } }
      }))
    } catch (e) {
      // NLP backend not available — local extraction only
    }
  }

  stop() {
    if (!this.isActive) return
    // send final patch
    this.processBuffer()
    this._callNLPBackend().catch(() => {})

    this.isActive = false
    try {
      window.removeEventListener('yap:ws:event', this.listener)
    } catch (e) {}
    this.listener = null
    if (this.initialTimer) { clearTimeout(this.initialTimer); this.initialTimer = null }
    if (this.updateTimer) { clearInterval(this.updateTimer); this.updateTimer = null }
  }

  processBuffer() {
    try {
      const nodes = new Map<string, { label: string; count: number }>()
      const edges = new Map<string, number>()

      for (const seg of this.buffer) {
        const topics = extractTopicsFromText(seg.text, this.maxTopicsPerSeg)
        for (const t of topics) {
          const id = 'topic:' + slugify(t)
          const prev = nodes.get(id) || { label: t, count: 0 }
          prev.count += 1
          nodes.set(id, prev)
        }
        for (let i = 0; i < topics.length; i++) {
          for (let j = i + 1; j < topics.length; j++) {
            const a = 'topic:' + slugify(topics[i])
            const b = 'topic:' + slugify(topics[j])
            const key = [a, b].sort().join('__')
            edges.set(key, (edges.get(key) || 0) + 1)
          }
        }
      }

      const nodesAdded: Array<{ id: string; label: string }> = []
      const edgesAdded: Array<{ id: string; source: string; target: string; value: number }> = []

      // nodes diffs
      for (const [id, v] of nodes.entries()) {
        if (!this.lastNodes.has(id)) nodesAdded.push({ id, label: v.label })
      }

      // edges diffs (send edges when value changed)
      for (const [key, val] of edges.entries()) {
        const prev = this.lastEdges.get(key) || 0
        if (prev !== val) {
          const [a, b] = key.split('__')
          edgesAdded.push({ id: key, source: a, target: b, value: val })
        }
      }

      if (nodesAdded.length > 0 || edgesAdded.length > 0) {
        const payload = { nodesAdded, edgesAdded }
        try {
          window.dispatchEvent(new CustomEvent('yap:ws:event', { detail: { type: 'graph.patch', payload } }))
        } catch (e) {}
      }

      // persist last full counts
      this.lastNodes = new Map(Array.from(nodes.entries()).map(([k, v]) => [k, v.count]))
      this.lastEdges = new Map(edges.entries())
    } catch (e) {
      console.warn('BatchTopicManager processBuffer failed', e)
    }
  }
}
