import axios from 'axios'

// Use VITE_API_BASE if set (e.g. for production), otherwise empty string (proxied via vite dev server)
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

export const api = axios.create({ baseURL: API_BASE })
