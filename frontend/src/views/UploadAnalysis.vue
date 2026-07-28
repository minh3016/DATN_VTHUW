<template>
  <div class="page-container">
    <div class="page-title-section">
      <div>
        <h1>Phân tích Dữ liệu AI</h1>
        <p class="page-title-sub">Tải lên video hoặc ảnh tĩnh để phát hiện vi phạm giao thông bằng AI YOLOv8n</p>
      </div>
    </div>

    <!-- Mode Tabs -->
    <div class="analysis-mode-tabs">
      <button
        class="mode-tab"
        :class="{ 'mode-tab--active': activeMode === 'video' }"
        @click="activeMode = 'video'"
      >
        <LucideIcon name="film" :size="18" /> Phân tích Video
      </button>
      <button
        class="mode-tab"
        :class="{ 'mode-tab--active': activeMode === 'image' }"
        @click="activeMode = 'image'"
      >
        <LucideIcon name="image" :size="18" /> Phân tích Ảnh
      </button>
    </div>

    <!-- Mode 1: Video Analysis -->
    <div v-if="activeMode === 'video'" class="mode-content">
      <!-- Upload zone + Settings -->
      <div class="upload-settings-row">
        <!-- Drop zone -->
        <div
          class="drop-zone"
          :class="{ 'drop-zone--active': dragOver }"
          @dragover.prevent="dragOver = true"
          @dragleave="dragOver = false"
          @drop.prevent="handleDrop"
          @click="$refs.fileInput.click()"
        >
          <input ref="fileInput" type="file" accept="video/mp4,video/avi,video/x-msvideo,video/quicktime,video/x-matroska" multiple style="display:none" @change="handleFileSelect" />
          <div class="drop-content">
            <div class="drop-icon-wrap"><LucideIcon name="film" :size="40" /></div>
            <p class="drop-title">Kéo thả video vào đây</p>
            <p class="drop-sub">hoặc nhấn để chọn file · MP4, AVI, MOV, MKV · Tối đa 10 phút · 500MB · Chọn nhiều file</p>
          </div>
        </div>

        <!-- Speed slider -->
        <div class="speed-panel">
          <h3><LucideIcon name="gauge" :size="16" /> Tốc độ phân tích</h3>
          <div class="speed-slider-wrap">
            <input
              type="range"
              class="speed-slider"
              :min="0"
              :max="speedSteps.length - 1"
              v-model.number="speedIndex"
            />
            <div class="speed-labels">
              <span v-for="(s, i) in speedSteps" :key="s" class="speed-label" :class="{ 'speed-label--active': i === speedIndex }">
                x{{ s }}
              </span>
            </div>
          </div>
          <div class="speed-info">
            <span class="speed-badge">x{{ currentSpeed }}</span>
            <span class="speed-desc" v-if="currentSpeed === 1">Phân tích tất cả frame (chính xác nhất)</span>
            <span class="speed-desc" v-else>Bỏ qua {{ currentSpeed - 1 }} frame, phân tích mỗi frame thứ {{ currentSpeed }} (nhanh gấp ~{{ currentSpeed }} lần)</span>
          </div>
          <div class="speed-note">
            <LucideIcon name="info" :size="13" />
            Tốc độ áp dụng cho video <strong>chưa bắt đầu</strong> phân tích. Tối đa 2 video phân tích đồng thời.
          </div>
        </div>
      </div>

      <!-- Video List -->
      <div v-if="videoJobs.length" class="video-list-section">
        <div class="video-list-header">
          <h2><LucideIcon name="list-video" :size="18" /> Danh sách video ({{ videoJobs.length }})</h2>
          <button v-if="videoJobs.length > 1" class="btn btn--ghost btn--sm" @click="clearAllCompleted">
            <LucideIcon name="trash-2" :size="14" /> Xóa video đã hoàn tất
          </button>
        </div>

        <div class="video-cards">
          <div v-for="(job, idx) in videoJobs" :key="job.id" class="video-card" :class="`video-card--${job.state}`">
            <!-- Card Header -->
            <div class="vc-header">
              <div class="vc-info">
                <div class="vc-title-row">
                  <span class="vc-idx">{{ idx + 1 }}</span>
                  <LucideIcon name="file-video" :size="18" />
                  <span class="vc-name">{{ job.filename }}</span>
                </div>
                <div class="vc-meta">
                  <span>{{ formatSize(job.file_size) }}</span>
                  <span v-if="job.duration_sec"> · {{ formatDuration(job.duration_sec) }}</span>
                  <span v-if="job.frame_skip > 1"> · Tua x{{ job.frame_skip }}</span>
                </div>
              </div>
              <div class="vc-status-actions">
                <span class="vc-status-badge" :class="`status--${job.state}`">{{ stateLabel(job.state) }}</span>
                <button v-if="job.state === 'pending' || job.state === 'uploaded'" class="btn--icon btn--icon-danger" @click="removeJob(idx)" title="Xóa">
                  <LucideIcon name="x" :size="16" />
                </button>
              </div>
            </div>

            <!-- Upload progress -->
            <div v-if="job.state === 'uploading'" class="vc-progress-section">
              <div class="progress-bar"><div class="progress-bar__fill progress-bar__fill--upload" :style="{ width: job.uploadProgress + '%' }"></div></div>
              <span class="vc-progress-text">Đang upload: {{ job.uploadProgress }}%</span>
            </div>

            <!-- Analysis progress + controls -->
            <div v-if="job.state === 'processing' || job.state === 'paused'" class="vc-progress-section">
              <div class="vc-controls-row">
                <button class="btn--icon-control" @click="togglePause(job)" :title="job.paused ? 'Tiếp tục' : 'Tạm dừng'">
                  <LucideIcon :name="job.paused ? 'play' : 'pause'" :size="16" />
                </button>
                <div class="progress-bar" style="flex:1"><div class="progress-bar__fill" :style="{ width: Math.round((job.progress||0)*100) + '%' }"></div></div>
                <span class="vc-pct">{{ Math.round((job.progress||0)*100) }}%</span>
              </div>
              <div class="vc-progress-details">
                <span>{{ job.processed_frames||0 }}/{{ job.total_frames||'?' }} frames</span>
                <span v-if="job.paused" class="vc-paused-badge"><LucideIcon name="pause" :size="12" /> Đã tạm dừng</span>
                <span class="vc-live-stats">
                  <LucideIcon name="car" :size="13" /> {{ job.vehicles_detected||0 }}
                  <LucideIcon name="alert-triangle" :size="13" /> {{ job.violations_detected||0 }}
                  <LucideIcon name="credit-card" :size="13" /> {{ job.plates_detected||0 }}
                </span>
              </div>

              <!-- Frame seek slider -->
              <div v-if="job.total_frames" class="vc-seek-section">
                <label class="vc-seek-label"><LucideIcon name="skip-forward" :size="13" /> Tua đến frame:</label>
                <div class="vc-seek-row">
                  <input
                    type="range"
                    class="vc-seek-slider"
                    :min="0"
                    :max="job.total_frames"
                    :value="job.seekValue ?? job.processed_frames"
                    @input="job.seekValue = Number($event.target.value)"
                    @change="seekToFrame(job, Number($event.target.value))"
                  />
                  <span class="vc-seek-val">{{ job.seekValue ?? job.processed_frames }}</span>
                </div>
              </div>
            </div>

            <!-- Live preview frame -->
            <LivePreviewFrame
              v-if="job.state === 'processing' || job.state === 'paused'"
              :frame="latestFrames[job.job_id]"
            />

            <!-- Actions: Start analysis -->
            <div v-if="job.state === 'uploaded'" class="vc-actions">
              <button class="btn btn--primary" @click="startJobAnalysis(job)" :disabled="job.starting">
                <LucideIcon name="play" :size="16" />
                {{ job.starting ? 'Đang khởi tạo...' : 'Bắt đầu phân tích' }}
              </button>
            </div>

            <!-- Completed results -->
            <div v-if="job.state === 'completed'" class="vc-results">
              <div class="vc-stats-row">
                <div class="rs-card rs-card--blue"><LucideIcon name="car" :size="18" /><span class="rs-val">{{ job.vehicles_detected||0 }}</span><span class="rs-label">Phương tiện</span></div>
                <div class="rs-card rs-card--red"><LucideIcon name="alert-triangle" :size="18" /><span class="rs-val">{{ job.violations_detected||0 }}</span><span class="rs-label">Vi phạm</span></div>
                <div class="rs-card rs-card--yellow"><LucideIcon name="credit-card" :size="18" /><span class="rs-val">{{ job.plates_detected||0 }}</span><span class="rs-label">Biển số</span></div>
              </div>

              <!-- Breakdown badges -->
              <div v-if="job.counts_by_violation && Object.keys(job.counts_by_violation).length" class="vc-badges-row">
                <span v-for="(cnt, vtype) in job.counts_by_violation" :key="vtype" class="badge badge--violation" :class="'viol--' + vtype">
                  {{ violLabel(vtype) }}: {{ cnt }}
                </span>
              </div>
              <div v-if="job.counts_by_class && Object.keys(job.counts_by_class).length" class="vc-badges-row">
                <span v-for="(cnt, cls) in job.counts_by_class" :key="cls" class="badge" :class="classBadge(cls)">
                  {{ classLabel(cls) }}: {{ cnt }}
                </span>
              </div>

              <!-- Expandable results -->
              <button class="btn btn--ghost btn--sm vc-expand-btn" @click="job.expanded = !job.expanded">
                <LucideIcon :name="job.expanded ? 'chevron-up' : 'chevron-down'" :size="16" />
                {{ job.expanded ? 'Thu gọn chi tiết' : 'Xem chi tiết vi phạm & phương tiện' }}
              </button>

              <div v-if="job.expanded" class="vc-detail-section animate-fade-in">
                <!-- Violations -->
                <div v-if="job.violations.length" class="detections-list violations-list">
                  <h3><LucideIcon name="alert-triangle" :size="16" /> Vi phạm phát hiện ({{ job.violations.length }})</h3>
                  <div class="det-grid">
                    <div v-for="(viol, i) in job.violations" :key="'vv'+i" class="det-item det-item--violation">
                      <div class="det-item__left">
                        <span class="det-idx det-idx--danger">{{ i + 1 }}</span>
                        <span class="badge badge--violation" :class="'viol--' + viol.violation_type">{{ viol.violation_label }}</span>
                        <span class="conf-bar__label">{{ (viol.confidence * 100).toFixed(0) }}%</span>
                        <span v-if="viol.plate_text" class="plate-text" style="font-size:0.8rem">{{ viol.plate_text }}</span>
                      </div>
                      <img v-if="viol.evidence_path" :src="getEvidenceUrl(viol.evidence_path)" class="evidence-thumb" @click="evidenceModalItem = viol" title="Xem bằng chứng" />
                    </div>
                  </div>
                </div>

                <!-- Vehicles -->
                <div v-if="job.detections.length" class="detections-list">
                  <h3><LucideIcon name="car" :size="16" /> Phương tiện phát hiện ({{ job.detections.length }})</h3>
                  <div class="det-grid">
                    <div v-for="(v, i) in job.detections" :key="'vd'+i" class="det-item" :class="`det-item--${v.category}`">
                      <div class="det-item__left">
                        <span class="det-idx">{{ i + 1 }}</span>
                        <span class="badge" :class="classBadge(v.vehicle_class)">{{ classLabel(v.vehicle_class) }}</span>
                        <span class="conf-bar__label">{{ (v.confidence * 100).toFixed(0) }}%</span>
                      </div>
                      <img v-if="v.evidence_path" :src="getEvidenceUrl(v.evidence_path)" class="evidence-thumb" @click="evidenceModalItem = v" title="Xem ảnh" />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Error state -->
            <div v-if="job.state === 'error'" class="vc-error">
              <LucideIcon name="alert-circle" :size="16" />
              <span>{{ job.error_message || 'Lỗi không xác định' }}</span>
              <button class="btn btn--ghost btn--sm" @click="retryJob(job)">Thử lại</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-if="!videoJobs.length" class="empty-state">
        <LucideIcon name="video-off" :size="48" />
        <p>Chưa có video nào. Hãy tải lên video để bắt đầu phân tích.</p>
      </div>
    </div>

    <!-- Mode 2: Image Analysis -->
    <div v-if="activeMode === 'image'" class="mode-content">
      <div class="image-upload-section">
        <!-- Drop zone for Image -->
        <div
          class="drop-zone"
          :class="{ 'drop-zone--active': imageDragOver }"
          @dragover.prevent="imageDragOver = true"
          @dragleave="imageDragOver = false"
          @drop.prevent="handleImageDrop"
          @click="triggerImageInput"
        >
          <input ref="imageFileInput" type="file" accept="image/jpeg,image/jpg,image/png,image/webp,image/bmp" style="display:none" @change="handleImageSelect" />
          <div class="drop-content">
            <div class="drop-icon-wrap"><LucideIcon name="image" :size="44" /></div>
            <p class="drop-title">Kéo thả ảnh vào đây</p>
            <p class="drop-sub">hoặc nhấn để chọn file ảnh · JPG, PNG, WEBP, BMP · Phân tích nhận diện AI tức thì</p>
          </div>
        </div>
      </div>

      <!-- Image Analysis Loading / Status -->
      <div v-if="isAnalyzingImage" class="image-analyzing-card">
        <div class="spinner"></div>
        <span>Đang phân tích ảnh bằng các mô hình AI (Vehicles, Violations, Plates)...</span>
      </div>

      <!-- Image Analysis Error -->
      <div v-if="imageError" class="vc-error" style="margin-top:16px">
        <LucideIcon name="alert-circle" :size="16" />
        <span>{{ imageError }}</span>
        <button class="btn btn--ghost btn--sm" @click="runImageAnalysis">Thử lại</button>
      </div>

      <!-- Image Analysis Results -->
      <div v-if="imageResult && !isAnalyzingImage" class="image-result-section animate-fade-in" style="margin-top:20px">
        <div class="image-result-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px">
          <h2 style="margin:0; font-size:1.1rem; display:flex; align-items:center; gap:8px">
            <LucideIcon name="file-check" :size="20" /> Kết quả phân tích ảnh: {{ imageResult.filename }}
          </h2>
          <button class="btn btn--ghost btn--sm" @click="clearImage">
            <LucideIcon name="trash-2" :size="14" /> Xóa kết quả
          </button>
        </div>

        <!-- Annotated Image Preview -->
        <div class="image-preview-card" style="background:var(--bg-card); border:1px solid var(--border-color); border-radius:var(--radius-lg); padding:16px; margin-bottom:20px">
          <h3 style="margin-top:0; font-size:0.95rem; color:var(--text-secondary); display:flex; align-items:center; gap:8px">
            <LucideIcon name="eye" :size="16" /> Ảnh kết quả AI (Vẽ Bounding Boxes)
          </h3>
          <div style="text-align:center; background:var(--bg-inset); border-radius:var(--radius-md); overflow:hidden; padding:8px">
            <img
              :src="`data:image/jpeg;base64,${imageResult.annotated_image_base64}`"
              alt="Annotated Result"
              style="max-width:100%; max-height:550px; object-fit:contain; border-radius:var(--radius-md); cursor:pointer"
              @click="evidenceModalItem = { evidence_path: null, annotated_b64: imageResult.annotated_image_base64, filename: imageResult.filename }"
              title="Nhấn để xem kích thước đầy đủ"
            />
          </div>
        </div>

        <!-- Summary stats -->
        <div class="vc-stats-row" style="margin-bottom:20px">
          <div class="rs-card rs-card--blue"><LucideIcon name="car" :size="20" /><span class="rs-val">{{ imageResult.vehicle_count||0 }}</span><span class="rs-label">Phương tiện</span></div>
          <div class="rs-card rs-card--red"><LucideIcon name="alert-triangle" :size="20" /><span class="rs-val">{{ imageResult.violation_count||0 }}</span><span class="rs-label">Vi phạm</span></div>
          <div class="rs-card rs-card--yellow"><LucideIcon name="credit-card" :size="20" /><span class="rs-val">{{ imageResult.plate_count||0 }}</span><span class="rs-label">Biển số</span></div>
        </div>

        <!-- Violations List -->
        <div v-if="imageResult.violations && imageResult.violations.length" class="detections-list violations-list" style="margin-bottom:20px">
          <h3><LucideIcon name="alert-triangle" :size="16" /> Vi phạm phát hiện ({{ imageResult.violations.length }})</h3>
          <div class="det-grid">
            <div v-for="(viol, i) in imageResult.violations" :key="'img_v'+i" class="det-item det-item--violation">
              <div class="det-item__left">
                <span class="det-idx det-idx--danger">{{ i + 1 }}</span>
                <span class="badge badge--violation" :class="'viol--' + viol.violation_type">{{ viol.violation_label }}</span>
                <span class="conf-bar__label">{{ (viol.confidence * 100).toFixed(0) }}%</span>
                <span v-if="viol.plate_text" class="plate-text" style="font-size:0.8rem">Biển số: {{ viol.plate_text }}</span>
                <span v-if="viol.vehicle_class" style="font-size:0.8rem; color:var(--text-muted)">({{ classLabel(viol.vehicle_class) }})</span>
              </div>
              <img v-if="viol.evidence_path" :src="getEvidenceUrl(viol.evidence_path)" class="evidence-thumb" @click="evidenceModalItem = viol" title="Xem bằng chứng" />
            </div>
          </div>
        </div>

        <!-- Vehicles List -->
        <div v-if="imageResult.vehicles && imageResult.vehicles.length" class="detections-list" style="margin-bottom:20px">
          <h3><LucideIcon name="car" :size="16" /> Phương tiện phát hiện ({{ imageResult.vehicles.length }})</h3>
          <div class="det-grid">
            <div v-for="(v, i) in imageResult.vehicles" :key="'img_det'+i" class="det-item" :class="`det-item--${v.category}`">
              <div class="det-item__left">
                <span class="det-idx">{{ i + 1 }}</span>
                <span class="badge" :class="classBadge(v.vehicle_class)">{{ classLabel(v.vehicle_class) }}</span>
                <span class="conf-bar__label">{{ (v.confidence * 100).toFixed(0) }}%</span>
              </div>
              <img v-if="v.evidence_path" :src="getEvidenceUrl(v.evidence_path)" class="evidence-thumb" @click="evidenceModalItem = v" title="Xem ảnh" />
            </div>
          </div>
        </div>

        <!-- Plates List -->
        <div v-if="imageResult.plates && imageResult.plates.length" class="detections-list" style="border-left: 3px solid #eab308">
          <h3><LucideIcon name="credit-card" :size="16" /> Biển số nhận diện ({{ imageResult.plates.length }})</h3>
          <div class="det-grid">
            <div v-for="(p, i) in imageResult.plates" :key="'img_p'+i" class="det-item">
              <div class="det-item__left">
                <span class="det-idx" style="background:rgba(234,179,8,0.15); color:#eab308">{{ i + 1 }}</span>
                <span class="plate-text" style="font-weight:700">{{ p.plate_text || 'Chưa đọc được' }}</span>
                <span v-if="p.province_name" class="badge badge--info">{{ p.province_name }}</span>
                <span v-if="p.is_valid_plate || p.is_valid" class="badge badge--success">Hợp lệ</span>
              </div>
              <img v-if="p.plate_crop_path" :src="getEvidenceUrl(p.plate_crop_path)" class="evidence-thumb" @click="evidenceModalItem = { evidence_path: p.plate_crop_path, plate_text: p.plate_text }" title="Xem crop biển số" />
            </div>
          </div>
        </div>
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
          <img v-if="evidenceModalItem.evidence_path" :src="getEvidenceUrl(evidenceModalItem.evidence_path)" alt="Evidence" style="width:100%;border-radius:var(--radius-md);display:block" />
          <img v-else-if="evidenceModalItem.annotated_b64" :src="`data:image/jpeg;base64,${evidenceModalItem.annotated_b64}`" alt="Annotated" style="width:100%;border-radius:var(--radius-md);display:block" />
          <div class="evidence-details">
            <p v-if="evidenceModalItem.violation_label"><strong>Lỗi:</strong> <span class="badge badge--violation" :class="'viol--' + evidenceModalItem.violation_type">{{ evidenceModalItem.violation_label }}</span></p>
            <p v-if="evidenceModalItem.vehicle_class"><strong>Loại xe:</strong> {{ classLabel(evidenceModalItem.vehicle_class) }}</p>
            <p v-if="evidenceModalItem.plate_text"><strong>Biển số:</strong> <span class="plate-text">{{ evidenceModalItem.plate_text }}</span></p>
            <p v-if="evidenceModalItem.created_at || evidenceModalItem.timestamp"><strong>Thời gian:</strong> {{ formatTime(evidenceModalItem.created_at || evidenceModalItem.timestamp) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted, reactive, shallowReactive } from 'vue'
import LucideIcon from '@/components/LucideIcon.vue'
import LivePreviewFrame from '@/components/LivePreviewFrame.vue'
import {
  uploadVideo, startAnalysis, getAnalysisStatus,
  pauseAnalysis, resumeAnalysis, seekAnalysis,
  createWebSocket, getViolations, getDetections, getEvidenceUrl,
  analyzeImage
} from '@/api/index.js'


const CLASS_LABELS = { car: 'Xe con', truck: 'Xe tải', bus: 'Xe bus', motorcycle: 'Xe máy' }
const CLASS_BADGES = { car: 'badge--success', truck: 'badge--warning', bus: 'badge--info', motorcycle: 'badge--danger' }
const VIOL_LABELS = { no_helmet: 'Không đội MBH', no_seatbelt: 'Không thắt dây', using_phone: 'Dùng ĐT' }
function classLabel(c) { return CLASS_LABELS[c] || c }
function classBadge(c) { return CLASS_BADGES[c] || 'badge--info' }
function violLabel(v) { return VIOL_LABELS[v] || v }
function stateLabel(s) {
  const map = { pending: 'Chờ upload', uploading: 'Đang upload', uploaded: 'Chờ phân tích', processing: 'Đang phân tích', paused: 'Tạm dừng', completed: 'Hoàn tất', error: 'Lỗi' }
  return map[s] || s
}

// Mode Tabs
const activeMode = ref('video') // 'video' | 'image'

// Single Image Analysis state
const imageFileInput = ref(null)
const selectedImageFile = ref(null)
const imagePreviewUrl = ref(null)
const isAnalyzingImage = ref(false)
const imageError = ref(null)
const imageResult = ref(null)
const imageDragOver = ref(false)

function triggerImageInput() {
  imageFileInput.value?.click()
}

function handleImageSelect(e) {
  const file = e.target.files?.[0]
  if (file) setAndAnalyzeImage(file)
}

function handleImageDrop(e) {
  imageDragOver.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file && (file.type.startsWith('image/') || /\.(jpg|jpeg|png|webp|bmp)$/i.test(file.name))) {
    setAndAnalyzeImage(file)
  }
}

