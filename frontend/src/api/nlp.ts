import { api } from './client'

export interface NLPTopic { label: string; score: number }
export interface NLPEdge  { source: string; target: string; value: number }

export interface NLPExtractResult {
  topics: NLPTopic[]
  edges: NLPEdge[]
}

export async function extractTopicsNLP(text: string, topN = 30): Promise<NLPExtractResult> {
  const resp = await api.post('/api/nlp/extract', { text, top_n: topN })
  return resp.data
}
