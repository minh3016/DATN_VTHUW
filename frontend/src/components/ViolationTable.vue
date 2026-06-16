<template>
  <div class="violation-table card">
    <div class="table-header">
      <h3>🚨 Vi phạm gần đây</h3>
      <div class="table-actions">
        <input
          v-model="search"
          class="input"
          placeholder="Tìm biển số..."
          style="width:180px;"
        />
        <button class="btn btn--ghost btn--sm" @click="load" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          <span v-else>🔄</span>
        </button>
      </div>
    </div>

    <!-- Table -->
    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Thời gian</th>
            <th>Vi phạm</th>
            <th>Camera</th>
            <th>Biển số</th>
            <th>Loại xe</th>
            <th>Ảnh</th>
            <th>Thao tác</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="8" style="text-align:center;padding:32px;">
              <span class="spinner"></span>
            </td>
          </tr>
          <tr v-else-if="filteredData.length === 0">
            <td colspan="8" style="text-align:center;color:var(--text-muted);padding:32px;">
              Chưa có vi phạm nào
            </td>
          </tr>
          <tr v-for="(item, idx) in filteredData" :key="item._id" class="animate-fade-in">
            <td style="color:var(--text-muted);">{{ idx + 1 }}</td>
            <td class="mono" style="font-size:0.78rem;white-space:nowrap;">
              {{ formatDate(item.created_at) }}
            </td>
            <td>
              <span class="badge" :class="badgeClass(item.violation_type)">
                {{ violationLabel(item.violation_type) }}
              </span>
            </td>
            <td>
              <span class="badge badge--info">{{ item.camera_id }}</span>
            </td>
            <td class="mono">
              <span v-if="item.plate_text" class="plate-chip">{{ item.plate_text }}</span>
              <span v-else style="color:var(--text-muted);">—</span>
            </td>
            <td>
              <span class="badge badge--primary">{{ item.vehicle_class }}</span>
            </td>
            <td>
              <img
                v-if="getEvidence(item)"
                :src="getEvidence(item)"
                class="thumb"
                @click="openModal(item)"
                title="Xem ảnh"
              />
              <span v-else style="color:var(--text-muted);">—</span>
            </td>
            <td>
              <button class="btn btn--ghost btn--sm" @click="remove(item._id)" title="Xóa">🗑️</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div class="table-footer">
      <span style="color:var(--text-muted);font-size:0.85rem;">Tổng: {{ total }} vi phạm</span>
      <div class="pagination">
        <button class="btn btn--ghost btn--sm" @click="prevPage" :disabled="page === 0">←</button>
        <span style="color:var(--text-secondary);font-size:0.85rem;">Trang {{ page + 1 }}</span>
        <button class="btn btn--ghost btn--sm" @click="nextPage" :disabled="(page + 1) * pageSize >= total">→</button>
      </div>
    </div>

    <!-- Image Modal -->
    <div v-if="modalItem" class="modal-overlay" @click.self="modalItem = null">
      <div class="modal-content">
        <div class="modal-header">
          <h4>Chi tiết vi phạm</h4>
          <button class="btn btn--ghost btn--sm" @click="modalItem = null">✕</button>
        </div>
        <img
          v-if="getEvidence(modalItem)"
          :src="getEvidence(modalItem)"
          style="width:100%;border-radius:var(--radius-md);"
        />
        <div class="modal-info">
          <div class="info-row">
            <span>Vi phạm:</span>
            <span class="badge" :class="badgeClass(modalItem.violation_type)">{{ violationLabel(modalItem.violation_type) }}</span>
          </div>
          <div class="info-row">
            <span>Biển số:</span>
            <span class="plate-chip mono">{{ modalItem.plate_text || 'Không xác định' }}</span>
          </div>
          <div class="info-row">
            <span>Thời gian:</span>
            <span class="mono">{{ formatDate(modalItem.created_at) }}</span>
          </div>
          <div class="info-row">
            <span>Camera:</span>
            <span>{{ modalItem.camera_id }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { getViolations, deleteViolation, getEvidenceUrl } from '@/api/index.js'
import { format } from 'date-fns'
import { vi } from 'date-fns/locale'

const props = defineProps({
  autoRefresh: { type: Boolean, default: false },
  refreshInterval: { type: Number, default: 30000 }, // 30 giây – giảm tải server
})

const violations = ref([])
const total = ref(0)
const loading = ref(false)
const search = ref('')
const page = ref(0)
const pageSize = 20
const modalItem = ref(null)

const filteredData = computed(() => {
  if (!search.value) return violations.value
  const q = search.value.toLowerCase()
  return violations.value.filter(v =>
    (v.plate_text || '').toLowerCase().includes(q) ||
    (v.camera_id || '').toLowerCase().includes(q)
  )
})

async function load() {
  loading.value = true
  try {
    const res = await getViolations({ skip: page.value * pageSize, limit: pageSize })
    violations.value = res.data || []
    total.value = res.total || 0
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function remove(id) {
  if (!confirm('Xóa vi phạm này?')) return
  try {
    await deleteViolation(id)
    await load()
  } catch (e) {
    alert(e.message)
  }
}

function prevPage() {
  if (page.value > 0) { page.value--; load() }
}
function nextPage() {
  if ((page.value + 1) * pageSize < total.value) { page.value++; load() }
}

function formatDate(iso) {
  try { return format(new Date(iso), 'dd/MM/yy HH:mm:ss', { locale: vi }) }
  catch { return iso }
}

function violationLabel(type) {
  const map = {
    no_helmet: '🪖 Không MBH',
    wrong_lane: '⚠️ Sai làn',
    red_light: '🔴 Vượt đèn đỏ',
    speeding: '⚡ Tốc độ cao',
  }
  return map[type] || type
}

function badgeClass(type) {
  const map = {
    no_helmet: 'badge--danger',
    wrong_lane: 'badge--warning',
    red_light: 'badge--danger',
    speeding: 'badge--warning',
  }
  return map[type] || 'badge--info'
}

function getEvidence(item) {
  if (!item) return ''
  // v2: evidence stored as file path on disk
  if (item.evidence_path) return getEvidenceUrl(item.evidence_path)
  // Legacy: base64 embedded
  if (item.frame_base64) return `data:image/jpeg;base64,${item.frame_base64}`
  return ''
}

function openModal(item) { modalItem.value = item }

// Public: add violation from stream or trigger reload from parent
defineExpose({
  load,
  addViolation(v) { violations.value.unshift(v); total.value++ }
})

// Auto-refresh với cleanup đúng cách
let timer = null
watch(() => props.autoRefresh, (v) => {
  clearInterval(timer)
  timer = null
  if (v) timer = setInterval(load, props.refreshInterval)
}, { immediate: true })

onMounted(load)
onUnmounted(() => { clearInterval(timer); timer = null })
</script>

<style scoped>
.violation-table { padding: 0; overflow: hidden; }

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-md) var(--sp-lg);
  border-bottom: 1px solid var(--border-color);
}
.table-header h3 { margin: 0; font-size: 1rem; }
.table-actions { display: flex; gap: var(--sp-sm); align-items: center; }

.table-wrapper { overflow-x: auto; max-height: 400px; overflow-y: auto; }

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-sm) var(--sp-lg);
  border-top: 1px solid var(--border-color);
  background: var(--bg-surface);
}
.pagination { display: flex; align-items: center; gap: var(--sp-sm); }

.thumb {
  width: 60px;
  height: 40px;
  object-fit: cover;
  border-radius: var(--radius-sm);
  cursor: pointer;
  border: 1px solid var(--border-color);
  transition: transform var(--transition-fast);
}
.thumb:hover { transform: scale(1.05); }

.plate-chip {
  background: rgba(59,130,246,0.1);
  color: var(--text-accent);
  border: 1px solid rgba(59,130,246,0.3);
  border-radius: var(--radius-sm);
  padding: 2px 8px;
  font-size: 0.8rem;
  font-family: var(--font-mono);
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}
.modal-content {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  padding: var(--sp-lg);
  max-width: 640px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  animation: fadeIn 0.2s ease;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-md);
}
.modal-header h4 { margin: 0; }
.modal-info {
  margin-top: var(--sp-md);
  display: flex;
  flex-direction: column;
  gap: var(--sp-sm);
}
.info-row {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  font-size: 0.875rem;
  color: var(--text-secondary);
}
.info-row span:first-child { width: 90px; color: var(--text-muted); }

.btn--sm { padding: 6px 10px; font-size: 0.8rem; }
</style>