function setAndAnalyzeImage(file) {
  imageError.value = null
  imageResult.value = null
  selectedImageFile.value = file
  if (imagePreviewUrl.value) URL.revokeObjectURL(imagePreviewUrl.value)
  imagePreviewUrl.value = URL.createObjectURL(file)
  runImageAnalysis()
}

async function runImageAnalysis() {
  if (!selectedImageFile.value || isAnalyzingImage.value) return
  isAnalyzingImage.value = true
  imageError.value = null
  try {
    const res = await analyzeImage(selectedImageFile.value)
    imageResult.value = res
  } catch (err) {
    imageError.value = err.message || 'Phân tích ảnh thất bại'
  } finally {
    isAnalyzingImage.value = false
  }
}

function clearImage() {
  selectedImageFile.value = null
  if (imagePreviewUrl.value) {
    URL.revokeObjectURL(imagePreviewUrl.value)
    imagePreviewUrl.value = null
  }
  imageResult.value = null
  imageError.value = null
}

// Speed slider
const speedSteps = [1, 2, 3, 5, 10, 15, 20, 30]
const speedIndex = ref(0)
const currentSpeed = computed(() => speedSteps[speedIndex.value])

// Video jobs list
const videoJobs = ref([])
const dragOver = ref(false)
const evidenceModalItem = ref(null)

