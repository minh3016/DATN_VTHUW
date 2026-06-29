<template>
  <div class="violation-history">
    <div class="page-header">
      <h1>⚠️ Lịch sử vi phạm giao thông</h1>
      <p class="page-desc">Danh sách các vi phạm giao thông đã phát hiện</p>
    </div>

    <!-- Stats Cards -->
    <div class="stats-row">
      <div class="stat-card stat-card--danger">
        <div class="stat-value">{{ totalViolations }}</div>
        <div class="stat-label">Tổng vi phạm</div>
      </div>
      <div class="stat-card stat-card--warning">
        <div class="stat-value">{{ violationStats.no_helmet || 0 }}</div>
        <div class="stat-label">Không đội MBH</div>
      </div>
      <div class="stat-card stat-card--info">
        <div class="stat-value">{{ violationStats.no_seatbelt || 0 }}</div>
        <div class="stat-label">Không thắt dây</div>
      </div>
      <div class="stat-card stat-card--purple">
        <div class="stat-value">{{ violationStats.using_phone || 0 }}</div>
        <div class="stat-label">Dùng điện thoại</div>
      </div>
    </div>

    <!-- Filters -->
    <div class="filters-bar">
      <select v-model="filterType" @change="loadViolations" class="filter-select">
        <option value="">Tất cả loại vi phạm</option>
        <option value="no_helmet">Không đội MBH</option>
        <option value="no_seatbelt">Không thắt dây an toàn</option>
        <option value="using_phone">Sử dụng điện thoại</option>
      </select>
      <input
        v-model="filterPlate"
        @input="debouncedLoad"
        type="text"
        placeholder="Tìm biển số..."
        class="filter-input"
      />
      <button @click="loadViolations" class="btn btn--primary">Tìm kiếm</button>
    </div>

    <!-- Table -->
    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Thời gian</th>
            <th>Loại vi phạm</th>
            <th>Biển số</th>
            <th>Confidence</th>
            <th>Nguồn</th>
            <th>Evidence</th>
            <th>Thao tác</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="8" class="table-empty">
              <div class="loading-spinner"></div>
              Đang tải...
            </td>
          </tr>
          <tr v-else-if="violations.length === 0">
            <td colspan="8" class="table-empty">Chưa có vi phạm nào</td>
          </tr>
          <tr v-for="(v, idx) in violations" :key="v._id" class="table-row">
            <td>{{ skip + idx + 1 }}</td>
            <td class="td-time">{{ formatTime(v.created_at) }}</td>
            <td>
              <span class="violation-badge" :class="'badge--' + v.violation_type">
                {{ v.violation_label || violationLabel(v.violation_type) }}
              </span>
            </td>
            <td class="td-plate">
              <span v-if="v.plate_text" class="plate-text">{{ v.plate_text }}</span>
              <span v-else class="text-muted">—</span>
            </td>
            <td>
              <span class="conf-badge">{{ (v.confidence * 100).toFixed(0) }}%</span>
            </td>
            <td>
              <span class="source-badge">{{ v.source_type }}</span>
            </td>
            <td>
              <button
                v-if="v.evidence_path"
                @click="showEvidence(v)"
                class="btn btn--sm btn--ghost"
              >
                🖼️ Xem
              </button>
              <span v-else class="text-muted">—</span>
            </td>
            <td>
              <button @click="handleDelete(v._id)" class="btn btn--sm btn--danger">🗑️</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div class="pagination" v-if="total > limit">
      <button @click="prevPage" :disabled="skip === 0" class="btn btn--sm">← Trước</button>
      <span class="page-info">
        {{ skip + 1 }}–{{ Math.min(skip + limit, total) }} / {{ total }}
      </span>
      <button @click="nextPage" :disabled="skip + limit >= total" class="btn btn--sm">Sau →</button>
    </div>

    <!-- Evidence Modal -->
    <div v-if="evidenceModal" class="modal-overlay" @click.self="evidenceModal = null">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Evidence – {{ evidenceModal.violation_label }}</h3>
          <button @click="evidenceModal = null" class="modal-close">✕</button>
        </div>
        <div class="modal-body">
          <img :src="evidenceUrl" alt="Evidence" class="evidence-img" />
          <div class="evidence-info">
            <p><strong>Loại vi phạm:</strong> {{ evidenceModal.violation_label }}</p>
            <p><strong>Biển số:</strong> {{ evidenceModal.plate_text || 'Chưa nhận diện' }}</p>
            <p><strong>Confidence:</strong> {{ (evidenceModal.confidence * 100).toFixed(1) }}%</p>
            <p><strong>Thời gian:</strong> {{ formatTime(evidenceModal.created_at) }}</p>
            <p><strong>Camera:</strong> {{ evidenceModal.camera_id }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getViolations, getViolationStats, deleteViolation, getEvidenceUrl } from '@/api/index.js'

const violations = ref([])
const total = ref(0)
const skip = ref(0)
const limit = ref(20)
const loading = ref(false)
const filterType = ref('')
const filterPlate = ref('')
const evidenceModal = ref(null)
const evidenceUrl = ref('')
const violationStats = reactive({})

const VIOLATION_LABELS = {
  no_helmet: 'Không đội MBH',
  no_seatbelt: 'Không thắt dây an toàn',
  using_phone: 'Sử dụng điện thoại',
}

function violationLabel(type) {
  return VIOLATION_LABELS[type] || type
}

function formatTime(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  return d.toLocaleString('vi-VN', { hour12: false })
}

let debounceTimer = null
function debouncedLoad() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(loadViolations, 500)
}

