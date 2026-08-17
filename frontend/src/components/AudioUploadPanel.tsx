import React, { useRef, useState } from 'react'
import axios from 'axios'

interface Props {
  onTranscript: (transcript: string, concepts: any) => void
  onError: (msg: string) => void
  onComplete: () => void
}

export default function AudioUploadPanel({ onTranscript, onError, onComplete }: Props) {
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setLoading(true)
    setProgress(0)
    
    try {
      const formData = new FormData()
      formData.append('file', file)

      const apiBase = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8000'

      const response = await axios.post(
        `${apiBase}/api/nlp/transcribe-audio`,
        formData,
        {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (progressEvent) => {
            if (progressEvent.total) {
              setProgress(Math.round((progressEvent.loaded / progressEvent.total) * 100))
            }
          }
        }
      )

      const { transcript, concepts } = response.data
      onTranscript(transcript, concepts)
      setProgress(0)
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Upload failed'
      onError(msg)
      setProgress(0)
    } finally {
      setLoading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center' }}>
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={loading}
        style={{
          minWidth: 200,
          padding: '11px 18px',
          borderRadius: 999,
          border: '1px solid rgba(255,255,255,0.16)',
          background: loading ? 'rgba(255,255,255,0.12)' : 'linear-gradient(135deg,rgba(200,170,255,0.95),rgba(170,200,255,0.88))',
          color: '#fff',
          fontWeight: 700,
          fontSize: 14,
          cursor: loading ? 'default' : 'pointer',
          boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
        }}
      >
        {loading ? `Transcribing... ${progress}%` : '📁 Upload Audio File'}
      </button>
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*"
        onChange={handleFileSelect}
        style={{ display: 'none' }}
      />
      <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.6)', margin: 0, textAlign: 'center' }}>
        Supports: MP3, WAV, WEBM, OGG, FLAC, M4A
      </p>
    </div>
  )
}
