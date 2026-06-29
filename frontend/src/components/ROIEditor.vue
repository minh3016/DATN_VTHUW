<template>
  <div class="roi-editor" v-if="showEditor">
    <div class="roi-header">
      <h4>Cau hinh vach dung (Stop Line)</h4>
      <button class="btn-close" @click="$emit('close')">✕</button>
    </div>

    <div class="roi-body">
      <!-- Canvas overlay -->
      <div class="roi-canvas-wrap" ref="canvasWrap">
        <canvas
          ref="canvas"
          :width="canvasWidth"
          :height="canvasHeight"
          @click="handleCanvasClick"
        ></canvas>
        <div class="roi-hint">
          Click để đặt vạch dừng (đường ngang).
          Y = {{ stopLineY }}px
        </div>
      </div>

      <!-- Config controls -->
      <div class="roi-controls">
        <div class="control-group">
          <label>Vạch dừng Y:</label>
          <input type="range" v-model.number="stopLineY" :min="50" :max="canvasHeight - 50" />
          <span class="control-val">{{ stopLineY }}px</span>
        </div>

        <div class="control-group">
          <label>Số lane:</label>
          <select v-model.number="numLanes">
            <option :value="2">2 lane</option>
            <option :value="3">3 lane</option>
            <option :value="4">4 lane</option>
          </select>
        </div>

        <div class="control-group">
          <label>Hướng di chuyển:</label>
          <select v-model="direction">
            <option value="bottom_to_top">↑ Dưới → Trên</option>
            <option value="top_to_bottom">↓ Trên → Dưới</option>
          </select>
        </div>

        <div class="control-group">
          <label>Camera ID:</label>
          <input type="text" v-model="cameraId" placeholder="CAM_01" />
        </div>

        <button class="btn-save" @click="saveConfig">
          Luu cau hinh
        </button>

        <div v-if="saveStatus" class="save-status" :class="saveStatus">
          {{ saveStatus === 'success' ? 'Da luu!' : 'Loi luu' }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import { saveROIConfig, getROIConfig } from '@/api/index.js'

const props = defineProps({
  showEditor: { type: Boolean, default: false },
  initialCameraId: { type: String, default: 'CAM_01' },
})

const emit = defineEmits(['close', 'saved'])

const canvas = ref(null)
const canvasWrap = ref(null)
const canvasWidth = ref(640)
const canvasHeight = ref(360)

const stopLineY = ref(250)
const numLanes = ref(3)
const direction = ref('bottom_to_top')
const cameraId = ref(props.initialCameraId)
const saveStatus = ref('')

// Draw the stop line on canvas
function drawCanvas() {
  const ctx = canvas.value?.getContext('2d')
  if (!ctx) return

  ctx.clearRect(0, 0, canvasWidth.value, canvasHeight.value)

  // Background grid
  ctx.strokeStyle = 'rgba(100, 116, 139, 0.2)'
  ctx.lineWidth = 1
  for (let y = 0; y < canvasHeight.value; y += 40) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(canvasWidth.value, y)
    ctx.stroke()
  }

  // Stop line
  ctx.strokeStyle = '#ef4444'
  ctx.lineWidth = 3
  ctx.setLineDash([10, 5])
  ctx.beginPath()
  ctx.moveTo(0, stopLineY.value)
  ctx.lineTo(canvasWidth.value, stopLineY.value)
  ctx.stroke()
  ctx.setLineDash([])

  // Label
  ctx.fillStyle = '#ef4444'
  ctx.font = 'bold 12px Inter, sans-serif'
  ctx.fillText(`STOP LINE (y=${stopLineY.value})`, 8, stopLineY.value - 8)

  // Lane dividers
  const laneW = canvasWidth.value / numLanes.value
  ctx.strokeStyle = 'rgba(59, 130, 246, 0.5)'
  ctx.lineWidth = 1
  ctx.setLineDash([5, 5])
  for (let i = 1; i < numLanes.value; i++) {
    ctx.beginPath()
    ctx.moveTo(i * laneW, 0)
    ctx.lineTo(i * laneW, canvasHeight.value)
    ctx.stroke()
  }
  ctx.setLineDash([])

  // Direction arrow
  const arrowX = canvasWidth.value / 2
  ctx.fillStyle = 'rgba(34, 197, 94, 0.8)'
  ctx.font = '24px sans-serif'
  if (direction.value === 'bottom_to_top') {
    ctx.fillText('↑', arrowX - 8, canvasHeight.value - 20)
  } else {
    ctx.fillText('↓', arrowX - 8, 30)
  }
}