// Ảnh preview realtime theo job_id
const latestFrames = shallowReactive({})

// Poll timers per job
const pollTimers = {}

// WebSocket
let ws = null

// Coalesce nhiều message WS đến giữa 2 lần vẽ lại màn hình thành 1 lần cập nhật DOM
// (requestAnimationFrame) — tránh set liên tục ngoài nhịp render của trình duyệt.
const pendingFrames = {}
let rafScheduled = false
function flushPendingFrames() {
  rafScheduled = false
  for (const jobId in pendingFrames) {
    latestFrames[jobId] = pendingFrames[jobId]
  }
  for (const jobId in pendingFrames) delete pendingFrames[jobId]
}
function queueFrameUpdate(jobId, frameBase64) {
  pendingFrames[jobId] = frameBase64
  if (!rafScheduled) {
    rafScheduled = true
    requestAnimationFrame(flushPendingFrames)
  }
}

function connectWS() {
  if (ws && ws.readyState <= 1) return
  try {
    ws = createWebSocket('upload')
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === 'upload_progress' && msg.data?.job_id && msg.data.frame_result?.frame_base64) {
          queueFrameUpdate(msg.data.job_id, msg.data.frame_result.frame_base64)
        }
      } catch {}
    }
    ws.onclose = () => { setTimeout(connectWS, 3000) }
  } catch {}
}