async function loadViolations() {
  loading.value = true
  try {
    const params = { skip: skip.value, limit: limit.value }
    if (filterType.value) params.violation_type = filterType.value
    if (filterPlate.value) params.plate_text = filterPlate.value
    const data = await getViolations(params)
    violations.value = data.violations || []
    total.value = data.total || 0
  } catch (e) {
    console.error('Load violations error:', e)
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    const data = await getViolationStats(24)
    Object.assign(violationStats, data.by_type || {})
  } catch (e) {
    console.error('Load stats error:', e)
  }
}

function prevPage() {
  skip.value = Math.max(0, skip.value - limit.value)
  loadViolations()
}

function nextPage() {
  skip.value += limit.value
  loadViolations()
}

async function handleDelete(id) {
  if (!confirm('Xóa vi phạm này?')) return
  try {
    await deleteViolation(id)
    await loadViolations()
    await loadStats()
  } catch (e) {
    alert('Lỗi: ' + e.message)
  }
}

function showEvidence(v) {
  evidenceModal.value = v
  evidenceUrl.value = getEvidenceUrl(v.evidence_path)
}

const totalViolations = ref(0)

onMounted(async () => {
  await Promise.all([loadViolations(), loadStats()])
  totalViolations.value = total.value
})
</script>

<style scoped>
.violation-history {
  padding: var(--sp-xl);
  max-width: 1400px;
}

.page-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: var(--sp-xs);
}
.page-desc {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: var(--sp-lg);
}

/* Stats Cards */
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--sp-md);
  margin-bottom: var(--sp-xl);
}
.stat-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--sp-lg);
  text-align: center;
  transition: transform 0.2s ease;
}
.stat-card:hover { transform: translateY(-2px); }
.stat-value {
  font-size: 2rem;
  font-weight: 800;
  line-height: 1.2;
}
.stat-label {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-top: var(--sp-xs);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.stat-card--danger .stat-value { color: #ef4444; }
.stat-card--warning .stat-value { color: #f59e0b; }
.stat-card--info .stat-value { color: #3b82f6; }
.stat-card--purple .stat-value { color: #a855f7; }

/* Filters */
.filters-bar {
  display: flex;
  gap: var(--sp-sm);
  margin-bottom: var(--sp-lg);
  flex-wrap: wrap;
}
.filter-select, .filter-input {
  padding: 8px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.9rem;
  min-width: 180px;
}
.filter-input { flex: 1; min-width: 200px; }

/* Table */
.table-container {
  overflow-x: auto;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
}
.data-table {
  width: 100%;
  border-collapse: collapse;
}
.data-table th {
  padding: 12px 16px;
  text-align: left;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-deeper);
  white-space: nowrap;
}
.data-table td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.9rem;
  color: var(--text-secondary);
}
.table-row:hover { background: rgba(59,130,246,0.04); }
.table-empty {
  text-align: center;
  padding: 40px !important;
  color: var(--text-muted);
}
.td-time { white-space: nowrap; font-size: 0.85rem; }

/* Badges */
.violation-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
}
.badge--no_helmet { background: rgba(245,158,11,0.15); color: #f59e0b; }
.badge--no_seatbelt { background: rgba(239,68,68,0.15); color: #ef4444; }
.badge--using_phone { background: rgba(168,85,247,0.15); color: #a855f7; }

.plate-text {
  font-family: 'Courier New', monospace;
  font-weight: 700;
  font-size: 0.9rem;
  background: rgba(59,130,246,0.1);
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  color: var(--accent-primary);
}
.conf-badge {
  font-weight: 600;
  font-size: 0.85rem;
}
.source-badge {
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  background: var(--bg-deeper);
  text-transform: uppercase;
}
.text-muted { color: var(--text-muted); }

/* Buttons */
.btn {
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  cursor: pointer;
  font-size: 0.9rem;
  transition: all var(--transition-fast);
}
.btn:hover { background: var(--bg-deeper); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn--primary {
  background: var(--accent-primary);
  color: #fff;
  border-color: var(--accent-primary);
}
.btn--primary:hover { filter: brightness(1.1); }
.btn--danger {
  color: #ef4444;
  border-color: rgba(239,68,68,0.3);
}
.btn--danger:hover { background: rgba(239,68,68,0.1); }
.btn--ghost { border: none; background: none; }
.btn--ghost:hover { background: var(--bg-deeper); }
.btn--sm { padding: 4px 10px; font-size: 0.8rem; }

/* Pagination */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-md);
  margin-top: var(--sp-lg);
}
.page-info {
  font-size: 0.85rem;
  color: var(--text-muted);
}

/* Loading spinner */
.loading-spinner {
  width: 24px;
  height: 24px;
  border: 3px solid var(--border-color);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
  margin-right: var(--sp-sm);
  vertical-align: middle;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Modal */
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
.modal-content {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  max-width: 700px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-lg);
  border-bottom: 1px solid var(--border-color);
}
.modal-header h3 { font-size: 1.1rem; font-weight: 600; }
.modal-close {
  background: none;
  border: none;
  font-size: 1.3rem;
  cursor: pointer;
  color: var(--text-muted);
  padding: 4px;
}
.modal-close:hover { color: var(--text-primary); }
.modal-body { padding: var(--sp-lg); }
.evidence-img {
  width: 100%;
  border-radius: var(--radius-md);
  margin-bottom: var(--sp-md);
}
.evidence-info p {
  font-size: 0.9rem;
  color: var(--text-secondary);
  margin-bottom: var(--sp-xs);
}
.evidence-info strong { color: var(--text-primary); }
</style>
