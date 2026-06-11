import React from 'react'
import { motion } from 'framer-motion'

function colorFromString(s: string) {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360
  return `hsl(${h}, 70%, 92%)`
}

export default function AnimatedNode(props: any) {
  const { data } = props
  const label = data?.label || ''
  const bg = data?.color || colorFromString(label)

  return (
    <motion.div
      initial={{ scale: 0.6, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      style={{
        padding: '10px 14px',
        borderRadius: 12,
        background: bg,
        border: '1px solid rgba(0,0,0,0.08)',
        boxShadow: '0 6px 14px rgba(23,23,23,0.06)',
        maxWidth: 220,
        textAlign: 'center',
        fontSize: 14,
        color: '#111',
      }}
    >
      {label}
    </motion.div>
  )
}
