<template>
  <div class="dtable card">
    <!-- Header -->
    <div class="dtable-header">
      <h3>Lich su phat hien</h3>
      <div class="dtable-controls">
        <select v-model="filterClass" class="input input--sm" @change="loadData">
          <option value="">Tất cả loại xe</option>
          <option value="car">Xe con</option>
          <option value="truck">Xe tai</option>
          <option value="bus">Xe buyt</option>
          <option value="motorcycle">Xe may</option>
          <option value="bicycle">Xe dap</option>
        </select>
        <select v-model="filterCategory" class="input input--sm" @change="loadData">
          <option value="">Tất cả nhóm</option>
          <option value="oto">Xe ô tô</option>
          <option value="xe_may">Xe máy</option>
          <option value="xe_dap">Xe đạp</option>
        </select>
        <button class="btn btn--ghost btn--sm" @click="loadData" title="Tai lai">Reload</button>
      </div>
    </div>

    <!-- Table -->
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th style="width:50px">#</th>
            <th>Thời gian</th>
            <th>Loại xe</th>
            <th>Nhóm</th>
            <th>Confidence</th>
            <th>Camera</th>
            <th>Ảnh</th>
            <th style="width:60px">Xóa</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="8" style="text-align:center;padding:24px;">
              <span class="spinner"></span> Đang tải...
            </td>
          </tr>
          <tr v-else-if="!detections.length">
            <td colspan="8" style="text-align:center;padding:24px;color:var(--text-muted);">
              Chưa có dữ liệu phát hiện
            </td>
          </tr>
          <tr v-for="(d, idx) in detections" :key="d._id">
            <td class="mono">{{ skip + idx + 1 }}</td>
            <td class="mono">{{ formatDate(d.created_at) }}</td>
            <td>
              <span class="badge" :class="classBadge(d.vehicle_class)">
                {{ classIcon(d.vehicle_class) }} {{ classLabel(d.vehicle_class) }}
              </span>
            </td>
            <td>
              <span class="cat-label" :class="`cat--${d.category}`">
                {{ categoryLabel(d.category) }}
              </span>
            </td>
            <td class="mono">{{ d.confidence ? `${(d.confidence * 100).toFixed(0)}%` : '--' }}</td>
            <td class="mono">{{ d.camera_id || '--' }}</td>
            <td>
              <img
                v-if="d.evidence_path"
                :src="getEvUrl(d.evidence_path)"
                class="evidence-thumb"
                @click="showEvidence(d.evidence_path)"
                alt="evidence"
              />
              <span v-else class="no-img">–</span>
            </td>
            <td>
              <button class="btn btn--ghost btn--sm btn--danger-text" @click="removeItem(d._id)" title="Xóa">✕</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div class="dtable-footer" v-if="total > pageSize">
      <span class="page-info mono">
        {{ skip + 1 }}–{{ Math.min(skip + pageSize, total) }} / {{ total }}
      </span>
      <div class="page-btns">
        <button class="btn btn--ghost btn--sm" :disabled="skip === 0" @click="prevPage">← Trước</button>
        <button class="btn btn--ghost btn--sm" :disabled="skip + pageSize >= total" @click="nextPage">Sau →</button>
      </div>
    </div>

    <!-- Evidence modal -->
    <Teleport to="body">
      <div v-if="modalSrc" class="modal-overlay" @click="modalSrc = null">
        <div class="modal-card" @click.stop>
          <img :src="modalSrc" alt="evidence" class="modal-img" />
          <button class="btn btn--ghost modal-close" @click="modalSrc = null">✕</button>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { getDetections, deleteDetection, getEvidenceUrl } from '@/api/index.js'

const props = defineProps({
  autoRefresh: { type: Boolean, default: false },
  camera: { type: String, default: '' },
})

// ── State ──────────────────────────────────────────────────────
const detections     = ref([])
const loading        = ref(false)
const total          = ref(0)
const skip           = ref(0)
const pageSize       = 15
const filterClass    = ref('')
const filterCategory = ref('')
const modalSrc       = ref(null)

// ── Labels ─────────────────────────────────────────────────────
const CLASS_LABELS = { car: 'Xe con', truck: 'Xe tải', bus: 'Xe buýt', motorcycle: 'Xe máy', bicycle: 'Xe đạp' }
const CLASS_BADGES = { car: 'badge--success', truck: 'badge--warning', bus: 'badge--info', motorcycle: 'badge--danger', bicycle: 'badge--primary' }
const CLASS_ICONS  = { car: 'Car', truck: 'Truck', bus: 'Bus', motorcycle: 'Moto', bicycle: 'Bike' }
const CAT_LABELS   = { oto: 'Xe ô tô', xe_may: 'Xe máy', xe_dap: 'Xe đạp' }

