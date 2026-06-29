<template>
  <div class="uploader-container">
    <!-- Drag & Drop Zone -->
    <div
      class="dropzone"
      :class="{
        'dropzone--dragging': isDragging,
        'dropzone--has-file': selectedFile,
        'dropzone--uploading': isUploading,
      }"
      @dragenter.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @dragover.prevent
      @drop.prevent="handleDrop"
      @click="triggerFileInput"
    >
      <input
        ref="fileInput"
        type="file"
        accept="video/mp4,video/avi,video/x-msvideo,video/quicktime,video/x-matroska"
        style="display: none"
        @change="handleFileSelect"
      />

      <template v-if="!selectedFile">
        <div class="dropzone__icon">VIDEO</div>
        <div class="dropzone__title">Kéo thả video vào đây</div>
        <div class="dropzone__sub">hoặc click để chọn file</div>
        <div class="dropzone__formats">MP4, AVI, MOV, MKV • Tối đa 10 phút • 500MB</div>
      </template>

      <template v-else>
        <div class="file-preview">
          <div class="file-preview__icon">FILM</div>
          <div class="file-preview__info">
            <span class="file-preview__name">{{ selectedFile.name }}</span>
            <span class="file-preview__meta">
              {{ formatFileSize(selectedFile.size) }}
              <span v-if="videoDuration"> • {{ formatDuration(videoDuration) }}</span>
            </span>
          </div>
          <button class="btn-remove" @click.stop="clearFile" title="Xóa file">✕</button>
        </div>

        <!-- Upload progress -->
        <div v-if="isUploading" class="progress-bar">
          <div class="progress-bar__fill" :style="{ width: uploadProgress + '%' }"></div>
          <span class="progress-bar__text">Đang upload: {{ uploadProgress }}%</span>
        </div>
      </template>
    </div>

    <!-- Upload button -->
    <div v-if="selectedFile && !isUploading" class="upload-actions">
      <div v-if="videoDuration" class="upload-estimate">
        Uoc tinh xu ly: ~{{ estimatedProcessTime }}
      </div>
      <button class="btn-upload" @click="handleUpload" :disabled="isUploading">
        Upload & Phan tich
      </button>
    </div>

    <!-- Error message -->
    <div v-if="errorMessage" class="upload-error">
      Loi: {{ errorMessage }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { uploadVideo as uploadVideoFn } from '@/api/index.js'

const emit = defineEmits(['uploaded', 'error'])

const fileInput = ref(null)
const selectedFile = ref(null)
const isDragging = ref(false)
const isUploading = ref(false)
const uploadProgress = ref(0)
const videoDuration = ref(null)
const errorMessage = ref('')

const MAX_DURATION = 600 // 10 minutes
const MAX_SIZE = 500 * 1024 * 1024 // 500MB

const estimatedProcessTime = computed(() => {
  if (!videoDuration.value) return '---'
  const processFrames = Math.ceil(videoDuration.value * 3) // 3 FPS
  const estimatedSec = processFrames * 0.5 // ~0.5s per frame
  if (estimatedSec < 60) return `${Math.round(estimatedSec)} giây`
  return `${Math.round(estimatedSec / 60)} phút`
})

function triggerFileInput() {
  if (!isUploading.value) fileInput.value?.click()
}

function handleDrop(e) {
  isDragging.value = false
  const files = e.dataTransfer?.files
  if (files?.length) validateAndSetFile(files[0])
}

function handleFileSelect(e) {
  const files = e.target?.files
  if (files?.length) validateAndSetFile(files[0])
}

function validateAndSetFile(file) {
  errorMessage.value = ''

  // Check file type
  const ext = file.name.split('.').pop().toLowerCase()
  if (!['mp4', 'avi', 'mov', 'mkv', 'wmv'].includes(ext)) {
    errorMessage.value = `Định dạng không hỗ trợ: .${ext}`
    return
  }

  // Check file size
  if (file.size > MAX_SIZE) {
    errorMessage.value = `File quá lớn: ${formatFileSize(file.size)}. Tối đa: 500MB`
    return
  }

  selectedFile.value = file

  // Get video duration
  const video = document.createElement('video')
  video.preload = 'metadata'
  video.onloadedmetadata = () => {
    videoDuration.value = video.duration
    URL.revokeObjectURL(video.src)

    if (video.duration > MAX_DURATION) {
      errorMessage.value = `Video quá dài: ${formatDuration(video.duration)}. Tối đa: 10 phút`
      selectedFile.value = null
      videoDuration.value = null
    }
  }
  video.onerror = () => {
    // Can't read metadata, allow upload anyway
    videoDuration.value = null
  }
  video.src = URL.createObjectURL(file)
}

function clearFile() {
  selectedFile.value = null
  videoDuration.value = null
  errorMessage.value = ''
  uploadProgress.value = 0
  if (fileInput.value) fileInput.value.value = ''
}

async function handleUpload() {
  if (!selectedFile.value || isUploading.value) return

  isUploading.value = true
  uploadProgress.value = 0
  errorMessage.value = ''

  try {
    const result = await uploadVideoFn(selectedFile.value, (pct) => {
      uploadProgress.value = pct
    })
    isUploading.value = false
    emit('uploaded', result)
  } catch (err) {
    isUploading.value = false
    errorMessage.value = err.message || 'Upload thất bại'
    emit('error', err)
  }
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDuration(sec) {
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
</script>

<style scoped>
.uploader-container {
  width: 100%;
}

.dropzone {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg, 12px);
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background: var(--bg-surface, #1e293b);
}
.dropzone:hover {
  border-color: var(--accent-primary, #3b82f6);
  background: rgba(59, 130, 246, 0.05);
}
.dropzone--dragging {
  border-color: var(--accent-primary, #3b82f6);
  background: rgba(59, 130, 246, 0.1);
  transform: scale(1.01);
}
.dropzone--has-file {
  border-style: solid;
  padding: 24px;
}
.dropzone--uploading {
  pointer-events: none;
  opacity: 0.8;
}

.dropzone__icon {
  font-size: 3rem;
  margin-bottom: 12px;
}
.dropzone__title {
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--text-primary, #e2e8f0);
  margin-bottom: 4px;
}
.dropzone__sub {
  color: var(--text-muted, #94a3b8);
  font-size: 0.9rem;
  margin-bottom: 12px;
}
.dropzone__formats {
  font-size: 0.75rem;
  color: var(--text-muted, #94a3b8);
  opacity: 0.7;
}

/* File preview */
.file-preview {
  display: flex;
  align-items: center;
  gap: 16px;
  text-align: left;
}
.file-preview__icon { font-size: 2.5rem; }
.file-preview__info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.file-preview__name {
  font-weight: 600;
  color: var(--text-primary, #e2e8f0);
  font-size: 0.95rem;
  word-break: break-all;
}
.file-preview__meta {
  font-size: 0.8rem;
  color: var(--text-muted, #94a3b8);
}
.btn-remove {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
  border: none;
  border-radius: 50%;
  width: 32px;
  height: 32px;
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-remove:hover {
  background: rgba(239, 68, 68, 0.4);
}

/* Progress */
.progress-bar {
  margin-top: 16px;
  background: rgba(59, 130, 246, 0.1);
  border-radius: 8px;
  height: 28px;
  position: relative;
  overflow: hidden;
}
.progress-bar__fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #06b6d4);
  border-radius: 8px;
  transition: width 0.3s ease;
}
.progress-bar__text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 600;
  color: #fff;
}

/* Actions */
.upload-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  gap: 16px;
}
.upload-estimate {
  font-size: 0.85rem;
  color: var(--text-muted, #94a3b8);
}
.btn-upload {
  background: linear-gradient(135deg, #3b82f6, #06b6d4);
  color: #fff;
  border: none;
  padding: 12px 28px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.95rem;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-upload:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.4);
}
.btn-upload:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.upload-error {
  margin-top: 12px;
  padding: 10px 16px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  color: #ef4444;
  font-size: 0.85rem;
}
</style>
