<template>
  <div class="upload-page">
    <header class="page-header">
      <h1><span class="text-gradient">Upload & Phan tich</span></h1>
      <p>Tải lên ảnh hoặc video để phát hiện vi phạm giao thông bằng AI YOLOv8n</p>
    </header>

    <!-- Mode selector -->
    <div class="mode-tabs">
      <button
        class="mode-tab" :class="{ 'mode-tab--active': mode === 'image' }"
        @click="resetAll(); mode = 'image'"
      >Phan tich Anh</button>
      <button
        class="mode-tab" :class="{ 'mode-tab--active': mode === 'video' }"
        @click="resetAll(); mode = 'video'"
      >Phan tich Video</button>
    </div>

    <!-- ============ IMAGE MODE ============ -->
    <div v-if="mode === 'image'" class="mode-content">
      <!-- Upload area -->
      <div
        v-if="!imageResult"
        class="drop-zone"
        :class="{ 'drop-zone--active': dragOver }"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="handleImageDrop"
        @click="$refs.imageInput.click()"
      >
        <input
          ref="imageInput" type="file"
          accept="image/jpeg,image/png,image/bmp,image/webp"
          style="display:none"
          @change="handleImageSelect"
        />

        <!-- Preview if selected -->
        <div v-if="imagePreview" class="preview-in-zone">
          <img :src="imagePreview" alt="preview" class="preview-thumb" />
          <div class="preview-info">
            <span class="preview-name">{{ imageFile?.name }}</span>
            <span class="preview-size">{{ formatSize(imageFile?.size) }}</span>
          </div>
          <button class="btn btn--primary" @click.stop="analyzeCurrentImage" :disabled="imageLoading">
            <span v-if="imageLoading" class="spinner"></span>
            <span v-else>Phan tich</span>
          </button>
        </div>

        <!-- Empty state -->
        <div v-else class="drop-content">
          <div class="drop-icon">IMG</div>
          <p class="drop-title">Kéo thả ảnh vào đây</p>
          <p class="drop-sub">hoặc nhấn để chọn file · JPG, PNG, BMP, WebP · Tối đa 20MB</p>
        </div>
      </div>

      <!-- Upload progress -->
      <div v-if="imageLoading" class="loading-card">
        <span class="spinner spinner--lg"></span>
        <p>Đang phân tích ảnh bằng AI (4 models)...</p>
      </div>

      <!-- Image Result -->
      <div v-if="imageResult" class="result-section animate-fade-in">
        <div class="result-header">
          <h2>Kết quả phân tích hình ảnh</h2>
          <button class="btn btn--ghost" @click="resetAll">Upload ảnh mới</button>
        </div>

        <div class="results-split-layout">
          <!-- Cột bên trái: Ảnh và KPI -->
          <div class="results-visuals-col">
            <!-- Annotated image -->
            <div class="annotated-wrap">
              <img
                v-if="imageResult.frame_base64"
                :src="`data:image/jpeg;base64,${imageResult.frame_base64}`"
                alt="Annotated"
                class="annotated-img"
              />
            </div>

            <!-- Stats cards -->
            <div class="result-stats">
              <div class="rs-card rs-card--blue">
                <span class="rs-icon">🚗</span>
                <span class="rs-val">{{ imageResult.vehicle_count || 0 }}</span>
                <span class="rs-label">Phương tiện</span>
              </div>
              <div class="rs-card rs-card--red">
                <span class="rs-icon">⚠️</span>
                <span class="rs-val">{{ imageResult.violation_count || 0 }}</span>
                <span class="rs-label">Vi phạm</span>
              </div>
              <div class="rs-card rs-card--yellow">
                <span class="rs-icon">🔢</span>
                <span class="rs-val">{{ imageResult.plate_count || 0 }}</span>
                <span class="rs-label">Biển số</span>
              </div>
              <div
                v-for="(cnt, cls) in (imageResult.counts_by_class || {})" :key="cls"
                class="rs-card" :class="`rs-card--${cls}`"
              >
                <span class="rs-icon">{{ classIcon(cls) }}</span>
                <span class="rs-val">{{ cnt }}</span>
                <span class="rs-label">{{ classLabel(cls) }}</span>
              </div>
            </div>

            <!-- Category breakdown -->
            <div v-if="imageResult.counts_by_category" class="category-row">
              <div
                v-for="(cnt, cat) in imageResult.counts_by_category" :key="cat"
                class="cat-chip" :class="`cat-chip--${cat}`"
              >
                <span class="cat-name">{{ catLabel(cat) }}</span>
                <span class="cat-count">{{ cnt }}</span>
              </div>
            </div>
          </div>

          <!-- Cột bên phải: Danh sách chi tiết phát hiện -->
          <div class="results-lists-col">
            <!-- Violations list -->
            <div v-if="imageResult.violations?.length" class="detections-list violations-list">
              <h3>⚠️ Vi phạm giao thông phát hiện</h3>
              <div class="det-grid">
                <div v-for="(viol, i) in imageResult.violations" :key="'v'+i" class="det-item det-item--violation" style="display:flex; align-items:center; justify-content:space-between;">
                  <div style="display:flex; align-items:center; gap:8px;">
                    <span class="det-idx det-idx--danger">{{ i + 1 }}</span>
                    <span class="badge badge--violation" :class="'viol--' + viol.violation_type">{{ viol.violation_label }}</span>
                    <span class="det-conf mono">{{ (viol.bbox.conf * 100).toFixed(0) }}%</span>
                  </div>
                  <span v-if="viol.plate_text" class="plate-text-lg" style="font-size:0.8rem; padding:2px 6px;">{{ viol.plate_text }}</span>
                </div>
              </div>
            </div>

            <!-- Plates list -->
            <div v-if="imageResult.plates?.length" class="detections-list plates-list">
              <h3>🔢 Biển số xe nhận diện</h3>
              <div class="det-grid">
                <div v-for="(plate, i) in imageResult.plates" :key="'p'+i" class="det-item det-item--plate">
                  <span class="det-idx det-idx--plate">{{ i + 1 }}</span>
                  <span class="plate-text-lg">{{ plate.plate_text || 'Không nhận dạng' }}</span>
                  <span class="det-conf mono">{{ plate.avg_ocr_confidence ? (plate.avg_ocr_confidence * 100).toFixed(0) + '%' : '—' }}</span>
                  <img v-if="plate.plate_image_base64" :src="'data:image/jpeg;base64,' + plate.plate_image_base64" class="plate-thumb" alt="plate" />
                </div>
              </div>
            </div>

            <!-- Vehicle detection list -->
            <div v-if="imageResult.vehicles?.length" class="detections-list">
              <h3>🚗 Phương tiện phát hiện trong ROI</h3>
              <div class="det-grid">
                <div v-for="(v, i) in imageResult.vehicles" :key="i" class="det-item" :class="`det-item--${v.category}`">
                  <span class="det-idx">{{ i + 1 }}</span>
                  <span class="badge" :class="classBadge(v.class_name)">{{ classIcon(v.class_name) }} {{ classLabel(v.class_name) }}</span>
                  <span class="det-conf mono">{{ (v.bbox.conf * 100).toFixed(0) }}%</span>
                  <span class="det-cat" style="margin-left:auto;">{{ catLabel(v.category) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ============ VIDEO MODE ============ -->
    <div v-if="mode === 'video'" class="mode-content">
      <!-- Upload -->
      <div v-if="!currentJob" class="upload-section">
        <VideoUploader @uploaded="handleVideoUploaded" @error="handleError" />
      </div>

      <!-- Analysis -->
      <div v-if="currentJob" class="analysis-section">
        <div class="job-card">
          <div class="job-card__header">
            <div class="job-info">
              <h3>{{ currentJob.filename }}</h3>
              <span class="job-meta">
                {{ formatSize(currentJob.file_size) }}
                <span v-if="currentJob.duration_sec"> · {{ formatDuration(currentJob.duration_sec) }}</span>
              </span>
            </div>
            <div class="job-status" :class="`status--${jobStatus?.status || 'pending'}`">
              {{ statusText }}
            </div>
          </div>

          <div class="job-progress" v-if="jobStatus">
            <div class="progress-bar">
              <div class="progress-bar__fill" :style="{ width: Math.round((jobStatus.progress||0)*100) + '%' }"></div>
            </div>
            <div class="progress-text">
              <span>{{ jobStatus.processed_frames||0 }}/{{ jobStatus.total_frames||'?' }} frames ({{ Math.round((jobStatus.progress||0)*100) }}%)</span>
              <span>🚗 {{ jobStatus.vehicles_detected||0 }} · ⚠️ {{ jobStatus.violations_detected||0 }} · 🔢 {{ jobStatus.plates_detected||0 }}</span>
            </div>
          </div>

          <button v-if="!jobStatus || jobStatus.status === 'pending'" class="btn btn--primary" style="width:100%" @click="startVideoAnalysis" :disabled="isStarting">
            {{ isStarting ? 'Dang khoi tao...' : 'Bat dau phan tich' }}
          </button>
        </div>

        <!-- Live preview -->
        <div v-if="latestFrame" class="preview-section">
          <h3>Xem truoc</h3>
          <img :src="'data:image/jpeg;base64,' + latestFrame" alt="Preview" class="annotated-img" />
        </div>

        <!-- Video results -->
        <div v-if="jobStatus?.status === 'completed'" class="result-section animate-fade-in">
          <div class="result-header">
            <h2>Kết quả phân tích video</h2>
            <button class="btn btn--ghost" @click="resetAll">Upload video mới</button>
          </div>

          <div class="results-split-layout">
            <!-- Cột bên trái: Thống kê & Biểu đồ sơ lược -->
            <div class="results-visuals-col">
              <div class="result-stats" style="grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));">
                <div class="rs-card rs-card--blue"><span class="rs-icon">🚗</span><span class="rs-val">{{ jobStatus.vehicles_detected }}</span><span class="rs-label">Phương tiện</span></div>
                <div class="rs-card rs-card--red"><span class="rs-icon">⚠️</span><span class="rs-val">{{ jobStatus.violations_detected || 0 }}</span><span class="rs-label">Vi phạm</span></div>
                <div class="rs-card rs-card--yellow"><span class="rs-icon">🔢</span><span class="rs-val">{{ jobStatus.plates_detected || 0 }}</span><span class="rs-label">Biển số</span></div>
              </div>

              <div class="result-stats" style="grid-template-columns: 1fr 1fr; margin-top: 0;">
                <div class="rs-card rs-card--car"><span class="rs-icon">Oto</span><span class="rs-val">{{ jobStatus.counts_by_category?.oto||0 }}</span><span class="rs-label">Xe ô tô</span></div>
                <div class="rs-card rs-card--motorcycle"><span class="rs-icon">Moto</span><span class="rs-val">{{ jobStatus.counts_by_category?.xe_may||0 }}</span><span class="rs-label">Xe máy</span></div>
              </div>

              <div v-if="jobStatus.counts_by_violation" class="category-row" style="margin-top:10px">
                <span v-for="(cnt, vtype) in jobStatus.counts_by_violation" :key="vtype" class="badge badge--violation" :class="'viol--' + vtype" style="padding:6px 14px;font-size:0.85rem">
                  {{ violLabel(vtype) }}: {{ cnt }}
                </span>
              </div>
              <div v-if="jobStatus.counts_by_class" class="category-row" style="margin-top:4px">
                <span v-for="(cnt, cls) in jobStatus.counts_by_class" :key="cls" class="badge" :class="classBadge(cls)" style="padding:6px 14px;font-size:0.85rem">
                  {{ classIcon(cls) }} {{ classLabel(cls) }}: {{ cnt }}
                </span>
              </div>
            </div>

            <!-- Cột bên phải: Danh sách phát hiện chi tiết -->
            <div class="results-lists-col">
              <!-- Video Violations -->
              <div v-if="videoViolations.length" class="detections-list violations-list">
                <h3>⚠️ Danh sách vi phạm phát hiện</h3>
                <div class="det-grid">
                  <div v-for="(viol, i) in videoViolations" :key="'vv'+i" class="det-item det-item--violation" style="display: flex; align-items: center; justify-content: space-between;">
                    <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                      <span class="det-idx det-idx--danger">{{ i + 1 }}</span>
                      <span class="badge badge--violation" :class="'viol--' + viol.violation_type">{{ viol.violation_label }}</span>
                      <span class="det-conf mono">{{ (viol.confidence * 100).toFixed(0) }}%</span>
                      <span v-if="viol.plate_text" class="plate-text-lg" style="font-size: 0.85rem; padding: 2px 6px;">{{ viol.plate_text }}</span>
                      <span class="badge badge--primary" style="font-size: 0.75rem;">{{ classLabel(viol.vehicle_class) }}</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 12px;">
                      <img v-if="viol.evidence_path" :src="getEvidenceUrl(viol.evidence_path)" class="plate-thumb" style="height: 48px; width: 80px; object-fit: cover; cursor: pointer; border-radius: 4px;" @click="showVideoEvidence(viol)" title="Xem ảnh bằng chứng" />
                    </div>
                  </div>
                </div>
              </div>

              <!-- Video Vehicles -->
              <div v-if="videoDetections.length" class="detections-list">
                <h3>🚗 Danh sách phương tiện phát hiện</h3>
                <div class="det-grid">
                  <div v-for="(v, i) in videoDetections" :key="'vd'+i" class="det-item" :class="`det-item--${v.category}`" style="display: flex; align-items: center; justify-content: space-between;">
                    <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                      <span class="det-idx">{{ i + 1 }}</span>
                      <span class="badge" :class="classBadge(v.vehicle_class)">{{ classIcon(v.vehicle_class) }} {{ classLabel(v.vehicle_class) }}</span>
                      <span class="det-conf mono">{{ (v.confidence * 100).toFixed(0) }}%</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 12px;">
                      <img v-if="v.evidence_path" :src="getEvidenceUrl(v.evidence_path)" class="plate-thumb" style="height: 48px; width: 80px; object-fit: cover; cursor: pointer; border-radius: 4px;" @click="showVideoEvidence(v)" title="Xem ảnh phương tiện" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Evidence Modal -->
    <div v-if="evidenceModalItem" class="modal-overlay" @click.self="evidenceModalItem = null">
      <div class="modal-content" style="max-width: 700px; width: 90%; background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: var(--radius-xl); overflow: hidden;">
        <div class="modal-header" style="display: flex; justify-content: space-between; align-items: center; padding: 16px; border-bottom: 1px solid var(--border-color);">
          <h3 style="margin: 0; font-size: 1.1rem;">Chi tiết ảnh bằng chứng</h3>
          <button @click="evidenceModalItem = null" style="background: none; border: none; font-size: 1.3rem; cursor: pointer; color: var(--text-muted);">✕</button>
        </div>
        <div class="modal-body" style="padding: 16px; max-height: 70vh; overflow-y: auto;">
          <img :src="getEvidenceUrl(evidenceModalItem.evidence_path)" alt="Evidence" style="width: 100%; border-radius: 8px; display: block;" />
          <div style="margin-top: 15px; display: flex; flex-direction: column; gap: 8px; font-size: 0.9rem; color: var(--text-secondary);">
            <p v-if="evidenceModalItem.violation_label" style="margin: 0;"><strong>Lỗi vi phạm:</strong> <span class="badge badge--violation" :class="'viol--' + evidenceModalItem.violation_type">{{ evidenceModalItem.violation_label }}</span></p>
            <p v-if="evidenceModalItem.vehicle_class" style="margin: 0;"><strong>Loại xe:</strong> {{ classLabel(evidenceModalItem.vehicle_class) }}</p>
            <p v-if="evidenceModalItem.plate_text" style="margin: 0;"><strong>Biển số:</strong> <span class="plate-text-lg" style="font-size: 0.85rem; padding: 2px 6px;">{{ evidenceModalItem.plate_text }}</span></p>
            <p style="margin: 0;"><strong>Thời gian chụp:</strong> {{ formatTime(evidenceModalItem.created_at || evidenceModalItem.timestamp) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import VideoUploader from '@/components/VideoUploader.vue'
import {
  analyzeImage,
  startAnalysis,
  getAnalysisStatus,
  createWebSocket,
  getViolations,
  getDetections,
  getEvidenceUrl
} from '@/api/index.js'

// ── Labels ──────────────────────────────────────────────────────
const CLASS_LABELS = { car: 'Xe con', truck: 'Xe tải', bus: 'Xe bus', motorcycle: 'Xe máy' }
const CLASS_BADGES = { car: 'badge--success', truck: 'badge--warning', bus: 'badge--info', motorcycle: 'badge--danger' }
const CLASS_ICONS  = { car: '🚗', truck: '🚛', bus: '🚌', motorcycle: '🏍️' }
const CAT_LABELS   = { oto: 'Xe ô tô', xe_may: 'Xe máy' }
const VIOL_LABELS  = { no_helmet: 'Không đội MBH', no_seatbelt: 'Không thắt dây', using_phone: 'Dùng ĐT' }
function classLabel(c) { return CLASS_LABELS[c] || c }
function classBadge(c) { return CLASS_BADGES[c] || 'badge--info' }
function classIcon(c) { return CLASS_ICONS[c] || '🚗' }
function catLabel(c) { return CAT_LABELS[c] || c }
function violLabel(v) { return VIOL_LABELS[v] || v }

// ── State ──────────────────────────────────────────────────────
const mode = ref('image')

// Image mode
const imageFile    = ref(null)
const imagePreview = ref(null)
const imageResult  = ref(null)
const imageLoading = ref(false)
const dragOver     = ref(false)

// Video mode
const currentJob = ref(null)
const jobStatus  = ref(null)
const latestFrame= ref(null)
const isStarting = ref(false)
const statusText = ref('Chờ xử lý')
const videoViolations = ref([])
const videoDetections = ref([])
const evidenceModalItem = ref(null)

let pollTimer = null
let ws = null

// ── Image handlers ─────────────────────────────────────────────
function handleImageSelect(e) {
  const f = e.target.files[0]
  if (f) setImageFile(f)
}
function handleImageDrop(e) {
  dragOver.value = false
  const f = e.dataTransfer.files[0]
  if (f && f.type.startsWith('image/')) setImageFile(f)
}
function setImageFile(f) {
  imageFile.value = f
  imagePreview.value = URL.createObjectURL(f)
  imageResult.value = null
}

async function analyzeCurrentImage() {
  if (!imageFile.value) return
  imageLoading.value = true
  try {
    const result = await analyzeImage(imageFile.value)
    imageResult.value = result
  } catch (e) {
    console.error('Analyze error:', e)
    alert('Lỗi phân tích: ' + e.message)
  } finally {
    imageLoading.value = false
  }
}

// ── Video handlers ─────────────────────────────────────────────
function handleVideoUploaded(result) {
  currentJob.value = result
  jobStatus.value = null
  latestFrame.value = null
}

function handleError(err) { console.error('Upload error:', err) }

async function startVideoAnalysis() {
  if (!currentJob.value) return
  isStarting.value = true
  try {
    await startAnalysis(currentJob.value.job_id)
    connectWS()
    startPolling()
  } catch (e) { console.error(e) }
  finally { isStarting.value = false }
}

function connectWS() {
  try {
    ws = createWebSocket('upload')
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'upload_progress' && msg.data?.frame_result?.frame_base64)
        latestFrame.value = msg.data.frame_result.frame_base64
    }
  } catch {}
}

async function loadVideoResults() {
  if (!currentJob.value) return
  try {
    const filename = currentJob.value.filename
    const violRes = await getViolations({ source_file: filename, limit: 100 })
    videoViolations.value = violRes.violations || []

    const detRes = await getDetections({ source_file: filename, limit: 100 })
    videoDetections.value = detRes.detections || []
  } catch (e) {
    console.error('Error loading video results:', e)
  }
}

function showVideoEvidence(item) {
  evidenceModalItem.value = item
}

async function pollStatus() {
  if (!currentJob.value) return
  try {
    const s = await getAnalysisStatus(currentJob.value.job_id)
    jobStatus.value = s
    const map = { pending:'Cho xu ly', processing:'Dang phan tich...', completed:'Hoan tat', error:'Loi' }
    statusText.value = map[s.status] || s.status
    if (s.status === 'completed' || s.status === 'error') {
      stopPolling()
      if (s.status === 'completed') {
        await loadVideoResults()
      }
    }
  } catch {}
}
function startPolling() { pollStatus(); pollTimer = setInterval(pollStatus, 2000) }
function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }

// ── Reset ──────────────────────────────────────────────────────
function resetAll() {
  imageFile.value = null; imagePreview.value = null; imageResult.value = null
  imageLoading.value = false; dragOver.value = false
  currentJob.value = null; jobStatus.value = null; latestFrame.value = null
  videoViolations.value = []
  videoDetections.value = []
  evidenceModalItem.value = null
  statusText.value = 'Chờ xử lý'
  stopPolling()
  if (ws) { ws.close(); ws = null }
}

// ── Helpers ────────────────────────────────────────────────────
function formatSize(b) {
  if (!b) return ''
  return b < 1024*1024 ? `${(b/1024).toFixed(1)} KB` : `${(b/(1024*1024)).toFixed(1)} MB`
}
function formatDuration(s) {
  if (!s) return ''
  return `${Math.floor(s/60)}:${String(Math.round(s%60)).padStart(2,'0')}`
}
function formatTime(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  return d.toLocaleString('vi-VN', { hour12: false })
}

onUnmounted(() => { stopPolling(); if (ws) ws.close() })
</script>

<style scoped>
.upload-page {
  padding: var(--sp-xl); max-width: 960px; margin: 0 auto;
  animation: fadeIn 0.4s ease;
}
.page-header { margin-bottom: var(--sp-lg); }
.page-header h1 { margin: 0; }
.page-header p  { margin: 4px 0 0; color: var(--text-muted); font-size: 0.9rem; }

/* Mode tabs */
.mode-tabs {
  display: flex; gap: var(--sp-sm); margin-bottom: var(--sp-xl);
  background: var(--bg-surface); border-radius: var(--radius-lg);
  padding: 4px; border: 1px solid var(--border-color);
}
.mode-tab {
  flex: 1; padding: 12px; border: none; background: transparent;
  color: var(--text-secondary); font-size: 0.9rem; font-weight: 600;
  border-radius: var(--radius-md); cursor: pointer;
  transition: all var(--transition-fast);
}
.mode-tab:hover { color: var(--text-primary); background: rgba(59,130,246,0.08); }
.mode-tab--active {
  background: rgba(59,130,246,0.15); color: var(--accent-primary);
  box-shadow: 0 1px 4px rgba(59,130,246,0.2);
}

/* Drop zone */
.drop-zone {
  border: 2px dashed var(--border-color); border-radius: var(--radius-lg);
  padding: var(--sp-2xl); text-align: center; cursor: pointer;
  transition: all var(--transition-fast); background: var(--bg-card);
  min-height: 220px; display: flex; align-items: center; justify-content: center;
}
.drop-zone:hover { border-color: var(--accent-primary); background: rgba(59,130,246,0.04); }
.drop-zone--active { border-color: var(--accent-primary); background: rgba(59,130,246,0.08); border-style: solid; }
.drop-content { display: flex; flex-direction: column; align-items: center; gap: var(--sp-sm); }
.drop-icon { font-size: 3rem; opacity: 0.6; }
.drop-title { font-size: 1rem; font-weight: 600; color: var(--text-primary); margin: 0; }
.drop-sub { font-size: 0.82rem; color: var(--text-muted); margin: 0; }

/* Preview in zone */
.preview-in-zone {
  display: flex; align-items: center; gap: var(--sp-lg); width: 100%;
}
.preview-thumb {
  width: 120px; height: 90px; object-fit: cover;
  border-radius: var(--radius-md); border: 1px solid var(--border-color);
}
.preview-info { flex: 1; text-align: left; }
.preview-name { display: block; font-weight: 600; font-size: 0.9rem; color: var(--text-primary); word-break: break-all; }
.preview-size { display: block; font-size: 0.78rem; color: var(--text-muted); margin-top: 2px; }

/* Loading */
.loading-card {
  display: flex; flex-direction: column; align-items: center;
  gap: var(--sp-md); padding: var(--sp-2xl); color: var(--text-muted);
}
.spinner--lg { width: 32px; height: 32px; }

/* Result */
.result-section { display: flex; flex-direction: column; gap: var(--sp-lg); }
.result-header { display: flex; align-items: center; justify-content: space-between; }
.result-header h2 { margin: 0; font-size: 1.2rem; }

.annotated-wrap { border-radius: var(--radius-lg); overflow: hidden; border: 1px solid var(--border-color); }
.annotated-img { width: 100%; display: block; }

/* Result stats */
.result-stats {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: var(--sp-md);
}
.rs-card {
  background: var(--bg-card); border: 1px solid var(--border-color);
  border-radius: var(--radius-lg); padding: 16px; text-align: center;
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  transition: transform 0.2s;
}
.rs-card:hover { transform: translateY(-2px); }
.rs-card--blue       { border-top: 3px solid #3b82f6; }
.rs-card--red        { border-top: 3px solid #ef4444; }
.rs-card--yellow     { border-top: 3px solid #f59e0b; }
.rs-card--car        { border-top: 3px solid #22c55e; }
.rs-card--truck      { border-top: 3px solid #f59e0b; }
.rs-card--bus        { border-top: 3px solid #06b6d4; }
.rs-card--motorcycle { border-top: 3px solid #ef4444; }
.rs-icon  { font-size: 1.5rem; }
.rs-val   { font-size: 1.8rem; font-weight: 800; color: var(--text-primary); }
.rs-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; }

/* Category row */
.category-row { display: flex; gap: var(--sp-sm); flex-wrap: wrap; }
.cat-chip {
  display: flex; align-items: center; gap: var(--sp-sm);
  padding: 8px 16px; border-radius: var(--radius-full);
  font-size: 0.85rem; font-weight: 600;
}
.cat-chip--oto    { background: rgba(34,197,94,0.12);  color: #22c55e; }
.cat-chip--xe_may { background: rgba(239,68,68,0.12);  color: #ef4444; }
.cat-chip--xe_dap { background: rgba(139,92,246,0.12); color: #8b5cf6; }
.cat-count { font-weight: 800; }

/* Detection list */
.detections-list {
  background: var(--bg-card); border: 1px solid var(--border-color);
  border-radius: var(--radius-lg); padding: var(--sp-lg);
}
.detections-list h3 { margin: 0 0 var(--sp-md); font-size: 0.95rem; color: var(--text-secondary); }
.det-grid { display: flex; flex-direction: column; gap: var(--sp-sm); }
.det-item {
  display: flex; align-items: center; gap: var(--sp-md);
  padding: 8px 12px; border-radius: var(--radius-md);
  background: var(--bg-surface); border: 1px solid var(--border-color);
  font-size: 0.85rem;
}
.det-item--oto    { border-left: 3px solid #22c55e; }
.det-item--xe_may { border-left: 3px solid #ef4444; }
.det-item--xe_dap { border-left: 3px solid #8b5cf6; }
.det-idx  { width: 24px; height: 24px; background: rgba(59,130,246,0.15); color: #60a5fa; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.72rem; font-weight: 700; flex-shrink: 0; }
.det-conf { margin-left: auto; font-size: 0.78rem; color: var(--text-muted); }
.det-cat  { font-size: 0.72rem; color: var(--text-muted); }
.mono { font-family: var(--font-mono); }

/* Job card */
.job-card { background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: 20px; margin-bottom: 20px; }
.job-card__header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.job-info h3 { margin: 0 0 4px; font-size: 1rem; }
.job-meta { font-size: 0.8rem; color: var(--text-muted); }
.job-status { padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
.status--pending    { background: rgba(234,179,8,0.15);   color: #eab308; }
.status--processing { background: rgba(59,130,246,0.15);  color: #3b82f6; }
.status--completed  { background: rgba(34,197,94,0.15);   color: #22c55e; }
.status--error      { background: rgba(239,68,68,0.15);   color: #ef4444; }
.job-progress { margin-bottom: 16px; }
.progress-bar { background: rgba(59,130,246,0.1); border-radius: 8px; height: 12px; overflow: hidden; margin-bottom: 8px; }
.progress-bar__fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #06b6d4); border-radius: 8px; transition: width 0.5s ease; }
.progress-text { display: flex; justify-content: space-between; font-size: 0.78rem; color: var(--text-muted); }

.preview-section { margin-bottom: 20px; }
.preview-section h3 { font-size: 1rem; margin: 0 0 12px; }

/* Violation items */
.violations-list { border-left: 3px solid #ef4444; }
.det-item--violation { border-left: 3px solid #ef4444; }
.det-idx--danger { background: rgba(239,68,68,0.15); color: #ef4444; }
.badge--violation {
  padding: 4px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 600;
}
.viol--no_helmet { background: rgba(245,158,11,0.15); color: #f59e0b; }
.viol--no_seatbelt { background: rgba(239,68,68,0.15); color: #ef4444; }
.viol--using_phone { background: rgba(168,85,247,0.15); color: #a855f7; }

/* Plate items */
.plates-list { border-left: 3px solid #f59e0b; }
.det-item--plate { border-left: 3px solid #f59e0b; }
.det-idx--plate { background: rgba(245,158,11,0.15); color: #f59e0b; }
.plate-text-lg {
  font-family: 'Courier New', monospace;
  font-weight: 700; font-size: 1rem;
  background: rgba(59,130,246,0.1);
  padding: 4px 10px; border-radius: var(--radius-sm);
  color: var(--accent-primary);
}
.plate-thumb {
  height: 36px; border-radius: 4px; margin-left: auto;
  border: 1px solid var(--border-color);
}

/* Modal style */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

/* Split Layout for Results */
.results-split-layout {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 24px;
  align-items: start;
  margin-top: 16px;
}
.results-visuals-col {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.results-lists-col {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (max-width: 992px) {
  .results-split-layout {
    grid-template-columns: 1fr;
  }
}
</style>
