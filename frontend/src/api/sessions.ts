import { api } from './client'

export type SessionCreatePayload = { title?: string; mode?: string }

export async function createSession(payload: SessionCreatePayload) {
  const resp = await api.post('/api/sessions', payload)
  return resp.data
}

export async function listSessions() {
  const resp = await api.get('/api/sessions')
  return resp.data
}
