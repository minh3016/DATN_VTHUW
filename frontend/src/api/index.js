/**
 * api/index.js - API client
 * Traffic Violation Detection System v4.0
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

// ── Detections (vehicles) ─────────────────────────────────────
export const getDetections = (params = {}) =>
  api.get('/api/detections', { params })

export const deleteDetection = (id) =>
  api.delete(`/api/detections/${id}`)

// ── Stats (vehicles) ─────────────────────────────────────────
export const getStats = (hours = 24) =>
  api.get('/api/stats', { params: { hours } })

// ── Violations ────────────────────────────────────────────────
export const getViolations = (params = {}) =>
  api.get('/api/violations', { params })

export const deleteViolation = (id) =>
  api.delete(`/api/violations/${id}`)

export const getViolationStats = (hours = 24) =>
  api.get('/api/violations/stats', { params: { hours } })

// ── Red Light Configuration & Stats ───────────────────────────
export const saveRedLightConfig = (config) =>
  api.post('/api/config/red-light', config)

export const getRedLightConfig = (sourceId) =>
  api.get(`/api/config/red-light/${sourceId}`)

export const getRedLightStats = (hours = 24) =>
  api.get('/api/violations/red-light/stats', { params: { hours } })

// ── Plates ───────────────────────────────────────────────────
export const getPlateDetections = (params = {}) =>
  api.get('/api/plates', { params })

export const deletePlateDetection = (id) =>
  api.delete(`/api/plates/${id}`)

export const getPlateStats = (hours = 24) =>
  api.get('/api/plates/stats', { params: { hours } })

// ── Image Analysis ────────────────────────────────────────────
export const analyzeImage = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/api/analyze/image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
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

export const startAnalysis = (jobId, frameSkip = 1) =>
  api.post(`/api/upload/${jobId}/analyze`, null, { params: { frame_skip: frameSkip } })

export const getAnalysisStatus = (jobId) =>
  api.get(`/api/upload/${jobId}/status`)

export const pauseAnalysis = (jobId) =>
  api.post(`/api/upload/${jobId}/pause`)

export const resumeAnalysis = (jobId) =>
  api.post(`/api/upload/${jobId}/resume`)

export const seekAnalysis = (jobId, frame) =>
  api.post(`/api/upload/${jobId}/seek`, null, { params: { frame } })

// ── Evidence ──────────────────────────────────────────────────
export const getEvidenceUrl = (evidencePath) => {
  if (!evidencePath) return ''
  return `${API_BASE}/api/${evidencePath}`
}

// ── Export Excel ──────────────────────────────────────────────
export const exportExcel = ({ dataTypes, dataType, days = 7, limit = 1000 }) => {
  const typesParam = Array.isArray(dataTypes) ? dataTypes.join(',') : (dataTypes || dataType)
  return api.get('/api/export/excel', {
    params: { data_types: typesParam, days, limit },
    responseType: 'blob',
  })
}

// ── WebSocket (for upload progress) ───────────────────────────
export function createWebSocket(room = 'upload') {
  const wsBase = (import.meta.env.VITE_WS_URL || API_BASE).replace(/^http/, 'ws')
  return new WebSocket(`${wsBase}/ws/${room}`)
}