// File handling
const MAX_SIZE = 500 * 1024 * 1024
const MAX_DURATION = 600

function handleFileSelect(e) {
  const files = Array.from(e.target.files || [])
  files.forEach(f => addFile(f))
  if (e.target) e.target.value = ''
}
function handleDrop(e) {
  dragOver.value = false
  const files = Array.from(e.dataTransfer?.files || [])
  files.forEach(f => { if (f.type.startsWith('video/') || /\.(mp4|avi|mov|mkv)$/i.test(f.name)) addFile(f) })
}

function addFile(file) {
  const ext = file.name.split('.').pop().toLowerCase()
  if (!['mp4', 'avi', 'mov', 'mkv', 'wmv'].includes(ext)) return
  if (file.size > MAX_SIZE) return

  const id = Date.now() + '_' + Math.random().toString(36).slice(2, 8)
  const job = reactive({
    id,
    file,
    filename: file.name,
    file_size: file.size,
    duration_sec: null,
    state: 'pending', // pending -> uploading -> uploaded -> processing -> completed|error
    job_id: null,
    uploadProgress: 0,
    progress: 0,
    total_frames: 0,
    processed_frames: 0,
    vehicles_detected: 0,
    violations_detected: 0,
    plates_detected: 0,
    counts_by_class: {},
    counts_by_category: {},
    counts_by_violation: {},
    error_message: null,
    frame_skip: 1,
    starting: false,
    paused: false,
    seekValue: null,
    expanded: false,
    violations: [],
    detections: [],
  })

  // Get duration
  const video = document.createElement('video')
  video.preload = 'metadata'
  video.onloadedmetadata = () => {
    job.duration_sec = video.duration
    URL.revokeObjectURL(video.src)
    if (video.duration > MAX_DURATION) {
      job.state = 'error'
      job.error_message = `Video quá dài: ${formatDuration(video.duration)}. Tối đa 10 phút.`
    }
  }
  video.src = URL.createObjectURL(file)

  videoJobs.value.push(job)

  // Auto-upload
  uploadJob(job)
}

