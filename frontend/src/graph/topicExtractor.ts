// Lightweight topic extraction utilities used by GraphCanvas and BatchTopicManager

export type Segment = { id?: string; text: string; ts?: number }

const STOPWORDS = new Set([
  'the','and','for','are','you','that','with','this','have','from','was','what','when','where','how',
  'a','an','in','on','of','to','is','it','i','we','they','be','as','at','by','or','if','but','not',
  'do','so','can','will','just','about','your','s','t','m','d','re','ve','ll',
  'yeah','yes','no','um','uh','okay','ok','like','right','well','actually','basically',
  'you know','kind','got','get','gonna','going','today','now','think','know','people',
  'want','really','very','much','still','even','maybe','probably','something','someone',
  'way','thing','things','make','made','time','see','use','also','never','always','every',
  'lot','many','more','most','some','same','another','other','new','old','good','great',
  'little','big','small','first','last','next','back','long','work','call','need','come',
  'tell','mean','keep','high','low','thought','feel','felt','take','gave','give','took',
  'say','said','look','try','tried','ask','asked','go','went','gone','put','let','bit',
  'then','than','here','there','just','very','too','over','after','before','between',
  'because','though','while','already','again','around','without','within','through'
])

// UUID and hex-string detection
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const PARTIAL_UUID_RE = /[0-9a-f]{8}-[0-9a-f]{4}/i
const LONG_HEX_RE = /^[0-9a-f]{10,}$/i

function isNoisyToken(raw: string, normalized: string): boolean {
  if (UUID_RE.test(raw) || PARTIAL_UUID_RE.test(raw)) return true
  if (LONG_HEX_RE.test(normalized)) return true
  // mostly digits/hex chars
  const hexRatio = (normalized.match(/[0-9a-f]/gi) || []).length / normalized.length
  if (normalized.length > 6 && hexRatio > 0.7) return true
  // pure numeric strings (e.g. "16000")
  if (/^\d+$/.test(normalized)) return true
  return false
}

function normalizeToken(w: string) {
  let t = w.toLowerCase().replace(/[^a-z0-9]/g, '')
  if (!t) return ''
  // strip simple plural/tense endings heuristically
  if (t.length > 5 && t.endsWith('ies')) t = t.replace(/ies$/, 'y')
  else if (t.length > 4 && t.endsWith('ing')) t = t.replace(/ing$/, '')
  else if (t.length > 3 && t.endsWith('ed')) t = t.replace(/ed$/, '')
  else if (t.length > 3 && t.endsWith('es')) t = t.replace(/es$/, 'e')
  else if (t.length > 2 && t.endsWith('s')) t = t.replace(/s$/, '')
  return t
}

export function slugify(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}

function tokenize(text: string) {
  const clean = (text || '').toLowerCase().replace(/[’'`]/g, "'")
  const toks = clean.split(/\s+/).map((t) => t.replace(/[^a-z0-9\-]/g, '')).filter(Boolean)
  const res: string[] = []
  for (const t of toks) {
    if (/^\d+$/.test(t)) continue
    const n = normalizeToken(t)
    if (!n) continue
    if (n.length < 3) continue
    if (STOPWORDS.has(n)) continue
    if (isNoisyToken(t, n)) continue
    res.push(n)
  }
  return res
}

export function extractTopicsFromText(text: string, maxTopics = 3): string[] {
  if (!text) return []
  const tokens = tokenize(text)
  if (tokens.length === 0) return []

  const uniFreq = new Map<string, number>()
  for (const w of tokens) uniFreq.set(w, (uniFreq.get(w) || 0) + 1)

  const biFreq = new Map<string, number>()
  for (let i = 0; i < tokens.length - 1; i++) {
    const b = `${tokens[i]} ${tokens[i + 1]}`
    biFreq.set(b, (biFreq.get(b) || 0) + 1)
  }

  // scoring: prefer bi-grams strongly but reward frequent unigrams
  const candidates = new Map<string, number>()
  for (const [k, v] of biFreq.entries()) candidates.set(k, v * 4)
  for (const [k, v] of uniFreq.entries()) candidates.set(k, Math.max(candidates.get(k) || 0, v * 1.5))

  // sort by score, but longer phrases first on tie
  const sorted = Array.from(candidates.entries()).sort((a, b) => {
    if (b[1] !== a[1]) return b[1] - a[1]
    return b[0].length - a[0].length
  })

  const topics: string[] = []
  for (const [cand] of sorted) {
    if (topics.length >= maxTopics) break
    if (!cand || cand.length < 2) continue
    topics.push(cand)
  }

  // fallback to first meaningful tokens if no topics
  if (topics.length === 0) {
    const fallback = tokens.slice(0, Math.min(2, tokens.length))
    if (fallback.length > 0) topics.push(fallback.join(' '))
  }

  // map normalized tokens back to prettier labels (replace '-' with space)
  return Array.from(new Set(topics)).map((t) => t.replace(/\s+/g, ' ').trim())
}

export function extractTopicsFromSegments(segments: Segment[], maxTopics = 6) {
  if (!segments || segments.length === 0) return []
  // aggregate tokens across segments to get more robust topics
  const globalUni = new Map<string, number>()
  const globalBi = new Map<string, number>()
  for (const seg of segments) {
    const toks = tokenize(seg.text)
    const seen = new Set<string>()
    for (const t of toks) {
      globalUni.set(t, (globalUni.get(t) || 0) + 1)
      seen.add(t)
    }
    for (let i = 0; i < toks.length - 1; i++) {
      const b = `${toks[i]} ${toks[i + 1]}`
      globalBi.set(b, (globalBi.get(b) || 0) + 1)
    }
  }

  const candidates = new Map<string, number>()
  for (const [k, v] of globalBi.entries()) candidates.set(k, v * 4)
  for (const [k, v] of globalUni.entries()) candidates.set(k, Math.max(candidates.get(k) || 0, v * 1.5))

  const sorted = Array.from(candidates.entries()).sort((a, b) => {
    if (b[1] !== a[1]) return b[1] - a[1]
    return b[0].length - a[0].length
  })

  const topics: string[] = []
  for (const [cand] of sorted) {
    if (topics.length >= maxTopics) break
    topics.push(cand)
  }

  if (topics.length === 0) {
    // fallback: first non-stop tokens across segments
    for (const seg of segments) {
      const toks = tokenize(seg.text)
      for (const t of toks) {
        if (topics.length >= maxTopics) break
        topics.push(t)
      }
      if (topics.length >= maxTopics) break
    }
  }

  return Array.from(new Set(topics)).map((t) => t.replace(/\s+/g, ' ').trim())
}
