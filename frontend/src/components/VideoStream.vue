<template>
  <div class="video-stream">
    <!-- Header -->
    <div class="stream-header">
      <div class="stream-title">
        <span class="status-dot" :class="statusDotClass"></span>
        <h3>{{ cameraId }}</h3>
        <span class="badge" :class="statusBadgeClass">{{ statusLabel }}</span>
      </div>
      <div class="stream-actions">
        <span v-if="frameData?.fps" class="fps-badge">{{ frameData.fps?.toFixed(1) }} FPS</span>
        <button class="btn btn--ghost btn--sm" @click="toggleFullscreen" title="Toàn màn hình">⛶</button>
      </div>
    </div>

    <!-- Controls: URL input + Test + Start/Stop -->
    <div class="stream-controls">
      <select v-model="sourceType" class="input source-select" :disabled="isStreaming">
        <option value="esp32">📡 ESP32 MJPEG</option>
        <option value="file">📂 Video file</option>
        <option value="webcam">🎥 Webcam</option>
      </select>

      <!-- ESP32 MJPEG URL -->
      <div v-if="sourceType === 'esp32'" class="url-group">
        <input
          v-model="mjpegUrl"
          class="input url-input"
          placeholder="http://192.168.x.x/stream"
          :disabled="isStreaming"
          @keydown.enter="!isStreaming && toggleStream()"
        />
        <button
          class="btn btn--ghost btn--sm"
          @click="testConnection"
          :disabled="isStreaming || testing"
          title="Test kết nối ESP32"
        >
          <span v-if="testing" class="spinner"></span>
          <span v-else>🔌</span>
        </button>
      </div>

      <!-- Video file path -->
      <input
        v-else-if="sourceType === 'file'"
        v-model="filePath"
        class="input url-input"
        placeholder="Đường dẫn file video hoặc URL..."
        :disabled="isStreaming"
      />

      <!-- Webcam info -->
      <span v-else class="source-hint">Camera mặc định (index 0)</span>

      <button
        class="btn"
        :class="isStreaming ? 'btn--danger' : 'btn--success'"
        @click="toggleStream"
        :disabled="connecting"
        id="stream-toggle-btn"
      >
        <span v-if="connecting" class="spinner"></span>
        <span v-else>{{ isStreaming ? '⏹ Dừng' : '▶ Bắt đầu' }}</span>
      </button>
    </div>

    <!-- Test connection result -->
    <div v-if="testResult" class="test-result" :class="testResult.ok ? 'test-ok' : 'test-fail'">
      {{ testResult.ok ? '✅' : '❌' }} {{ testResult.message }}
    </div>

    <!-- Reconnecting overlay -->
    <div v-if="reconnecting" class="reconnect-banner">
      <span class="spinner"></span> Đang kết nối lại ESP32...
    </div>

    <!-- Frame display -->
    <div class="stream-canvas" ref="canvasContainer">
      <img
        v-if="currentFrame"
        :src="`data:image/jpeg;base64,${currentFrame}`"
        class="stream-img"
        alt="Camera feed"
      />
      <div v-else class="stream-placeholder">
        <div class="placeholder-icon">
          {{ sourceType === 'esp32' ? '📡' : '📷' }}
        </div>
        <p v-if="!isStreaming">
          {{ sourceType === 'esp32' ? 'Nhập URL ESP32 và nhấn Bắt đầu' : 'Nhấn Bắt đầu để xem camera' }}
        </p>
        <p v-else>Đang chờ frame từ {{ sourceType === 'esp32' ? 'ESP32' : 'camera' }}...</p>
      </div>

      <!-- Live stats overlay (vehicle counts) -->
      <div v-if="isStreaming && frameData" class="stream-overlay">
        <div class="overlay-stat">
          <span class="overlay-label">FPS</span>
          <span class="overlay-val">{{ frameData.fps?.toFixed(1) || '--' }}</span>
        </div>
        <div class="overlay-stat">
          <span class="overlay-label">Tổng xe</span>
          <span class="overlay-val">{{ frameData.vehicle_count || 0 }}</span>
        </div>
        <div v-for="(cnt, cat) in (frameData.counts_by_category || {})" :key="cat" class="overlay-stat" :class="`overlay-stat--${cat}`">
          <span class="overlay-label">{{ catLabel(cat) }}</span>
          <span class="overlay-val">{{ cnt }}</span>
        </div>
      </div>
    </div>

    <!-- Vehicle counts bar -->
    <div v-if="frameData?.counts_by_class && Object.keys(frameData.counts_by_class).length" class="counts-bar">
      <span class="counts-label">🚗 Phân loại:</span>
      <span v-for="(cnt, cls) in frameData.counts_by_class" :key="cls" class="badge" :class="classBadge(cls)">
        {{ classIcon(cls) }} {{ classLabel(cls) }}: {{ cnt }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { createWebSocket, addCamera, removeCamera } from '@/api/index.js'

const props = defineProps({
  cameraId: { type: String, default: 'ESP32_01' },
})
const emit = defineEmits(['frame-result', 'stream-change'])

// ── Labels ──────────────────────────────────────────────────────
const CLASS_LABELS = { car: 'Xe con', truck: 'Xe tải', bus: 'Xe buýt', motorcycle: 'Xe máy', bicycle: 'Xe đạp' }
const CLASS_BADGES = { car: 'badge--success', truck: 'badge--warning', bus: 'badge--info', motorcycle: 'badge--danger', bicycle: 'badge--primary' }
const CLASS_ICONS  = { car: '🚙', truck: '🚛', bus: '🚌', motorcycle: '🏍️', bicycle: '🚲' }
const CAT_LABELS   = { oto: 'Ô tô', xe_may: 'Xe máy', xe_dap: 'Xe đạp' }

function classLabel(c) { return CLASS_LABELS[c] || c }
function classBadge(c) { return CLASS_BADGES[c] || 'badge--info' }
function classIcon(c) { return CLASS_ICONS[c] || '🚗' }
function catLabel(c) { return CAT_LABELS[c] || c }

// ── State ──────────────────────────────────────────────────────
const sourceType = ref('esp32')
const mjpegUrl   = ref('')
const filePath   = ref('')
const isStreaming = ref(false)
const connecting  = ref(false)
const reconnecting = ref(false)
const currentFrame = ref(null)
const frameData    = ref(null)
const canvasContainer = ref(null)
const testing    = ref(false)
const testResult = ref(null)

let ws = null

// ── Computed ───────────────────────────────────────────────────
const statusDotClass = computed(() => ({
  'status-dot--live':        isStreaming.value && !reconnecting.value,
  'status-dot--reconnecting': reconnecting.value,
  'status-dot--offline':     !isStreaming.value,
}))

const statusBadgeClass = computed(() => {
  if (reconnecting.value) return 'badge--warning'
  if (isStreaming.value)  return 'badge--danger'
  return 'badge--info'
})

const statusLabel = computed(() => {
  if (reconnecting.value) return '⟳ RECONNECTING'
  if (isStreaming.value)  return '● LIVE'
  return 'STANDBY'
})

// ── Source URL ─────────────────────────────────────────────────
function getSource() {
  if (sourceType.value === 'esp32')  return mjpegUrl.value || 'http://192.168.1.100/stream'
  if (sourceType.value === 'file')   return filePath.value
  if (sourceType.value === 'webcam') return '0'
  return '0'
}

// ── Test kết nối ESP32 ─────────────────────────────────────────
async function testConnection() {
  if (!mjpegUrl.value) {
    testResult.value = { ok: false, message: 'Vui lòng nhập URL ESP32' }
    return
  }
  testing.value = true
  testResult.value = null

  try {
    const base = mjpegUrl.value.replace(/\/stream$/, '')
    const res = await fetch(`${base}/status`, { signal: AbortSignal.timeout(4000) })
    if (res.ok) {
      testResult.value = { ok: true, message: `ESP32 online! (${new URL(base).hostname})` }
    } else {
      const res2 = await fetch(`${base}/capture`, { signal: AbortSignal.timeout(4000) })
      testResult.value = res2.ok
        ? { ok: true, message: 'ESP32 phản hồi (capture endpoint)' }
        : { ok: false, message: `HTTP ${res2.status} – Kiểm tra lại URL` }
    }
  } catch (e) {
    testResult.value = { ok: false, message: `Không kết nối được: ${e.message}` }
  } finally {
    testing.value = false
    setTimeout(() => { testResult.value = null }, 5000)
  }
}

// ── Stream control ─────────────────────────────────────────────
async function toggleStream() {
  if (isStreaming.value) {
    await stopCurrentStream()
  } else {
    await startCurrentStream()
  }
}

async function startCurrentStream() {
  connecting.value = true
  testResult.value = null

  try {
    ws = createWebSocket(props.cameraId)

    ws.onopen = async () => {
      await addCamera(getSource(), props.cameraId, null, 2)
      isStreaming.value = true
      connecting.value = false
      emit('stream-change', true)
    }

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)

      if (msg.type === 'frame_result') {
        frameData.value  = msg.data
        currentFrame.value = msg.data.frame_base64 || null
        reconnecting.value = false
        emit('frame-result', msg.data)
      } else if (msg.type === 'stream_ended') {
        isStreaming.value  = false
        reconnecting.value = false
        currentFrame.value = null
        emit('stream-change', false)
      } else if (msg.type === 'camera_status') {
        if (msg.data.status === 'reconnecting') reconnecting.value = true
        if (msg.data.status === 'live')         reconnecting.value = false
        if (msg.data.status === 'offline')      { isStreaming.value = false; emit('stream-change', false) }
      }
    }

    ws.onerror = () => {
      connecting.value   = false
      reconnecting.value = false
    }
    ws.onclose = () => {
      if (isStreaming.value) reconnecting.value = true
    }
  } catch (e) {
    connecting.value = false
    console.error('Stream error:', e)
  }
}