async function uploadJob(job) {
  if (job.state === 'error') return
  job.state = 'uploading'
  job.uploadProgress = 0
  try {
    const result = await uploadVideo(job.file, (pct) => { job.uploadProgress = pct })
    job.job_id = result.job_id
    job.filename = result.filename
    job.file_size = result.file_size
    job.duration_sec = result.duration_sec || job.duration_sec
    job.total_frames = result.total_frames || 0
    job.state = 'uploaded'
  } catch (err) {
    job.state = 'error'
    job.error_message = err.message || 'Upload thất bại'
  }
}

async function startJobAnalysis(job) {
  if (!job.job_id || job.starting) return
  job.starting = true
  job.frame_skip = currentSpeed.value
  try {
    await startAnalysis(job.job_id, currentSpeed.value)
    job.state = 'processing'
    connectWS()
    startPollForJob(job)
  } catch (err) {
    if (err.message && err.message.includes('429')) {
      job.error_message = 'Đang phân tích 2 video. Vui lòng chờ video khác hoàn tất.'
      job.state = 'error'
    } else {
      job.error_message = err.message || 'Không thể bắt đầu phân tích'
      job.state = 'error'
    }
  } finally {
    job.starting = false
  }
}

async function togglePause(job) {
  if (!job.job_id) return
  try {
    if (job.paused) {
      await resumeAnalysis(job.job_id)
      job.paused = false
      job.state = 'processing'
    } else {
      await pauseAnalysis(job.job_id)
      job.paused = true
      job.state = 'paused'
    }
  } catch (err) {
    console.error('Pause/resume error:', err)
  }
}

