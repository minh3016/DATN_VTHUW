<template>
  <div class="page-container">
    <div class="page-title-section">
      <div>
        <h1>Upload & Phân tích</h1>
        <p class="page-title-sub">Tải lên ảnh hoặc video để phát hiện vi phạm giao thông bằng AI YOLOv8n</p>
      </div>
    </div>

    <!-- Mode selector -->
    <div class="mode-tabs">
      <button class="mode-tab" :class="{ 'mode-tab--active': mode === 'image' }" @click="resetAll(); mode = 'image'">
        <LucideIcon name="image" :size="16" />
        Phân tích ảnh
      </button>
      <button class="mode-tab" :class="{ 'mode-tab--active': mode === 'video' }" @click="resetAll(); mode = 'video'">
        <LucideIcon name="film" :size="16" />
        Phân tích video
      </button>
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
        <input ref="imageInput" type="file" accept="image/jpeg,image/png,image/bmp,image/webp" style="display:none" @change="handleImageSelect" />

        <div v-if="imagePreview" class="preview-in-zone">
          <img :src="imagePreview" alt="preview" class="preview-thumb" />
          <div class="preview-info">
            <span class="preview-name">{{ imageFile?.name }}</span>
            <span class="preview-size">{{ formatSize(imageFile?.size) }}</span>
          </div>
          <button class="btn btn--primary" @click.stop="analyzeCurrentImage" :disabled="imageLoading">
            <span v-if="imageLoading" class="spinner"></span>
            <template v-else>
              <LucideIcon name="scan" :size="16" />
              Phân tích
            </template>
          </button>
        </div>

        <div v-else class="drop-content">
          <div class="drop-icon-wrap">
            <LucideIcon name="image-plus" :size="40" />
          </div>
          <p class="drop-title">Kéo thả ảnh vào đây</p>
          <p class="drop-sub">hoặc nhấn để chọn file · JPG, PNG, BMP, WebP · Tối đa 20MB</p>
        </div>
      </div>

      <!-- Upload progress -->
      <div v-if="imageLoading" class="loading-card">
        <span class="spinner spinner--lg"></span>
        <p>Đang phân tích ảnh bằng 4 model AI...</p>
      </div>

      <!-- Image Result -->
      <div v-if="imageResult" class="result-section animate-fade-in">
        <div class="result-header">
          <h2>Kết quả phân tích hình ảnh</h2>
          <button class="btn btn--ghost" @click="resetAll">
            <LucideIcon name="plus" :size="16" />
            Upload ảnh mới
          </button>
        </div>

        <div class="results-split-layout">
          <div class="results-visuals-col">
            <!-- Annotated image -->
            <div class="annotated-wrap" @click="showImageLightbox = true" title="Nhấn để phóng to">
              <img v-if="imageResult.frame_base64" :src="`data:image/jpeg;base64,${imageResult.frame_base64}`" alt="Annotated" class="annotated-img" />
            </div>

            <!-- Stats cards -->
            <div class="result-stats">
              <div class="rs-card rs-card--blue">
                <LucideIcon name="car" :size="20" />
                <span class="rs-val">{{ imageResult.vehicle_count || 0 }}</span>
                <span class="rs-label">Phương tiện</span>
              </div>
              <div class="rs-card rs-card--red">
                <LucideIcon name="alert-triangle" :size="20" />
                <span class="rs-val">{{ imageResult.violation_count || 0 }}</span>
                <span class="rs-label">Vi phạm</span>
              </div>
              <div class="rs-card rs-card--yellow">
                <LucideIcon name="credit-card" :size="20" />
                <span class="rs-val">{{ imageResult.plate_count || 0 }}</span>
                <span class="rs-label">Biển số</span>
              </div>
            </div>

            <!-- Category breakdown -->
            <div v-if="imageResult.counts_by_category" class="category-row">
              <div v-for="(cnt, cat) in imageResult.counts_by_category" :key="cat" class="cat-chip" :class="`cat-chip--${cat}`">
                <span class="cat-name">{{ catLabel(cat) }}</span>
                <span class="cat-count">{{ cnt }}</span>
              </div>
            </div>
          </div>

          <div class="results-lists-col">
            <!-- Violations list -->
            <div v-if="imageResult.violations?.length" class="detections-list violations-list">
              <h3><LucideIcon name="alert-triangle" :size="16" /> Vi phạm giao thông</h3>
              <div class="det-grid">
                <div v-for="(viol, i) in imageResult.violations" :key="'v'+i" class="det-item det-item--violation">
                  <div class="det-item__left">
                    <span class="det-idx det-idx--danger">{{ i + 1 }}</span>
                    <span class="badge badge--violation" :class="'viol--' + viol.violation_type">{{ viol.violation_label }}</span>
                    <span class="conf-bar__label">{{ (viol.bbox.conf * 100).toFixed(0) }}%</span>
                  </div>
                  <span v-if="viol.plate_text" class="plate-text" style="font-size:0.8rem">{{ viol.plate_text }}</span>
                </div>
              </div>
            </div>

            <!-- Plates list -->
            <div v-if="imageResult.plates?.length" class="detections-list plates-list">
              <h3><LucideIcon name="credit-card" :size="16" /> Biển số xe nhận diện</h3>
              <div class="det-grid">
                <div v-for="(plate, i) in imageResult.plates" :key="'p'+i" class="det-item det-item--plate">
                  <span class="det-idx det-idx--plate">{{ i + 1 }}</span>
                  <div class="flex flex-col gap-1" style="flex:1">
                    <div class="flex items-center gap-2">
                      <span class="plate-text" :class="{ 'text-danger': !plate.is_valid_plate }">{{ plate.normalized_text || plate.plate_text || 'Không nhận dạng' }}</span>
                      <span v-if="plate.is_valid_plate" class="badge badge--success" style="font-size:0.7rem;padding:2px 6px">Hợp lệ</span>
                      <span v-else class="badge badge--danger" style="font-size:0.7rem;padding:2px 6px" :title="'Raw OCR: ' + plate.plate_text">Không hợp lệ</span>
                    </div>
                    <span v-if="plate.province_name" style="font-size:0.75rem;color:var(--text-muted)">{{ plate.province_name }}</span>
                  </div>
                  <span class="conf-bar__label">{{ plate.avg_ocr_confidence ? (plate.avg_ocr_confidence * 100).toFixed(0) + '%' : '—' }}</span>
                  <img v-if="plate.plate_image_base64" :src="'data:image/jpeg;base64,' + plate.plate_image_base64" class="plate-thumb-img" style="cursor:zoom-in" alt="plate" @click="showPlateEvidence(plate)" title="Click để xem chi tiết ký tự" />
                </div>
              </div>
            </div>

            <!-- Vehicle detection list -->
            <div v-if="imageResult.vehicles?.length" class="detections-list">
              <h3><LucideIcon name="car" :size="16" /> Phương tiện trong ROI</h3>
              <div class="det-grid">
                <div v-for="(v, i) in imageResult.vehicles" :key="i" class="det-item" :class="`det-item--${v.category}`">
                  <span class="det-idx">{{ i + 1 }}</span>
                  <span class="badge" :class="classBadge(v.class_name)">{{ classLabel(v.class_name) }}</span>
                  <span class="conf-bar__label">{{ (v.bbox.conf * 100).toFixed(0) }}%</span>
                  <span class="det-cat">{{ catLabel(v.category) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ============ VIDEO MODE ============ -->
    <div v-if="mode === 'video'" class="mode-content">
      <div v-if="!currentJob" class="upload-section">
        <VideoUploader @uploaded="handleVideoUploaded" @error="handleError" />
      </div>

      <div v-if="currentJob" class="analysis-section">
        <div class="job-card">
          <div class="job-card__header">
            <div class="job-info">
              <h3><LucideIcon name="film" :size="18" /> {{ currentJob.filename }}</h3>
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
              <span class="progress-counts">
                <LucideIcon name="car" :size="13" /> {{ jobStatus.vehicles_detected||0 }}
                <LucideIcon name="alert-triangle" :size="13" /> {{ jobStatus.violations_detected||0 }}
                <LucideIcon name="credit-card" :size="13" /> {{ jobStatus.plates_detected||0 }}
              </span>
            </div>
          </div>

          <button v-if="!jobStatus || jobStatus.status === 'pending'" class="btn btn--primary btn--lg" style="width:100%" @click="startVideoAnalysis" :disabled="isStarting">
            <LucideIcon name="play" :size="18" />
            {{ isStarting ? 'Đang khởi tạo...' : 'Bắt đầu phân tích' }}
          </button>
        </div>

        <!-- Live preview -->
        <div v-if="latestFrame" class="preview-section">
          <h3>Xem trước xử lý</h3>
          <img :src="'data:image/jpeg;base64,' + latestFrame" alt="Preview" class="annotated-img" />
        </div>

        <!-- Video results -->
        <div v-if="jobStatus?.status === 'completed'" class="result-section animate-fade-in">
          <div class="result-header">
            <h2>Kết quả phân tích video</h2>
            <button class="btn btn--ghost" @click="resetAll">
              <LucideIcon name="plus" :size="16" />
              Upload video mới
            </button>
          </div>

          <div class="results-split-layout">
            <div class="results-visuals-col">
              <div class="result-stats">
                <div class="rs-card rs-card--blue"><LucideIcon name="car" :size="20" /><span class="rs-val">{{ jobStatus.vehicles_detected }}</span><span class="rs-label">Phương tiện</span></div>
                <div class="rs-card rs-card--red"><LucideIcon name="alert-triangle" :size="20" /><span class="rs-val">{{ jobStatus.violations_detected || 0 }}</span><span class="rs-label">Vi phạm</span></div>
                <div class="rs-card rs-card--yellow"><LucideIcon name="credit-card" :size="20" /><span class="rs-val">{{ jobStatus.plates_detected || 0 }}</span><span class="rs-label">Biển số</span></div>
              </div>

              <div v-if="jobStatus.counts_by_violation" class="category-row">
                <span v-for="(cnt, vtype) in jobStatus.counts_by_violation" :key="vtype" class="badge badge--violation" :class="'viol--' + vtype" style="padding:6px 14px;font-size:0.85rem">
                  {{ violLabel(vtype) }}: {{ cnt }}
                </span>
              </div>
              <div v-if="jobStatus.counts_by_class" class="category-row">
                <span v-for="(cnt, cls) in jobStatus.counts_by_class" :key="cls" class="badge" :class="classBadge(cls)" style="padding:6px 14px;font-size:0.85rem">
                  {{ classLabel(cls) }}: {{ cnt }}
                </span>
              </div>
            </div>

            <div class="results-lists-col">
              <!-- Video Violations -->
              <div v-if="videoViolations.length" class="detections-list violations-list">
                <h3><LucideIcon name="alert-triangle" :size="16" /> Vi phạm phát hiện</h3>
                <div class="det-grid">
                  <div v-for="(viol, i) in videoViolations" :key="'vv'+i" class="det-item det-item--violation">
                    <div class="det-item__left">
                      <span class="det-idx det-idx--danger">{{ i + 1 }}</span>
                      <span class="badge badge--violation" :class="'viol--' + viol.violation_type">{{ viol.violation_label }}</span>
                      <span class="conf-bar__label">{{ (viol.confidence * 100).toFixed(0) }}%</span>
                      <span v-if="viol.plate_text" class="plate-text" style="font-size:0.8rem">{{ viol.plate_text }}</span>
                    </div>
                    <img v-if="viol.evidence_path" :src="getEvidenceUrl(viol.evidence_path)" class="evidence-thumb" @click="showVideoEvidence(viol)" title="Xem bằng chứng" />
                  </div>
                </div>
              </div>

              <!-- Video Vehicles -->
              <div v-if="videoDetections.length" class="detections-list">
                <h3><LucideIcon name="car" :size="16" /> Phương tiện phát hiện</h3>
                <div class="det-grid">
                  <div v-for="(v, i) in videoDetections" :key="'vd'+i" class="det-item" :class="`det-item--${v.category}`">
                    <div class="det-item__left">
                      <span class="det-idx">{{ i + 1 }}</span>
                      <span class="badge" :class="classBadge(v.vehicle_class)">{{ classLabel(v.vehicle_class) }}</span>
                      <span class="conf-bar__label">{{ (v.confidence * 100).toFixed(0) }}%</span>
                    </div>
                    <img v-if="v.evidence_path" :src="getEvidenceUrl(v.evidence_path)" class="evidence-thumb" @click="showVideoEvidence(v)" title="Xem ảnh" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Image Lightbox -->
    <div v-if="showImageLightbox && imageResult?.frame_base64" class="modal-overlay" @click.self="showImageLightbox = false">
      <div class="lightbox-content">
        <img :src="`data:image/jpeg;base64,${imageResult.frame_base64}`" alt="Full size" />
        <button class="modal-close" @click="showImageLightbox = false">✕</button>
      </div>
    </div>

    <!-- Evidence Modal -->
    <div v-if="evidenceModalItem" class="modal-overlay" @click.self="evidenceModalItem = null">
      <div class="modal-content" style="max-width:720px">
        <div class="modal-header">
          <h3>Chi tiết bằng chứng</h3>
          <button @click="evidenceModalItem = null" class="modal-close">✕</button>
        </div>
        <div class="modal-body">
          <img :src="getEvidenceUrl(evidenceModalItem.evidence_path)" alt="Evidence" style="width:100%;border-radius:var(--radius-md);display:block" />
          <div class="evidence-details">
            <p v-if="evidenceModalItem.violation_label"><strong>Lỗi:</strong> <span class="badge badge--violation" :class="'viol--' + evidenceModalItem.violation_type">{{ evidenceModalItem.violation_label }}</span></p>
            <p v-if="evidenceModalItem.vehicle_class"><strong>Loại xe:</strong> {{ classLabel(evidenceModalItem.vehicle_class) }}</p>
            <p v-if="evidenceModalItem.plate_text"><strong>Biển số:</strong> <span class="plate-text">{{ evidenceModalItem.plate_text }}</span></p>
            <p><strong>Thời gian:</strong> {{ formatTime(evidenceModalItem.created_at || evidenceModalItem.timestamp) }}</p>
          </div>
        </div>
      </div>
    </div>
    <!-- Plate Evidence Modal -->
    <div v-if="plateEvidenceModalItem" class="modal-overlay" @click.self="plateEvidenceModalItem = null">
      <div class="modal-content" style="max-width:500px">
        <div class="modal-header">
          <h3>Chi tiết nhận diện biển số</h3>
          <button @click="plateEvidenceModalItem = null" class="modal-close">✕</button>
        </div>
        <div class="modal-body text-center">
          <img :src="'data:image/jpeg;base64,' + plateEvidenceModalItem.plate_image_base64" alt="Plate Crop" style="max-height:150px;width:auto;margin:0 auto;border-radius:var(--radius-md);display:block" />
          <div class="evidence-details mt-4 text-left" style="margin-top: 16px;">
            <p><strong>Biển số đã chuẩn hóa:</strong> <span class="plate-text">{{ plateEvidenceModalItem.normalized_text || plateEvidenceModalItem.plate_text }}</span></p>
            <p><strong>OCR Gốc:</strong> <span style="font-family: monospace;">{{ plateEvidenceModalItem.plate_text }}</span></p>
            <p><strong>Trạng thái:</strong> 
              <span v-if="plateEvidenceModalItem.is_valid_plate" class="text-success font-bold">Hợp lệ</span>
              <span v-else class="text-danger font-bold">Không hợp lệ</span>
            </p>
            <p v-if="plateEvidenceModalItem.province_name"><strong>Tỉnh/TP:</strong> {{ plateEvidenceModalItem.province_name }}</p>
            <p><strong>Độ tin cậy:</strong> {{ plateEvidenceModalItem.avg_ocr_confidence ? (plateEvidenceModalItem.avg_ocr_confidence * 100).toFixed(1) + '%' : '—' }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import VideoUploader from '@/components/VideoUploader.vue'
import LucideIcon from '@/components/LucideIcon.vue'
import {
  analyzeImage, startAnalysis, getAnalysisStatus,
  createWebSocket, getViolations, getDetections, getEvidenceUrl
} from '@/api/index.js'

const CLASS_LABELS = { car: 'Xe con', truck: 'Xe tải', bus: 'Xe bus', motorcycle: 'Xe máy' }
const CLASS_BADGES = { car: 'badge--success', truck: 'badge--warning', bus: 'badge--info', motorcycle: 'badge--danger' }
const CAT_LABELS = { oto: 'Xe ô tô', xe_may: 'Xe máy' }
const VIOL_LABELS = { no_helmet: 'Không đội MBH', no_seatbelt: 'Không thắt dây', using_phone: 'Dùng ĐT' }
function classLabel(c) { return CLASS_LABELS[c] || c }
function classBadge(c) { return CLASS_BADGES[c] || 'badge--info' }
function catLabel(c) { return CAT_LABELS[c] || c }
function violLabel(v) { return VIOL_LABELS[v] || v }

const mode = ref('image')
const imageFile = ref(null)
const imagePreview = ref(null)
const imageResult = ref(null)
const imageLoading = ref(false)
const dragOver = ref(false)
const showImageLightbox = ref(false)

const currentJob = ref(null)
const jobStatus = ref(null)
const latestFrame = ref(null)
const isStarting = ref(false)
const statusText = ref('Chờ xử lý')
const videoViolations = ref([])
const videoDetections = ref([])
const evidenceModalItem = ref(null)
const plateEvidenceModalItem = ref(null)

let pollTimer = null
let ws = null

function handleImageSelect(e) { const f = e.target.files[0]; if (f) setImageFile(f) }
function handleImageDrop(e) { dragOver.value = false; const f = e.dataTransfer.files[0]; if (f && f.type.startsWith('image/')) setImageFile(f) }
function setImageFile(f) { imageFile.value = f; imagePreview.value = URL.createObjectURL(f); imageResult.value = null }

async function analyzeCurrentImage() {
  if (!imageFile.value) return
  imageLoading.value = true
  try { imageResult.value = await analyzeImage(imageFile.value) }
  catch (e) { alert('Lỗi phân tích: ' + e.message) }
  finally { imageLoading.value = false }
}

function handleVideoUploaded(result) { currentJob.value = result; jobStatus.value = null; latestFrame.value = null }
function handleError(err) { console.error('Upload error:', err) }

async function startVideoAnalysis() {
  if (!currentJob.value) return
  isStarting.value = true
  try { await startAnalysis(currentJob.value.job_id); connectWS(); startPolling() }
  catch (e) { console.error(e) }
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
  } catch (e) { console.error('Error loading video results:', e) }
}

function showVideoEvidence(item) { evidenceModalItem.value = item }

async function pollStatus() {
  if (!currentJob.value) return
  try {
    const s = await getAnalysisStatus(currentJob.value.job_id)
    jobStatus.value = s
    const map = { pending:'Chờ xử lý', processing:'Đang phân tích...', completed:'Hoàn tất', error:'Lỗi' }
    statusText.value = map[s.status] || s.status
    if (s.status === 'completed' || s.status === 'error') {
      stopPolling()
      if (s.status === 'completed') await loadVideoResults()
    }
  } catch {}
}
function startPolling() { pollStatus(); pollTimer = setInterval(pollStatus, 2000) }
function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }

function resetAll() {
  imageFile.value = null; imagePreview.value = null; imageResult.value = null
  imageLoading.value = false; dragOver.value = false; showImageLightbox.value = false
  currentJob.value = null; jobStatus.value = null; latestFrame.value = null
  videoViolations.value = []; videoDetections.value = []; evidenceModalItem.value = null; plateEvidenceModalItem.value = null
  statusText.value = 'Chờ xử lý'; stopPolling()
  if (ws) { ws.close(); ws = null }
}

function formatSize(b) { if (!b) return ''; return b < 1024*1024 ? `${(b/1024).toFixed(1)} KB` : `${(b/(1024*1024)).toFixed(1)} MB` }
function formatDuration(s) { if (!s) return ''; return `${Math.floor(s/60)}:${String(Math.round(s%60)).padStart(2,'0')}` }
function formatTime(ts) { if (!ts) return '—'; return new Date(ts).toLocaleString('vi-VN', { hour12: false }) }

function showPlateEvidence(plate) { plateEvidenceModalItem.value = plate }

onUnmounted(() => { stopPolling(); if (ws) ws.close() })
</script>

<style scoped>
.mode-tabs {
  display: flex; gap: 4px;
  background: var(--bg-surface); border-radius: var(--radius-lg);
  padding: 4px; border: 1px solid var(--border-color);
  margin-bottom: var(--sp-xl); max-width: 400px;
}
.mode-tab {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 10px 16px; border: none; background: transparent;
  color: var(--text-secondary); font-size: 0.875rem; font-weight: 600;
  border-radius: var(--radius-md); cursor: pointer; transition: all var(--transition-fast);
}
.mode-tab:hover { color: var(--text-primary); background: rgba(37,99,235,0.06); }
.mode-tab--active { background: rgba(37,99,235,0.12); color: var(--accent-primary); }

.drop-zone {
  border: 2px dashed var(--border-color); border-radius: var(--radius-lg);
  padding: var(--sp-2xl); text-align: center; cursor: pointer;
  transition: all var(--transition-fast); background: var(--bg-card);
  min-height: 220px; display: flex; align-items: center; justify-content: center;
}
.drop-zone:hover { border-color: var(--accent-primary); background: rgba(37,99,235,0.03); }
.drop-zone--active { border-color: var(--accent-primary); background: rgba(37,99,235,0.06); border-style: solid; }
.drop-content { display: flex; flex-direction: column; align-items: center; gap: var(--sp-sm); }
.drop-icon-wrap { color: var(--text-muted); opacity: 0.5; margin-bottom: 8px; }
.drop-title { font-size: 1rem; font-weight: 600; color: var(--text-primary); margin: 0; }
.drop-sub { font-size: 0.82rem; color: var(--text-muted); margin: 0; }

.preview-in-zone { display: flex; align-items: center; gap: var(--sp-lg); width: 100%; }
.preview-thumb { width: 160px; height: 110px; object-fit: cover; border-radius: var(--radius-md); border: 1px solid var(--border-color); }
.preview-info { flex: 1; text-align: left; }
.preview-name { display: block; font-weight: 600; font-size: 0.9rem; color: var(--text-primary); word-break: break-all; }
.preview-size { display: block; font-size: 0.78rem; color: var(--text-muted); margin-top: 4px; }

.loading-card { display: flex; flex-direction: column; align-items: center; gap: var(--sp-md); padding: var(--sp-2xl); color: var(--text-muted); }

.result-section { display: flex; flex-direction: column; gap: var(--sp-lg); }
.result-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--sp-sm); }
.result-header h2 { margin: 0; font-size: 1.2rem; }

