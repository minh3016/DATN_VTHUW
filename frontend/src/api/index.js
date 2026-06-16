/**
 * api/index.js - API client
 * Vehicle Classification System - YOLOv7
 */
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || 'Lỗi không xác định'
    return Promise.reject(new Error(msg))
  }
)

// ── Health ────────────────────────────────────────────────────
export const getHealth = () => api.get('/')

// ── Detections ─────────────────────────────────────────────────
export const getDetections = (params = {}) =>
  api.get('/api/detections', { params })

export const deleteDetection = (id) =>
  api.delete(`/api/detections/${id}`)

// ── Stats ─────────────────────────────────────────────────────
export const getStats = (hours = 24) =>
  api.get('/api/stats', { params: { hours } })

// ── Analyze Image (upload ảnh) ────────────────────────────────
export const analyzeImage = (file, onProgress = null) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/api/analyze/image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    },
  })
}

// ── Video Upload & Analysis ───────────────────────────────────
export const uploadVideo = (file, onProgress = null) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    },
  })
}

export const startAnalysis = (jobId) =>
  api.post(`/api/upload/${jobId}/analyze`)

export const getAnalysisStatus = (jobId) =>
  api.get(`/api/upload/${jobId}/status`)

// ── Evidence ──────────────────────────────────────────────────
export const getEvidenceUrl = (evidencePath) => {
  if (!evidencePath) return ''
  return `${API_BASE}/api/${evidencePath}`
}

// ── WebSocket (for upload progress) ───────────────────────────
export function createWebSocket(room = 'upload') {
  const wsBase = (import.meta.env.VITE_WS_URL || API_BASE).replace(/^http/, 'ws')
  return new WebSocket(`${wsBase}/ws/${room}`)
}