async function seekToFrame(job, frame) {
  if (!job.job_id) return
  try {
    await seekAnalysis(job.job_id, frame)
    job.seekValue = frame
  } catch (err) {
    console.error('Seek error:', err)
  }
}

function startPollForJob(job) {
  if (pollTimers[job.id]) clearInterval(pollTimers[job.id])
  pollStatus(job)
  pollTimers[job.id] = setInterval(() => pollStatus(job), 2000)
}

async function pollStatus(job) {
  if (!job.job_id) return
  try {
    const s = await getAnalysisStatus(job.job_id)
    job.progress = s.progress || 0
    job.total_frames = s.total_frames || job.total_frames
    job.processed_frames = s.processed_frames || 0
    job.vehicles_detected = s.vehicles_detected || 0
    job.violations_detected = s.violations_detected || 0
    job.plates_detected = s.plates_detected || 0
    job.counts_by_class = s.counts_by_class || {}
    job.counts_by_category = s.counts_by_category || {}
    job.counts_by_violation = s.counts_by_violation || {}
    job.error_message = s.error_message
    job.frame_skip = s.frame_skip || job.frame_skip

    if (s.status === 'completed') {
      job.state = 'completed'
      job.paused = false
      stopPollForJob(job)
      await loadJobResults(job)
    } else if (s.status === 'error') {
      job.state = 'error'
      job.paused = false
      stopPollForJob(job)
    } else if (s.status === 'paused') {
      job.state = 'paused'
      job.paused = true
    } else if (s.status === 'processing') {
      job.state = 'processing'
      job.paused = false
    }
  } catch {}
}

function stopPollForJob(job) {
  if (pollTimers[job.id]) {
    clearInterval(pollTimers[job.id])
    delete pollTimers[job.id]
  }
}

async function loadJobResults(job) {
  try {
    const filename = job.filename
    const violRes = await getViolations({ source_file: filename, limit: 100 })
    job.violations = violRes.violations || []
    const detRes = await getDetections({ source_file: filename, limit: 100 })
    job.detections = detRes.detections || []
  } catch (e) { console.error('Error loading results:', e) }
}

function removeJob(idx) {
  const job = videoJobs.value[idx]
  stopPollForJob(job)
  if (job.job_id) {
    delete latestFrames[job.job_id]
    delete pendingFrames[job.job_id]
  }
  videoJobs.value.splice(idx, 1)
}

function clearAllCompleted() {
  for (const j of videoJobs.value) {
    if (j.state === 'completed' && j.job_id) delete latestFrames[j.job_id]
  }
  videoJobs.value = videoJobs.value.filter(j => j.state !== 'completed')
}

function retryJob(job) {
  if (job.job_id) {
    job.state = 'uploaded'
    job.error_message = null
    job.progress = 0
    job.processed_frames = 0
    job.vehicles_detected = 0
    job.violations_detected = 0
    job.plates_detected = 0
    if (job.job_id) delete latestFrames[job.job_id]
  } else {
    job.state = 'pending'
    job.error_message = null
    uploadJob(job)
  }
}

function formatSize(b) { if (!b) return ''; return b < 1024*1024 ? `${(b/1024).toFixed(1)} KB` : `${(b/(1024*1024)).toFixed(1)} MB` }
function formatDuration(s) { if (!s) return ''; return `${Math.floor(s/60)}:${String(Math.round(s%60)).padStart(2,'0')}` }
function formatTime(ts) { if (!ts) return '—'; return new Date(ts).toLocaleString('vi-VN', { hour12: false }) }

onUnmounted(() => {
  Object.values(pollTimers).forEach(t => clearInterval(t))
  if (ws) ws.close()
})
</script>

<style scoped>
/* Mode Tabs */
.analysis-mode-tabs {
  display: flex;
  gap: 12px;
  margin-bottom: var(--sp-xl);
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 14px;
}
.mode-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 22px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.95rem;
  cursor: pointer;
  transition: all var(--transition-fast);
}
.mode-tab:hover {
  color: var(--text-primary);
  border-color: var(--accent-primary);
  background: rgba(37,99,235,0.04);
}
.mode-tab--active {
  background: var(--accent-primary);
  color: #ffffff;
  border-color: var(--accent-primary);
  box-shadow: 0 4px 14px rgba(37,99,235,0.3);
}