function handleCanvasClick(e) {
  const rect = canvas.value.getBoundingClientRect()
  const scaleY = canvasHeight.value / rect.height
  stopLineY.value = Math.round((e.clientY - rect.top) * scaleY)
}

async function saveConfig() {
  try {
    const config = {
      camera_id: cameraId.value,
      stop_line_y: stopLineY.value,
      num_lanes: numLanes.value,
      direction: direction.value,
    }
    await saveROIConfig(config)
    saveStatus.value = 'success'
    emit('saved', config)
    setTimeout(() => { saveStatus.value = '' }, 2000)
  } catch (err) {
    saveStatus.value = 'error'
    setTimeout(() => { saveStatus.value = '' }, 2000)
  }
}

async function loadConfig() {
  try {
    const config = await getROIConfig(cameraId.value)
    if (config) {
      stopLineY.value = config.stop_line_y || 250
      numLanes.value = config.num_lanes || 3
      direction.value = config.direction || 'bottom_to_top'
    }
  } catch { /* use defaults */ }
}

watch([stopLineY, numLanes, direction], drawCanvas)
watch(() => props.showEditor, async (val) => {
  if (val) {
    await loadConfig()
    await nextTick()
    drawCanvas()
  }
})

onMounted(() => {
  if (props.showEditor) {
    loadConfig()
    nextTick(drawCanvas)
  }
})
</script>

<style scoped>
.roi-editor {
  background: var(--bg-surface, #1e293b);
  border: 1px solid var(--border-color, #334155);
  border-radius: var(--radius-lg, 12px);
  overflow: hidden;
}

.roi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(59, 130, 246, 0.1);
  border-bottom: 1px solid var(--border-color, #334155);
}
.roi-header h4 {
  margin: 0;
  font-size: 0.95rem;
  color: var(--text-primary, #e2e8f0);
}
.btn-close {
  background: none;
  border: none;
  color: var(--text-muted, #94a3b8);
  font-size: 1.2rem;
  cursor: pointer;
}

.roi-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.roi-canvas-wrap {
  position: relative;
}
.roi-canvas-wrap canvas {
  width: 100%;
  height: auto;
  background: #0f172a;
  border-radius: 8px;
  cursor: crosshair;
}
.roi-hint {
  font-size: 0.75rem;
  color: var(--text-muted, #94a3b8);
  margin-top: 4px;
}

.roi-controls {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.control-group {
  display: flex;
  align-items: center;
  gap: 10px;
}
.control-group label {
  min-width: 130px;
  font-size: 0.85rem;
  color: var(--text-secondary, #cbd5e1);
}
.control-group input[type="range"] {
  flex: 1;
  accent-color: var(--accent-primary, #3b82f6);
}
.control-group input[type="text"],
.control-group select {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid var(--border-color, #334155);
  border-radius: 6px;
  background: var(--bg-primary, #0f172a);
  color: var(--text-primary, #e2e8f0);
  font-size: 0.85rem;
}
.control-val {
  min-width: 50px;
  text-align: right;
  font-size: 0.8rem;
  color: var(--accent-primary, #3b82f6);
  font-weight: 600;
}

.btn-save {
  background: linear-gradient(135deg, #22c55e, #16a34a);
  color: #fff;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-save:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.3);
}

.save-status {
  font-size: 0.85rem;
  text-align: center;
}
.save-status.success { color: #22c55e; }
.save-status.error { color: #ef4444; }
</style>
