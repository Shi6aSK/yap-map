// IndexedDB-backed session persistence

export interface SerializedNode {
  id: string
  label: string
  timestamps?: number[]
}

export interface SerializedLink {
  source: string
  target: string
  value: number
}

export interface TranscriptSegment {
  text: string
  ts: number // ms since session start
}

export interface GraphSnapshot {
  ts: number // ms since session start
  nodes: SerializedNode[]
  links: SerializedLink[]
}

export interface YapSession {
  id: string
  title: string
  createdAt: number // unix ms
  duration: number  // ms
  transcript: TranscriptSegment[]
  snapshots: GraphSnapshot[] // sampled graph states over time
}

const DB_NAME = 'yapmap_sessions_v1'
const DB_VERSION = 1
const STORE_NAME = 'sessions'

let _db: IDBDatabase | null = null

function openDB(): Promise<IDBDatabase> {
  if (_db) return Promise.resolve(_db)
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' })
        store.createIndex('createdAt', 'createdAt')
      }
    }
    req.onsuccess = () => { _db = req.result; resolve(_db!) }
    req.onerror = () => reject(req.error)
  })
}

export const sessionStore = {
  async save(session: YapSession): Promise<void> {
    const db = await openDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite')
      tx.objectStore(STORE_NAME).put(session)
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
  },

  async list(): Promise<YapSession[]> {
    const db = await openDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly')
      const req = tx.objectStore(STORE_NAME).getAll()
      req.onsuccess = () => {
        const all: YapSession[] = req.result || []
        resolve(all.sort((a, b) => b.createdAt - a.createdAt))
      }
      req.onerror = () => reject(req.error)
    })
  },

  async get(id: string): Promise<YapSession | null> {
    const db = await openDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly')
      const req = tx.objectStore(STORE_NAME).get(id)
      req.onsuccess = () => resolve(req.result || null)
      req.onerror = () => reject(req.error)
    })
  },

  async delete(id: string): Promise<void> {
    const db = await openDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite')
      tx.objectStore(STORE_NAME).delete(id)
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
  },
}
