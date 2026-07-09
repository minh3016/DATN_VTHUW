<template>
  <div class="page-container">
    <div class="page-title-section">
      <div>
        <h1>Quản lý vi phạm giao thông</h1>
        <p class="page-title-sub">Danh sách các vi phạm đã phát hiện bằng AI</p>
      </div>
    </div>

    <!-- Stats Cards -->
    <div class="kpi-grid" style="margin-bottom:var(--sp-xl)">
      <div class="kpi-card kpi-card--red animate-fade-in">
        <div class="kpi-icon-wrap kpi-icon-wrap--red"><LucideIcon name="alert-triangle" :size="22" /></div>
        <div class="kpi-body">
          <div class="kpi-value">{{ totalViolations }}</div>
          <div class="kpi-label">Tổng vi phạm</div>
        </div>
      </div>
      <div class="kpi-card kpi-card--yellow animate-fade-in" style="animation-delay:60ms">
        <div class="kpi-icon-wrap kpi-icon-wrap--yellow"><LucideIcon name="hard-hat" :size="22" /></div>
        <div class="kpi-body">
          <div class="kpi-value">{{ violationStats.no_helmet || 0 }}</div>
          <div class="kpi-label">Không đội MBH</div>
        </div>
      </div>
      <div class="kpi-card kpi-card--blue animate-fade-in" style="animation-delay:120ms">
        <div class="kpi-icon-wrap kpi-icon-wrap--blue"><LucideIcon name="shield-off" :size="22" /></div>
        <div class="kpi-body">
          <div class="kpi-value">{{ violationStats.no_seatbelt || 0 }}</div>
          <div class="kpi-label">Không thắt dây</div>
        </div>
      </div>
      <div class="kpi-card kpi-card--purple animate-fade-in" style="animation-delay:180ms">
        <div class="kpi-icon-wrap kpi-icon-wrap--purple"><LucideIcon name="smartphone" :size="22" /></div>
        <div class="kpi-body">
          <div class="kpi-value">{{ violationStats.using_phone || 0 }}</div>
          <div class="kpi-label">Dùng điện thoại</div>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="filter-bar" style="margin-bottom:var(--sp-lg)">
      <select v-model="filterType" @change="loadViolations" class="input input--sm" style="min-width:180px">
        <option value="">Tất cả loại vi phạm</option>
        <option value="no_helmet">Không đội MBH</option>
        <option value="no_seatbelt">Không thắt dây an toàn</option>
        <option value="using_phone">Sử dụng điện thoại</option>
      </select>
      <select v-model="filterSource" @change="loadViolations" class="input input--sm" style="min-width:140px">
        <option value="">Tất cả nguồn</option>
        <option value="stream">Stream</option>
        <option value="upload">Upload</option>
        <option value="image">Image</option>
      </select>
      <input v-model="filterPlate" @input="debouncedLoad" type="text" placeholder="Tìm biển số..." class="input input--sm input--search" />
      <button @click="loadViolations" class="btn btn--primary btn--sm">
        <LucideIcon name="search" :size="15" />
        Tìm kiếm
      </button>
    </div>

    <!-- Table -->
    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th style="width:50px">#</th>
            <th>Thời gian</th>
            <th>Loại vi phạm</th>
            <th>Biển số</th>
            <th>Loại xe</th>
            <th>Confidence</th>
            <th>Nguồn</th>
            <th>Bằng chứng</th>
            <th style="width:60px">Xóa</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="9" class="table-empty">
              <span class="spinner"></span> Đang tải...
            </td>
          </tr>
          <tr v-else-if="violations.length === 0">
            <td colspan="9" class="table-empty">
              <div class="empty-state">
                <LucideIcon name="shield-check" :size="40" />
                <p>Chưa có vi phạm nào được ghi nhận</p>
              </div>
            </td>
          </tr>
          <tr v-for="(v, idx) in violations" :key="v._id">
            <td class="mono">{{ skip + idx + 1 }}</td>
            <td class="mono" style="white-space:nowrap;font-size:0.82rem">{{ formatTime(v.created_at) }}</td>
            <td>
              <span class="badge badge--violation" :class="'viol--' + v.violation_type">
                {{ v.violation_label || violationLabel(v.violation_type) }}
              </span>
            </td>
            <td>
              <span v-if="v.plate_text" class="plate-text">{{ v.plate_text }}</span>
              <span v-else class="text-muted">—</span>
            </td>
            <td>
              <span v-if="v.vehicle_class" class="badge" :class="classBadge(v.vehicle_class)">{{ classLabel(v.vehicle_class) }}</span>
              <span v-else class="text-muted">—</span>
            </td>
            <td>
              <div class="conf-bar">
                <div class="conf-bar__track">
                  <div class="conf-bar__fill" :class="confClass(v.confidence)" :style="{ width: (v.confidence * 100) + '%' }"></div>
                </div>
                <span class="conf-bar__label">{{ (v.confidence * 100).toFixed(0) }}%</span>
              </div>
            </td>
            <td>
              <span class="source-badge" :class="'source-badge--' + v.source_type">{{ v.source_type }}</span>
            </td>
            <td>
              <img v-if="v.evidence_path" :src="getEvUrl(v.evidence_path)" class="evidence-thumb" @click="showEvidence(v)" alt="evidence" />
              <span v-else class="text-muted">—</span>
            </td>
            <td>
              <button @click="handleDelete(v._id)" class="btn--icon" title="Xóa vi phạm">
                <LucideIcon name="trash-2" :size="16" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div class="pagination" v-if="total > limit">
      <button @click="prevPage" :disabled="skip === 0" class="btn btn--ghost btn--sm">
        <LucideIcon name="chevron-left" :size="14" /> Trước
      </button>
      <span class="page-info">
        Trang {{ currentPage }}/{{ totalPages }} · {{ skip + 1 }}–{{ Math.min(skip + limit, total) }} / {{ total }} bản ghi
      </span>
      <button @click="nextPage" :disabled="skip + limit >= total" class="btn btn--ghost btn--sm">
        Sau <LucideIcon name="chevron-right" :size="14" />
      </button>
    </div>

    <!-- Evidence Modal -->
    <div v-if="evidenceModal" class="modal-overlay" @click.self="evidenceModal = null">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Bằng chứng vi phạm</h3>
          <button @click="evidenceModal = null" class="modal-close">✕</button>
        </div>
        <div class="modal-body">
          <img :src="evidenceUrl" alt="Evidence" style="width:100%;border-radius:var(--radius-md);display:block" />
          <div class="evidence-info">
            <div class="evidence-row">
              <span class="evidence-label">Loại vi phạm</span>
              <span class="badge badge--violation" :class="'viol--' + evidenceModal.violation_type">{{ evidenceModal.violation_label }}</span>
            </div>
            <div class="evidence-row">
              <span class="evidence-label">Biển số</span>
              <span v-if="evidenceModal.plate_text" class="plate-text">{{ evidenceModal.plate_text }}</span>
              <span v-else class="text-muted">Chưa nhận diện</span>
            </div>
            <div class="evidence-row">
              <span class="evidence-label">Confidence</span>
              <span class="mono">{{ (evidenceModal.confidence * 100).toFixed(1) }}%</span>
            </div>
            <div class="evidence-row">
              <span class="evidence-label">Thời gian</span>
              <span class="mono">{{ formatTime(evidenceModal.created_at) }}</span>
            </div>
            <div class="evidence-row" v-if="evidenceModal.camera_id">
              <span class="evidence-label">Camera</span>
              <span>{{ evidenceModal.camera_id }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { getViolations, getViolationStats, deleteViolation, getEvidenceUrl } from '@/api/index.js'
import LucideIcon from '@/components/LucideIcon.vue'

const violations = ref([])
const total = ref(0)
const skip = ref(0)
const limit = ref(20)
const loading = ref(false)
const filterType = ref('')
const filterPlate = ref('')
const filterSource = ref('')
const evidenceModal = ref(null)
const evidenceUrl = ref('')
const violationStats = reactive({})
const totalViolations = ref(0)

const CLASS_LABELS = { car: 'Xe con', truck: 'Xe tải', bus: 'Xe bus', motorcycle: 'Xe máy' }
const CLASS_BADGES = { car: 'badge--success', truck: 'badge--warning', bus: 'badge--info', motorcycle: 'badge--danger' }
const VIOLATION_LABELS = { no_helmet: 'Không đội MBH', no_seatbelt: 'Không thắt dây an toàn', using_phone: 'Sử dụng điện thoại' }

function violationLabel(type) { return VIOLATION_LABELS[type] || type }
function classLabel(c) { return CLASS_LABELS[c] || c }
function classBadge(c) { return CLASS_BADGES[c] || 'badge--info' }
function getEvUrl(p) { return getEvidenceUrl(p) }
function confClass(c) { return c >= 0.8 ? 'conf-bar__fill--high' : c >= 0.5 ? 'conf-bar__fill--medium' : 'conf-bar__fill--low' }

function formatTime(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('vi-VN', { hour12: false })
}

const currentPage = computed(() => Math.floor(skip.value / limit.value) + 1)
const totalPages = computed(() => Math.ceil(total.value / limit.value))

let debounceTimer = null
function debouncedLoad() { clearTimeout(debounceTimer); debounceTimer = setTimeout(loadViolations, 500) }

async function loadViolations() {
  loading.value = true
  try {
    const params = { skip: skip.value, limit: limit.value }
    if (filterType.value) params.violation_type = filterType.value
    if (filterPlate.value) params.plate_text = filterPlate.value
    if (filterSource.value) params.source_type = filterSource.value
    const data = await getViolations(params)
    violations.value = data.violations || []
    total.value = data.total || 0
  } catch (e) { console.error('Load violations error:', e) }
  finally { loading.value = false }
}

async function loadStats() {
  try {
    const data = await getViolationStats(24)
    Object.assign(violationStats, data.by_type || {})
    totalViolations.value = data.total_violations || 0
  } catch (e) { console.error('Load stats error:', e) }
}

function prevPage() { skip.value = Math.max(0, skip.value - limit.value); loadViolations() }
function nextPage() { skip.value += limit.value; loadViolations() }

async function handleDelete(id) {
  if (!confirm('Xóa vi phạm này?')) return
  try { await deleteViolation(id); await loadViolations(); await loadStats() }
  catch (e) { alert('Lỗi: ' + e.message) }
}

function showEvidence(v) { evidenceModal.value = v; evidenceUrl.value = getEvidenceUrl(v.evidence_path) }

onMounted(async () => { await Promise.all([loadViolations(), loadStats()]) })
</script>

<style scoped>
.evidence-info {
  margin-top: var(--sp-lg);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.evidence-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.9rem;
}
.evidence-row:last-child { border-bottom: none; }
.evidence-label {
  color: var(--text-muted);
  font-size: 0.82rem;
  font-weight: 500;
}
</style>