/* Image Analyzing Card */
.image-analyzing-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px 24px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  margin-top: 16px;
  color: var(--text-primary);
  font-size: 0.95rem;
}
.spinner {
  width: 22px;
  height: 22px;
  border: 3px solid rgba(37,99,235,0.2);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Upload + Settings Row */
.upload-settings-row {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  gap: var(--sp-lg);
  margin-bottom: var(--sp-xl);
  align-items: stretch;
}
@media (max-width: 992px) { .upload-settings-row { grid-template-columns: 1fr; } }

/* Drop zone */
.drop-zone {
  border: 2px dashed var(--border-color); border-radius: var(--radius-lg);
  padding: var(--sp-2xl); text-align: center; cursor: pointer;
  transition: all var(--transition-fast); background: var(--bg-card);
  min-height: 200px; display: flex; align-items: center; justify-content: center;
}
.drop-zone:hover { border-color: var(--accent-primary); background: rgba(37,99,235,0.03); }
.drop-zone--active { border-color: var(--accent-primary); background: rgba(37,99,235,0.06); border-style: solid; }
.drop-content { display: flex; flex-direction: column; align-items: center; gap: var(--sp-sm); }
.drop-icon-wrap { color: var(--text-muted); opacity: 0.5; margin-bottom: 8px; }
.drop-title { font-size: 1rem; font-weight: 600; color: var(--text-primary); margin: 0; }
.drop-sub { font-size: 0.82rem; color: var(--text-muted); margin: 0; max-width: 320px; line-height: 1.5; }

/* Speed panel */
.speed-panel {
  background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg);
  padding: var(--sp-lg); display: flex; flex-direction: column; gap: 14px;
}
.speed-panel h3 { margin: 0; font-size: 0.9rem; color: var(--text-primary); display: flex; align-items: center; gap: 8px; }
.speed-slider-wrap { display: flex; flex-direction: column; gap: 6px; }
.speed-slider {
  width: 100%; height: 6px; -webkit-appearance: none; appearance: none;
  background: var(--bg-inset); border-radius: 3px; outline: none;
  cursor: pointer;
}
.speed-slider::-webkit-slider-thumb {
  -webkit-appearance: none; width: 20px; height: 20px; border-radius: 50%;
  background: var(--accent-primary); cursor: grab;
  box-shadow: 0 2px 6px rgba(37,99,235,0.3);
  transition: transform 0.15s ease;
}
.speed-slider::-webkit-slider-thumb:hover { transform: scale(1.2); }
.speed-slider::-moz-range-thumb {
  width: 20px; height: 20px; border-radius: 50%; border: none;
  background: var(--accent-primary); cursor: grab;
}
.speed-labels {
  display: flex; justify-content: space-between; padding: 0 2px;
}
.speed-label { font-size: 0.68rem; color: var(--text-muted); font-weight: 600; transition: color 0.2s; }
.speed-label--active { color: var(--accent-primary); }
.speed-info { display: flex; align-items: center; gap: 10px; }
.speed-badge {
  background: rgba(37,99,235,0.12); color: var(--accent-primary);
  padding: 4px 12px; border-radius: var(--radius-full);
  font-weight: 800; font-size: 0.9rem; font-family: var(--font-mono);
}
.speed-desc { font-size: 0.78rem; color: var(--text-muted); line-height: 1.4; }
.speed-note {
  font-size: 0.72rem; color: var(--text-muted); display: flex; align-items: flex-start; gap: 6px;
  background: rgba(234,179,8,0.06); padding: 8px 12px; border-radius: var(--radius-md);
  border: 1px solid rgba(234,179,8,0.12); line-height: 1.4;
}

/* Video list */
.video-list-section { margin-top: var(--sp-md); }
.video-list-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--sp-md); }
.video-list-header h2 { margin: 0; font-size: 1.05rem; display: flex; align-items: center; gap: 8px; }
.video-cards { display: flex; flex-direction: column; gap: var(--sp-md); }