.annotated-wrap { border-radius: var(--radius-lg); overflow: hidden; border: 1px solid var(--border-color); cursor: zoom-in; }
.annotated-img { width: 100%; display: block; }

.result-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: var(--sp-md); }
.rs-card {
  background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg);
  padding: 16px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 6px;
  transition: transform var(--transition-fast);
}
.rs-card:hover { transform: translateY(-2px); }
.rs-card--blue   { border-top: 3px solid var(--accent-primary); }
.rs-card--red    { border-top: 3px solid var(--accent-danger); }
.rs-card--yellow { border-top: 3px solid var(--accent-warning); }
.rs-val  { font-size: 1.75rem; font-weight: 800; color: var(--text-primary); }
.rs-label { font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }

.category-row { display: flex; gap: var(--sp-sm); flex-wrap: wrap; }
.cat-chip { display: flex; align-items: center; gap: var(--sp-sm); padding: 8px 16px; border-radius: var(--radius-full); font-size: 0.85rem; font-weight: 600; }
.cat-chip--oto    { background: rgba(34,197,94,0.1);  color: #22c55e; }
.cat-chip--xe_may { background: rgba(239,68,68,0.1);  color: #ef4444; }
.cat-count { font-weight: 800; }

.detections-list { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: var(--sp-lg); }
.detections-list h3 { margin: 0 0 var(--sp-md); font-size: 0.9rem; color: var(--text-secondary); display: flex; align-items: center; gap: 8px; }
.det-grid { display: flex; flex-direction: column; gap: 6px; }
.det-item {
  display: flex; align-items: center; justify-content: space-between; gap: var(--sp-sm);
  padding: 8px 12px; border-radius: var(--radius-md); background: var(--bg-inset); border: 1px solid var(--border-color); font-size: 0.85rem;
}
.det-item__left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.det-item--oto    { border-left: 3px solid #22c55e; }
.det-item--xe_may { border-left: 3px solid #ef4444; }
.det-item--violation { border-left: 3px solid #ef4444; }
.det-item--plate { border-left: 3px solid #f59e0b; }
.violations-list { border-left: 3px solid #ef4444; }
.plates-list { border-left: 3px solid #f59e0b; }

.det-idx { width: 24px; height: 24px; background: rgba(37,99,235,0.12); color: #60a5fa; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.72rem; font-weight: 700; flex-shrink: 0; }
.det-idx--danger { background: rgba(239,68,68,0.12); color: #f87171; }
.det-idx--plate  { background: rgba(245,158,11,0.12); color: #fbbf24; }
.det-cat { font-size: 0.72rem; color: var(--text-muted); margin-left: auto; }

.plate-thumb-img { height: 32px; border-radius: 4px; margin-left: auto; border: 1px solid var(--border-color); }

.results-split-layout { display: grid; grid-template-columns: 1.2fr 1fr; gap: 24px; align-items: start; margin-top: 16px; }
.results-visuals-col, .results-lists-col { display: flex; flex-direction: column; gap: 16px; }
@media (max-width: 992px) { .results-split-layout { grid-template-columns: 1fr; } }

.job-card { background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: 20px; margin-bottom: 20px; }
.job-card__header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.job-info h3 { margin: 0 0 4px; font-size: 1rem; display: flex; align-items: center; gap: 8px; }
.job-meta { font-size: 0.8rem; color: var(--text-muted); }
.job-status { padding: 4px 12px; border-radius: var(--radius-full); font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
.status--pending    { background: rgba(234,179,8,0.12);  color: #eab308; }
.status--processing { background: rgba(37,99,235,0.12);  color: #60a5fa; }
.status--completed  { background: rgba(16,185,129,0.12); color: #34d399; }
.status--error      { background: rgba(239,68,68,0.12);  color: #f87171; }
.job-progress { margin-bottom: 16px; }
.progress-text { display: flex; justify-content: space-between; font-size: 0.78rem; color: var(--text-muted); margin-top: 8px; }
.progress-counts { display: flex; align-items: center; gap: 8px; }

.preview-section { margin-bottom: 20px; }
.preview-section h3 { font-size: 1rem; margin: 0 0 12px; }

.evidence-details { margin-top: 16px; display: flex; flex-direction: column; gap: 8px; }
.evidence-details p { margin: 0; font-size: 0.9rem; color: var(--text-secondary); }
.evidence-details strong { color: var(--text-primary); }

.lightbox-content { position: relative; max-width: 95vw; max-height: 95vh; }
.lightbox-content img { max-width: 100%; max-height: 90vh; border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); display: block; }
.lightbox-content .modal-close { position: absolute; top: -12px; right: -12px; }
</style>
