<template>
  <div v-if="isOpen" class="modal-backdrop" @click.self="close">
    <div class="modal-card">
      <div class="modal-header">
        <h3 class="modal-title">
          <span class="icon">🚦</span> Cấu hình Vạch Dừng & Đèn Giao Thông ({{ sourceId }})
        </h3>
        <button class="close-btn" @click="close">&times;</button>
      </div>

      <div class="modal-body">
        <div v-if="loading" class="loading-state">
          <div class="spinner"></div>
          <p>Đang tải cấu hình...</p>
        </div>

        <div v-else class="config-content">
          <div class="control-row toggle-row">
            <label class="toggle-label">
              <input type="checkbox" v-model="config.enabled" />
              <span class="toggle-text">Kích hoạt phát hiện vi phạm Vượt Đèn Đỏ</span>
            </label>
          </div>

          <div class="interactive-preview">
            <div class="preview-container" ref="containerRef" @mousedown="handleMouseDown" @mousemove="handleMouseMove" @mouseup="handleMouseUp">
              <img v-if="previewImage" :src="previewImage" class="preview-img" alt="Preview Frame" />
              <div v-else class="placeholder-box">
                <span class="ph-text">Bản đồ cấu hình tỉ lệ (0.0 -> 1.0)</span>
              </div>

              <!-- SVG Overlay for Line & ROI drawing -->
              <svg class="overlay-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
                <!-- Traffic Light ROI Box -->
                <rect
                  :x="config.traffic_light_roi_ratio[0] * 100"
                  :y="config.traffic_light_roi_ratio[1] * 100"
                  :(width)="(config.traffic_light_roi_ratio[2] - config.traffic_light_roi_ratio[0]) * 100"
                  :(height)="(config.traffic_light_roi_ratio[3] - config.traffic_light_roi_ratio[1]) * 100"
                  fill="rgba(255, 200, 0, 0.2)"
                  stroke="#ffc800"
                  stroke-width="1.5"
                  stroke-dasharray="3,3"
                />
                <text
                  :x="config.traffic_light_roi_ratio[0] * 100 + 2"
                  :y="config.traffic_light_roi_ratio[1] * 100 + 8"
                  fill="#ffc800"
                  font-size="4"
                  font-weight="bold"
                >ROI ĐÈN</text>

                <!-- Stopping Line -->
                <line
                  :x1="config.stopping_line_ratio[0][0] * 100"
                  :y1="config.stopping_line_ratio[0][1] * 100"
                  :x2="config.stopping_line_ratio[1][0] * 100"
                  :y2="config.stopping_line_ratio[1][1] * 100"
                  stroke="#ff3b30"
                  stroke-width="2.5"
                />
                <circle
                  :cx="config.stopping_line_ratio[0][0] * 100"
                  :cy="config.stopping_line_ratio[0][1] * 100"
                  r="3"
                  fill="#ff3b30"
                />
                <circle
                  :cx="config.stopping_line_ratio[1][0] * 100"
                  :cy="config.stopping_line_ratio[1][1] * 100"
                  r="3"
                  fill="#ff3b30"
                />
                <text
                  :x="((config.stopping_line_ratio[0][0] + config.stopping_line_ratio[1][0]) / 2) * 100 - 12"
                  :y="((config.stopping_line_ratio[0][1] + config.stopping_line_ratio[1][1]) / 2) * 100 - 3"
                  fill="#ff3b30"
                  font-size="4.5"
                  font-weight="bold"
                >VACH DUNG</text>
              </svg>
            </div>
            <p class="hint-text">💡 Kéo thả chuột trên vùng xem trước để tùy chỉnh Vạch Dừng và Vùng ROI Đèn giao thông.</p>
          </div>

          <div class="inputs-grid">
            <div class="input-section">
              <h4>🔴 Vạch Dừng (Stopping Line)</h4>
              <div class="coord-inputs">
                <div class="coord-group">
                  <label>Điểm 1 (X1, Y1):</label>
                  <input type="number" step="0.01" min="0" max="1" v-model.number="config.stopping_line_ratio[0][0]" />
                  <input type="number" step="0.01" min="0" max="1" v-model.number="config.stopping_line_ratio[0][1]" />
                </div>
                <div class="coord-group">
                  <label>Điểm 2 (X2, Y2):</label>
                  <input type="number" step="0.01" min="0" max="1" v-model.number="config.stopping_line_ratio[1][0]" />
                  <input type="number" step="0.01" min="0" max="1" v-model.number="config.stopping_line_ratio[1][1]" />
                </div>
              </div>
            </div>

            <div class="input-section">
              <h4>🟡 Vùng ROI Đèn Giao Thông</h4>
              <div class="coord-inputs">
                <div class="coord-group">
                  <label>Top-Left (X1, Y1):</label>
                  <input type="number" step="0.01" min="0" max="1" v-model.number="config.traffic_light_roi_ratio[0]" />
                  <input type="number" step="0.01" min="0" max="1" v-model.number="config.traffic_light_roi_ratio[1]" />
                </div>
                <div class="coord-group">
                  <label>Bottom-Right (X2, Y2):</label>
                  <input type="number" step="0.01" min="0" max="1" v-model.number="config.traffic_light_roi_ratio[2]" />
                  <input type="number" step="0.01" min="0" max="1" v-model.number="config.traffic_light_roi_ratio[3]" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn btn-secondary" @click="close">Hủy</button>
        <button class="btn btn-primary" :disabled="saving" @click="handleSave">
          <span v-if="saving">Đang lưu...</span>
          <span v-else>Lưu Cấu Hình</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, reactive } from 'vue'