/* Video card */
.video-card {
  background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg);
  padding: 24px 28px; transition: all var(--transition-fast);
  border-left: 5px solid var(--border-color);
}
.video-card:hover { box-shadow: var(--shadow-md); }
.video-card--uploading { border-left-color: #60a5fa; }
.video-card--uploaded { border-left-color: #eab308; }
.video-card--processing { border-left-color: #60a5fa; animation: pulse-border 2s ease-in-out infinite; }
.video-card--paused { border-left-color: #eab308; }
.video-card--completed { border-left-color: #34d399; }
.video-card--error { border-left-color: #f87171; }

@keyframes pulse-border { 0%, 100% { border-left-color: #60a5fa; } 50% { border-left-color: #3b82f6; } }

/* Card header */
.vc-header { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--sp-md); }
.vc-info { flex: 1; }
.vc-title-row { display: flex; align-items: center; gap: 8px; }
.vc-idx {
  width: 30px; height: 30px; border-radius: 50%; background: rgba(37,99,235,0.12); color: #60a5fa;
  display: flex; align-items: center; justify-content: center; font-size: 0.82rem; font-weight: 700; flex-shrink: 0;
}
.vc-name { font-weight: 600; font-size: 1.05rem; color: var(--text-primary); word-break: break-all; }
.vc-meta { font-size: 0.85rem; color: var(--text-muted); margin-top: 6px; margin-left: 38px; }
.vc-status-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.vc-status-badge {
  padding: 4px 12px; border-radius: var(--radius-full); font-size: 0.72rem; font-weight: 600; text-transform: uppercase; white-space: nowrap;
}
.status--pending    { background: rgba(148,163,184,0.12); color: #94a3b8; }
.status--uploading  { background: rgba(37,99,235,0.12);   color: #60a5fa; }
.status--uploaded   { background: rgba(234,179,8,0.12);   color: #eab308; }
.status--processing { background: rgba(37,99,235,0.12);   color: #60a5fa; }
.status--paused     { background: rgba(234,179,8,0.12);   color: #eab308; }
.status--completed  { background: rgba(16,185,129,0.12);  color: #34d399; }
.status--error      { background: rgba(239,68,68,0.12);   color: #f87171; }
.btn--icon-danger {
  width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
  border: none; background: rgba(239,68,68,0.1); color: #f87171; border-radius: 50%; cursor: pointer;
  transition: all 0.2s;
}
.btn--icon-danger:hover { background: rgba(239,68,68,0.2); }

/* Progress + Controls */
.vc-progress-section { margin-top: 14px; display: flex; flex-direction: column; gap: 8px; }
.vc-progress-text { font-size: 0.78rem; color: var(--text-muted); text-align: center; display: block; margin-top: 6px; }
.progress-bar__fill--upload { background: linear-gradient(90deg, #60a5fa, #3b82f6); }
.vc-progress-details { display: flex; justify-content: space-between; align-items: center; font-size: 0.78rem; color: var(--text-muted); }
.vc-live-stats { display: flex; align-items: center; gap: 8px; }

/* Controls row (pause btn + progress bar + pct) */
.vc-controls-row {
  display: flex; align-items: center; gap: 12px;
}
.btn--icon-control {
  width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--border-color); background: var(--bg-inset); color: var(--text-primary);
  border-radius: 50%; cursor: pointer; transition: all 0.2s; flex-shrink: 0;
}
.btn--icon-control:hover { background: rgba(37,99,235,0.1); border-color: var(--accent-primary); color: var(--accent-primary); }
.vc-pct { font-size: 0.82rem; font-weight: 700; color: var(--text-primary); font-family: var(--font-mono); min-width: 40px; text-align: right; }
.vc-paused-badge {
  display: inline-flex; align-items: center; gap: 4px;
  background: rgba(234,179,8,0.12); color: #eab308; padding: 2px 10px; border-radius: var(--radius-full);
  font-size: 0.72rem; font-weight: 600;
}

/* Frame seek slider */
.vc-seek-section {
  background: var(--bg-inset); border: 1px solid var(--border-color); border-radius: var(--radius-md);
  padding: 10px 14px; display: flex; flex-direction: column; gap: 6px;
}
.vc-seek-label {
  font-size: 0.75rem; font-weight: 600; color: var(--text-muted); display: flex; align-items: center; gap: 6px;
}
.vc-seek-row { display: flex; align-items: center; gap: 12px; }
.vc-seek-slider {
  flex: 1; height: 5px; -webkit-appearance: none; appearance: none;
  background: var(--border-color); border-radius: 3px; outline: none; cursor: pointer;
}
.vc-seek-slider::-webkit-slider-thumb {
  -webkit-appearance: none; width: 16px; height: 16px; border-radius: 50%;
  background: var(--accent-primary); cursor: grab;
  box-shadow: 0 1px 4px rgba(37,99,235,0.3);
}
.vc-seek-slider::-moz-range-thumb {
  width: 16px; height: 16px; border-radius: 50%; border: none;
  background: var(--accent-primary); cursor: grab;
}
.vc-seek-val {
  font-size: 0.82rem; font-weight: 700; color: var(--accent-primary); font-family: var(--font-mono);
  min-width: 48px; text-align: right;
}

/* Preview */
.vc-preview { margin-top: 16px; border-radius: var(--radius-lg); overflow: hidden; border: 1px solid var(--border-color); max-height: 420px; }
.vc-preview-img { width: 100%; display: block; object-fit: contain; max-height: 420px; }

/* Actions */
.vc-actions { margin-top: 12px; }

/* Results */
.vc-results { margin-top: 18px; display: flex; flex-direction: column; gap: 16px; }
.vc-stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.rs-card {
  background: var(--bg-inset); border: 1px solid var(--border-color); border-radius: var(--radius-lg);
  padding: 18px 16px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 6px;
  transition: transform var(--transition-fast);
}
.rs-card:hover { transform: translateY(-2px); }
.rs-card--blue   { border-top: 3px solid var(--accent-primary); }
.rs-card--red    { border-top: 3px solid var(--accent-danger); }
.rs-card--yellow { border-top: 3px solid var(--accent-warning); }
.rs-val  { font-size: 1.8rem; font-weight: 800; color: var(--text-primary); }
.rs-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
.vc-badges-row { display: flex; gap: 6px; flex-wrap: wrap; }
.vc-expand-btn { align-self: center; }
.vc-detail-section { display: flex; flex-direction: column; gap: 14px; }

/* Error */
.vc-error {
  margin-top: 12px; padding: 10px 16px; display: flex; align-items: center; gap: 8px;
  background: rgba(239,68,68,0.06); border: 1px solid rgba(239,68,68,0.15); border-radius: var(--radius-md);
  color: #f87171; font-size: 0.85rem;
}
.vc-error span { flex: 1; }

/* Empty state */
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--sp-md);
  padding: var(--sp-2xl); color: var(--text-muted); opacity: 0.6;
}
.empty-state p { margin: 0; font-size: 0.9rem; }

/* Reused detection list styles */
.detections-list { background: var(--bg-inset); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: var(--sp-lg); }
.detections-list h3 { margin: 0 0 var(--sp-md); font-size: 0.9rem; color: var(--text-secondary); display: flex; align-items: center; gap: 8px; }
.det-grid { display: flex; flex-direction: column; gap: 6px; }
.det-item {
  display: flex; align-items: center; justify-content: space-between; gap: var(--sp-sm);
  padding: 8px 12px; border-radius: var(--radius-md); background: var(--bg-card); border: 1px solid var(--border-color); font-size: 0.85rem;
}
.det-item__left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.det-item--oto    { border-left: 3px solid #22c55e; }
.det-item--xe_may { border-left: 3px solid #ef4444; }
.det-item--violation { border-left: 3px solid #ef4444; }
.violations-list { border-left: 3px solid #ef4444; }
.det-idx { width: 24px; height: 24px; background: rgba(37,99,235,0.12); color: #60a5fa; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.72rem; font-weight: 700; flex-shrink: 0; }
.det-idx--danger { background: rgba(239,68,68,0.12); color: #f87171; }

.evidence-details { margin-top: 16px; display: flex; flex-direction: column; gap: 8px; }
.evidence-details p { margin: 0; font-size: 0.9rem; color: var(--text-secondary); }
.evidence-details strong { color: var(--text-primary); }
</style>
