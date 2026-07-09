<template>
  <div class="uploader-container">
    <div
      class="dropzone"
      :class="{ 'dropzone--dragging': isDragging, 'dropzone--has-file': selectedFile, 'dropzone--uploading': isUploading }"
      @dragenter.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @dragover.prevent
      @drop.prevent="handleDrop"
      @click="triggerFileInput"
    >
      <input ref="fileInput" type="file" accept="video/mp4,video/avi,video/x-msvideo,video/quicktime,video/x-matroska" style="display:none" @change="handleFileSelect" />

      <template v-if="!selectedFile">
        <div class="dropzone__icon"><LucideIcon name="film" :size="44" /></div>
        <div class="dropzone__title">Kéo thả video vào đây</div>
        <div class="dropzone__sub">hoặc nhấn để chọn file</div>
        <div class="dropzone__formats">MP4, AVI, MOV, MKV · Tối đa 10 phút · 500MB</div>
      </template>

      <template v-else>
        <div class="file-preview">
          <div class="file-preview__icon"><LucideIcon name="file-video" :size="32" /></div>
          <div class="file-preview__info">
            <span class="file-preview__name">{{ selectedFile.name }}</span>
            <span class="file-preview__meta">
              {{ formatFileSize(selectedFile.size) }}
              <span v-if="videoDuration"> · {{ formatDuration(videoDuration) }}</span>
            </span>
          </div>
          <button class="btn-remove" @click.stop="clearFile" title="Xóa file">
            <LucideIcon name="x" :size="16" />
          </button>
        </div>

        <div v-if="isUploading" class="upload-progress">
          <div class="progress-bar">
            <div class="progress-bar__fill" :style="{ width: uploadProgress + '%' }"></div>
          </div>
          <span class="progress-label">Đang upload: {{ uploadProgress }}%</span>
        </div>
      </template>
    </div>

    <div v-if="selectedFile && !isUploading" class="upload-actions">
      <div v-if="videoDuration" class="upload-estimate">
        <LucideIcon name="clock" :size="14" />
        Ước tính xử lý: ~{{ estimatedProcessTime }}
      </div>
      <button class="btn btn--primary btn--lg" @click="handleUpload" :disabled="isUploading">
        <LucideIcon name="upload-cloud" :size="18" />
        Upload & Phân tích
      </button>
    </div>

    <div v-if="errorMessage" class="upload-error">
      <LucideIcon name="alert-circle" :size="16" />
      {{ errorMessage }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { uploadVideo as uploadVideoFn } from '@/api/index.js'
import LucideIcon from '@/components/LucideIcon.vue'

const emit = defineEmits(['uploaded', 'error'])

const fileInput = ref(null)
const selectedFile = ref(null)
const isDragging = ref(false)
const isUploading = ref(false)
const uploadProgress = ref(0)
const videoDuration = ref(null)
const errorMessage = ref('')

const MAX_DURATION = 600
const MAX_SIZE = 500 * 1024 * 1024

const estimatedProcessTime = computed(() => {
  if (!videoDuration.value) return '---'
  const processFrames = Math.ceil(videoDuration.value * 3)
  const estimatedSec = processFrames * 0.5
  if (estimatedSec < 60) return `${Math.round(estimatedSec)} giây`
  return `${Math.round(estimatedSec / 60)} phút`
})

function triggerFileInput() { if (!isUploading.value) fileInput.value?.click() }
function handleDrop(e) { isDragging.value = false; const files = e.dataTransfer?.files; if (files?.length) validateAndSetFile(files[0]) }
function handleFileSelect(e) { const files = e.target?.files; if (files?.length) validateAndSetFile(files[0]) }

function validateAndSetFile(file) {
  errorMessage.value = ''
  const ext = file.name.split('.').pop().toLowerCase()
  if (!['mp4', 'avi', 'mov', 'mkv', 'wmv'].includes(ext)) { errorMessage.value = `Định dạng không hỗ trợ: .${ext}`; return }
  if (file.size > MAX_SIZE) { errorMessage.value = `File quá lớn: ${formatFileSize(file.size)}. Tối đa: 500MB`; return }
  selectedFile.value = file
  const video = document.createElement('video')
  video.preload = 'metadata'
  video.onloadedmetadata = () => {
    videoDuration.value = video.duration
    URL.revokeObjectURL(video.src)
    if (video.duration > MAX_DURATION) { errorMessage.value = `Video quá dài: ${formatDuration(video.duration)}. Tối đa: 10 phút`; selectedFile.value = null; videoDuration.value = null }
  }
  video.onerror = () => { videoDuration.value = null }
  video.src = URL.createObjectURL(file)
}

function clearFile() { selectedFile.value = null; videoDuration.value = null; errorMessage.value = ''; uploadProgress.value = 0; if (fileInput.value) fileInput.value.value = '' }

async function handleUpload() {
  if (!selectedFile.value || isUploading.value) return
  isUploading.value = true; uploadProgress.value = 0; errorMessage.value = ''
  try {
    const result = await uploadVideoFn(selectedFile.value, (pct) => { uploadProgress.value = pct })
    isUploading.value = false; emit('uploaded', result)
  } catch (err) {
    isUploading.value = false; errorMessage.value = err.message || 'Upload thất bại'; emit('error', err)
  }
}

function formatFileSize(bytes) { if (bytes < 1024) return `${bytes} B`; if (bytes < 1024*1024) return `${(bytes/1024).toFixed(1)} KB`; return `${(bytes/(1024*1024)).toFixed(1)} MB` }
function formatDuration(sec) { const m = Math.floor(sec/60); const s = Math.round(sec%60); return `${m}:${String(s).padStart(2,'0')}` }
</script>

<style scoped>
.uploader-container { width: 100%; }

.dropzone {
  border: 2px dashed var(--border-color); border-radius: var(--radius-lg);
  padding: 48px 24px; text-align: center; cursor: pointer;
  transition: all 0.3s ease; background: var(--bg-card);
}
.dropzone:hover { border-color: var(--accent-primary); background: rgba(37,99,235,0.03); }
.dropzone--dragging { border-color: var(--accent-primary); background: rgba(37,99,235,0.06); transform: scale(1.005); }
.dropzone--has-file { border-style: solid; padding: 24px; }
.dropzone--uploading { pointer-events: none; opacity: 0.8; }

.dropzone__icon { color: var(--text-muted); opacity: 0.4; margin-bottom: 12px; }
.dropzone__title { font-size: 1.1rem; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.dropzone__sub { color: var(--text-muted); font-size: 0.9rem; margin-bottom: 12px; }
.dropzone__formats { font-size: 0.75rem; color: var(--text-muted); opacity: 0.7; }

.file-preview { display: flex; align-items: center; gap: 16px; text-align: left; }
.file-preview__icon { color: var(--accent-primary); flex-shrink: 0; }
.file-preview__info { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.file-preview__name { font-weight: 600; color: var(--text-primary); font-size: 0.95rem; word-break: break-all; }
.file-preview__meta { font-size: 0.8rem; color: var(--text-muted); }
.btn-remove {
  width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
  background: rgba(239,68,68,0.12); color: #f87171; border: none; border-radius: 50%;
  cursor: pointer; transition: all 0.2s;
}
.btn-remove:hover { background: rgba(239,68,68,0.25); }

.upload-progress { margin-top: 16px; }
.progress-label { display: block; text-align: center; font-size: 0.8rem; font-weight: 600; color: var(--text-secondary); margin-top: 8px; }

.upload-actions { display: flex; align-items: center; justify-content: space-between; margin-top: 16px; gap: 16px; }
.upload-estimate { font-size: 0.85rem; color: var(--text-muted); display: flex; align-items: center; gap: 6px; }

.upload-error {
  margin-top: 12px; padding: 10px 16px; display: flex; align-items: center; gap: 8px;
  background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.2); border-radius: var(--radius-md);
  color: #f87171; font-size: 0.85rem;
}
</style>