import { getRedLightConfig, saveRedLightConfig } from '../api'

const props = defineProps({
  isOpen: Boolean,
  sourceId: { type: String, default: 'CAM_01' },
  previewImage: { type: String, default: '' }
})

const emit = defineEmits(['close', 'saved'])

const loading = ref(false)
const saving = ref(false)
const containerRef = ref(null)

const config = reactive({
  source_id: 'CAM_01',
  stopping_line_ratio: [[0.05, 0.65], [0.95, 0.65]],
  traffic_light_roi_ratio: [0.65, 0.02, 0.98, 0.45],
  enabled: true
})

watch(() => props.isOpen, async (newVal) => {
  if (newVal) {
    await fetchConfig()
  }
})

const fetchConfig = async () => {
  loading.value = true
  try {
    const res = await getRedLightConfig(props.sourceId)
    if (res) {
      config.source_id = res.source_id || props.sourceId
      config.stopping_line_ratio = res.stopping_line_ratio || [[0.05, 0.65], [0.95, 0.65]]
      config.traffic_light_roi_ratio = res.traffic_light_roi_ratio || [0.65, 0.02, 0.98, 0.45]
      config.enabled = res.enabled !== undefined ? res.enabled : true
    }
  } catch (err) {
    console.error("Lỗi khi tải cấu hình đèn đỏ:", err)
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    config.source_id = props.sourceId
    await saveRedLightConfig(config)
    emit('saved', { ...config })
    close()
  } catch (err) {
    alert("Lưu cấu hình thất bại: " + err.message)
  } finally {
    saving.value = false
  }
}

const close = () => {
  emit('close')
}

// Interactivity helpers for dragging line endpoints
let isDragging = false
let dragTarget = null

const handleMouseDown = (e) => {
  if (!containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  const clickX = (e.clientX - rect.left) / rect.width
  const clickY = (e.clientY - rect.top) / rect.height

  // Dist to Line Endpoints
  const d1 = Math.hypot(clickX - config.stopping_line_ratio[0][0], clickY - config.stopping_line_ratio[0][1])
  const d2 = Math.hypot(clickX - config.stopping_line_ratio[1][0], clickY - config.stopping_line_ratio[1][1])

  if (d1 < 0.08) {
    isDragging = true
    dragTarget = 'p1'
  } else if (d2 < 0.08) {
    isDragging = true
    dragTarget = 'p2'
  }
}

const handleMouseMove = (e) => {
  if (!isDragging || !containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  const curX = Math.min(Math.max(0, (e.clientX - rect.left) / rect.width), 1)
  const curY = Math.min(Math.max(0, (e.clientY - rect.top) / rect.height), 1)

  if (dragTarget === 'p1') {
    config.stopping_line_ratio[0][0] = Number(curX.toFixed(2))
    config.stopping_line_ratio[0][1] = Number(curY.toFixed(2))
  } else if (dragTarget === 'p2') {
    config.stopping_line_ratio[1][0] = Number(curX.toFixed(2))
    config.stopping_line_ratio[1][1] = Number(curY.toFixed(2))
  }
}

const handleMouseUp = () => {
  isDragging = false
  dragTarget = null
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(10, 14, 23, 0.82);
  backdrop-filter: blur(6px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-card {
  background: #141b2d;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  width: 90%;
  max-width: 720px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
}

.modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-title {
  font-size: 1.15rem;
  font-weight: 600;
  margin: 0;
  color: #f8fafc;
}

.close-btn {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 1.5rem;
  cursor: pointer;
}
.close-btn:hover { color: #fff; }

.modal-body {
  padding: 20px;
  max-height: 75vh;
  overflow-y: auto;
}

.toggle-row {
  margin-bottom: 16px;
}
.toggle-label {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-weight: 500;
}
.toggle-label input {
  width: 18px;
  height: 18px;
  accent-color: #3b82f6;
}

.interactive-preview {
  margin-bottom: 20px;
}

.preview-container {
  position: relative;
  width: 100%;
  aspect-ratio: 16/9;
  background: #0f172a;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.1);
  cursor: crosshair;
}

.preview-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.placeholder-box {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  font-size: 0.9rem;
}

.overlay-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.hint-text {
  font-size: 0.8rem;
  color: #94a3b8;
  margin-top: 6px;
}

.inputs-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.input-section {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 12px;
}

.input-section h4 {
  margin: 0 0 10px 0;
  font-size: 0.9rem;
  color: #cbd5e1;
}

.coord-inputs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.coord-group {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
}
.coord-group label { width: 110px; color: #94a3b8; }
.coord-group input {
  width: 65px;
  padding: 4px 6px;
  background: #0f172a;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  color: #fff;
  font-size: 0.82rem;
}

.modal-footer {
  padding: 14px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  border: none;
}
.btn-secondary { background: rgba(255, 255, 255, 0.1); color: #cbd5e1; }
.btn-secondary:hover { background: rgba(255, 255, 255, 0.18); }
.btn-primary { background: #2563eb; color: #fff; }
.btn-primary:hover { background: #1d4ed8; }

.loading-state {
  text-align: center;
  padding: 30px;
}
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(255, 255, 255, 0.1);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 10px auto;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