async function stopCurrentStream() {
  try {
    await removeCamera(props.cameraId)
  } catch {}
  if (ws) { ws.close(); ws = null }
  isStreaming.value  = false
  reconnecting.value = false
  currentFrame.value = null
  frameData.value    = null
  emit('stream-change', false)
}

function toggleFullscreen() {
  const el = canvasContainer.value
  if (!el) return
  if (!document.fullscreenElement) el.requestFullscreen?.()
  else document.exitFullscreen?.()
}

onUnmounted(() => {
  if (isStreaming.value) stopCurrentStream()
})
</script>

<style scoped>
.video-stream {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Header */
.stream-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px var(--sp-md);
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-color);
}
.stream-title { display: flex; align-items: center; gap: var(--sp-sm); }
.stream-title h3 { font-size: 0.95rem; margin: 0; }
.stream-actions { display: flex; align-items: center; gap: var(--sp-sm); }

.fps-badge {
  font-size: 0.72rem;
  font-family: var(--font-mono);
  color: var(--text-muted);
  background: rgba(99,102,241,0.12);
  border: 1px solid rgba(99,102,241,0.25);
  border-radius: var(--radius-full);
  padding: 2px 8px;
}

/* Status dots */
.status-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot--live         { background: #10b981; box-shadow: 0 0 6px #10b981; animation: pulse 1.5s infinite; }
.status-dot--reconnecting { background: #f59e0b; box-shadow: 0 0 6px #f59e0b; animation: pulse 0.8s infinite; }
.status-dot--offline      { background: #64748b; }
@keyframes pulse {
  0%, 100% { opacity: 1; } 50% { opacity: 0.4; }
}

/* Controls */
.stream-controls {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  padding: var(--sp-sm) var(--sp-md);
  background: var(--bg-base);
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
}
.source-select { width: 150px; flex-shrink: 0; }
.url-group { display: flex; align-items: center; gap: 4px; flex: 1; min-width: 0; }
.url-input { flex: 1; min-width: 0; font-size: 0.85rem; font-family: var(--font-mono); }
.source-hint { flex: 1; color: var(--text-muted); font-size: 0.82rem; }
.btn--sm { padding: 6px 10px; font-size: 0.8rem; }

/* Test result */
.test-result {
  padding: 6px var(--sp-md);
  font-size: 0.8rem;
  border-bottom: 1px solid var(--border-color);
}
.test-ok   { background: rgba(16,185,129,0.1); color: #10b981; }
.test-fail { background: rgba(239,68,68,0.1);  color: #ef4444; }

/* Reconnect banner */
.reconnect-banner {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  padding: 6px var(--sp-md);
  background: rgba(245,158,11,0.1);
  border-bottom: 1px solid rgba(245,158,11,0.3);
  color: #f59e0b;
  font-size: 0.82rem;
}

/* Canvas */
.stream-canvas {
  position: relative;
  background: #000;
  min-height: 340px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.stream-img {
  width: 100%; height: auto;
  display: block;
  max-height: 500px;
  object-fit: contain;
}

/* Placeholder */
.stream-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-md);
  color: var(--text-muted);
  padding: var(--sp-2xl);
}
.placeholder-icon { font-size: 3rem; opacity: 0.5; }

/* Overlay stats */
.stream-overlay {
  position: absolute;
  top: var(--sp-sm);
  right: var(--sp-sm);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.overlay-stat {
  background: rgba(0,0,0,0.72);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  backdrop-filter: blur(4px);
}
.overlay-stat--oto    { border-color: rgba(34,197,94,0.5); }
.overlay-stat--xe_may { border-color: rgba(239,68,68,0.5); }
.overlay-stat--xe_dap { border-color: rgba(139,92,246,0.5); }
.overlay-label { font-size: 0.68rem; color: var(--text-muted); }
.overlay-val   { font-size: 0.9rem; font-weight: 700; color: #fff; font-family: var(--font-mono); }

/* Vehicle counts bar */
.counts-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--sp-xs);
  padding: var(--sp-sm) var(--sp-md);
  background: var(--bg-base);
  border-top: 1px solid var(--border-color);
  font-size: 0.8rem;
}
.counts-label { color: var(--text-muted); margin-right: var(--sp-xs); }
</style>