function classLabel(c) { return CLASS_LABELS[c] || c }
function classBadge(c) { return CLASS_BADGES[c] || 'badge--info' }
function classIcon(c)  { return CLASS_ICONS[c] || 'Car' }
function categoryLabel(c) { return CAT_LABELS[c] || c }
function getEvUrl(p) { return getEvidenceUrl(p) }

// ── Load ───────────────────────────────────────────────────────
async function loadData() {
  loading.value = true
  try {
    const params = { skip: skip.value, limit: pageSize }
    if (filterClass.value) params.vehicle_class = filterClass.value
    if (filterCategory.value) params.category = filterCategory.value
    if (props.camera) params.camera_id = props.camera

    const res = await getDetections(params)
    detections.value = res.detections || []
    total.value = res.total || 0
  } catch (e) {
    console.error('Load detections error:', e)
  } finally {
    loading.value = false
  }
}

// ── Pagination ─────────────────────────────────────────────────
function prevPage() { skip.value = Math.max(0, skip.value - pageSize); loadData() }
function nextPage() { skip.value += pageSize; loadData() }

// ── Delete ─────────────────────────────────────────────────────
async function removeItem(id) {
  try {
    await deleteDetection(id)
    detections.value = detections.value.filter(d => d._id !== id)
    total.value = Math.max(0, total.value - 1)
  } catch (e) {
    console.error('Delete error:', e)
  }
}

// ── Modal ──────────────────────────────────────────────────────
function showEvidence(path) { modalSrc.value = getEvUrl(path) }

// ── Helpers ────────────────────────────────────────────────────
function formatDate(d) {
  if (!d) return '--'
  try {
    return new Date(d).toLocaleString('vi-VN', {
      day: '2-digit', month: '2-digit', year: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  } catch { return d }
}

// ── Auto refresh ───────────────────────────────────────────────
let refreshTimer = null
watch(() => props.autoRefresh, (v) => {
  clearInterval(refreshTimer)
  if (v) refreshTimer = setInterval(loadData, 30000)
}, { immediate: true })

onMounted(loadData)
onUnmounted(() => clearInterval(refreshTimer))

defineExpose({ loadData })
</script>

<style scoped>
.dtable {
  padding: 0;
  overflow: hidden;
}

/* Header */
.dtable-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px var(--sp-lg);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-surface);
}
.dtable-header h3 { margin: 0; font-size: 0.95rem; }
.dtable-controls { display: flex; gap: var(--sp-sm); align-items: center; }
.input--sm { padding: 5px 10px; font-size: 0.78rem; width: auto; }

/* Table */
.table-wrap { overflow-x: auto; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}
th {
  background: var(--bg-surface);
  color: var(--text-muted);
  font-weight: 600;
  text-align: left;
  padding: 8px 12px;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--border-color);
  white-space: nowrap;
}
td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color);
  white-space: nowrap;
}
tr:hover td {
  background: rgba(59,130,246,0.04);
}

/* Cat labels */
.cat-label {
  font-size: 0.72rem;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-weight: 600;
}
.cat--oto    { background: rgba(34,197,94,0.12);  color: #22c55e; }
.cat--xe_may { background: rgba(239,68,68,0.12);  color: #ef4444; }
.cat--xe_dap { background: rgba(139,92,246,0.12); color: #8b5cf6; }

/* Evidence */
.evidence-thumb {
  width: 42px; height: 30px;
  object-fit: cover;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: transform 0.2s;
  border: 1px solid var(--border-color);
}
.evidence-thumb:hover { transform: scale(1.2); }
.no-img { color: var(--text-muted); font-size: 0.7rem; }

/* Footer */
.dtable-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px var(--sp-lg);
  border-top: 1px solid var(--border-color);
  background: var(--bg-surface);
}
.page-info { font-size: 0.75rem; color: var(--text-muted); }
.page-btns { display: flex; gap: var(--sp-sm); }

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.2s;
}
.modal-card {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
}
.modal-img {
  max-width: 100%;
  max-height: 85vh;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
}
.modal-close {
  position: absolute;
  top: -12px;
  right: -12px;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #1e293b;
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.9rem;
}

.mono { font-family: var(--font-mono); }
.btn--sm { padding: 5px 10px; font-size: 0.78rem; }
.btn--danger-text { color: #ef4444; }
</style>
