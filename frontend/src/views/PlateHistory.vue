<template>
  <div class="page-container">
    <div class="page-title-section">
      <div>
        <h1>Lịch sử biển số xe</h1>
        <p class="page-title-sub">Danh sách biển số xe đã nhận diện bằng AI</p>
      </div>
    </div>

    <!-- Stats Cards -->
    <div class="kpi-grid" style="margin-bottom:var(--sp-xl)">
      <div class="kpi-card kpi-card--blue animate-fade-in">
        <div class="kpi-icon-wrap kpi-icon-wrap--blue"><LucideIcon name="credit-card" :size="22" /></div>
        <div class="kpi-body">
          <div class="kpi-value">{{ stats.total_plates || 0 }}</div>
          <div class="kpi-label">Tổng biển số</div>
        </div>
      </div>
      <div class="kpi-card kpi-card--green animate-fade-in" style="animation-delay:60ms">
        <div class="kpi-icon-wrap kpi-icon-wrap--green"><LucideIcon name="check-circle" :size="22" /></div>
        <div class="kpi-body">
          <div class="kpi-value">{{ stats.valid_plates || 0 }}</div>
          <div class="kpi-label">Hợp lệ</div>
        </div>
      </div>
      <div class="kpi-card kpi-card--red animate-fade-in" style="animation-delay:120ms">
        <div class="kpi-icon-wrap kpi-icon-wrap--red"><LucideIcon name="x-circle" :size="22" /></div>
        <div class="kpi-body">
          <div class="kpi-value">{{ stats.invalid_plates || 0 }}</div>
          <div class="kpi-label">Không hợp lệ</div>
        </div>
      </div>
      <div class="kpi-card kpi-card--purple animate-fade-in" style="animation-delay:180ms">
        <div class="kpi-icon-wrap kpi-icon-wrap--purple"><LucideIcon name="map-pin" :size="22" /></div>
        <div class="kpi-body">
          <div class="kpi-value">{{ stats.unique_provinces || 0 }}</div>
          <div class="kpi-label">Tỉnh / TP</div>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="filter-bar" style="margin-bottom:var(--sp-lg)">
      <input
        v-model="filterPlate"
        @input="debouncedLoad"
        type="text"
        placeholder="Tìm biển số..."
        class="input input--sm input--search"
      />
      <select v-model="filterValid" @change="loadPlates" class="input input--sm" style="min-width:160px">
        <option value="">Tất cả trạng thái</option>
        <option value="true">Hợp lệ</option>
        <option value="false">Không hợp lệ</option>
      </select>
      <select v-model="filterSource" @change="loadPlates" class="input input--sm" style="min-width:140px">
        <option value="">Tất cả nguồn</option>
        <option value="stream">Stream</option>
        <option value="upload">Upload Video</option>
        <option value="image">Upload Ảnh</option>
      </select>
      <button @click="loadPlates" class="btn btn--primary btn--sm">
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
            <th>Biển số</th>
            <th>Trạng thái</th>
            <th>Tỉnh / TP</th>
            <th>Độ tin cậy</th>
            <th>Nguồn</th>
            <th>Minh chứng</th>
            <th style="width:60px">Xóa</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="9" class="table-empty">
              <span class="spinner"></span> Đang tải...
            </td>
          </tr>
          <tr v-else-if="plates.length === 0">
            <td colspan="9" class="table-empty">
              <div class="empty-state">
                <LucideIcon name="credit-card" :size="40" />
                <p>Chưa có biển số nào được ghi nhận</p>
              </div>
            </td>
          </tr>
          <tr v-for="(item, idx) in plates" :key="item.id || item._id">
            <td class="mono">{{ skip + idx + 1 }}</td>
            <td class="mono" style="white-space:nowrap;font-size:0.82rem">{{ formatTime(item.created_at) }}</td>
            <td>
              <span class="plate-text">{{ item.plate_text }}</span>
              <div v-if="item.plate_text !== item.plate_text_raw" class="plate-raw-text">
                OCR: <span class="mono">{{ item.plate_text_raw }}</span>
              </div>
            </td>
            <td>
              <span v-if="item.is_valid" class="badge badge--success">Hợp lệ</span>
              <span v-else class="badge badge--danger">Không hợp lệ</span>
            </td>
            <td>
              <span v-if="item.province_name">{{ item.province_name }}</span>
              <span v-else class="text-muted">—</span>
            </td>
            <td>
              <div class="conf-bar">
                <div class="conf-bar__track">
                  <div class="conf-bar__fill" :class="confClass(item.avg_confidence)" :style="{ width: (item.avg_confidence * 100) + '%' }"></div>
                </div>
                <span class="conf-bar__label">{{ (item.avg_confidence * 100).toFixed(0) }}%</span>
              </div>
            </td>
            <td>
              <span class="source-badge" :class="'source-badge--' + item.source_type">{{ item.source_type }}</span>
            </td>
            <td>
              <img
                v-if="item.plate_evidence_path"
                :src="getEvUrl(item.plate_evidence_path)"
                class="evidence-thumb"
                @click="showEvidence(item)"
                alt="plate evidence"
                title="Xem chi tiết"
              />
              <img
                v-else-if="item.evidence_path"
                :src="getEvUrl(item.evidence_path)"
                class="evidence-thumb"
                @click="showEvidence(item)"
                alt="evidence"
                title="Xem chi tiết"
              />
              <span v-else class="text-muted">—</span>
            </td>
            <td>
              <button @click="handleDelete(item.id || item._id)" class="btn--icon" title="Xóa biển số">
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
      <div class="modal-content" style="max-width:800px">
        <div class="modal-header">
          <h3>Chi tiết biển số xe</h3>
          <button @click="evidenceModal = null" class="modal-close">✕</button>
        </div>
        <div class="modal-body">
          <!-- Plate crop image -->
          <div v-if="evidenceModal.plate_evidence_path" class="evidence-section">
            <h4 class="evidence-section__title">
              <LucideIcon name="scan" :size="16" /> Khu vực biển số (Crop)
            </h4>
            <div class="evidence-image-wrap evidence-image-wrap--crop">
              <img :src="getEvUrl(evidenceModal.plate_evidence_path)" alt="Plate Crop" />
            </div>
            <p class="evidence-caption">Bounding box bao quanh từng ký tự được nhận diện</p>
          </div>

          <!-- Full frame image -->
          <div v-if="evidenceModal.evidence_path" class="evidence-section">
            <h4 class="evidence-section__title">
              <LucideIcon name="image" :size="16" /> Khung hình gốc
            </h4>
            <div class="evidence-image-wrap">
              <img :src="getEvUrl(evidenceModal.evidence_path)" alt="Full Frame" />
            </div>
            <p class="evidence-caption">Bounding box hiển thị vị trí biển số trên khung hình</p>
          </div>

          <!-- Detail info -->
          <div class="evidence-info">
            <div class="evidence-row">
              <span class="evidence-label">Biển số</span>
              <span class="plate-text">{{ evidenceModal.plate_text }}</span>
            </div>
            <div class="evidence-row" v-if="evidenceModal.plate_text !== evidenceModal.plate_text_raw">
              <span class="evidence-label">OCR gốc</span>
              <span class="mono" style="text-decoration:line-through;color:var(--text-muted)">{{ evidenceModal.plate_text_raw }}</span>
            </div>
            <div class="evidence-row">
              <span class="evidence-label">Trạng thái</span>
              <span v-if="evidenceModal.is_valid" class="badge badge--success">Hợp lệ</span>
              <span v-else class="badge badge--danger">Không hợp lệ</span>
            </div>
            <div class="evidence-row" v-if="evidenceModal.province_name">
              <span class="evidence-label">Tỉnh / TP</span>
              <span>{{ evidenceModal.province_name }}</span>
            </div>
            <div class="evidence-row">
              <span class="evidence-label">Độ tin cậy OCR</span>
              <span class="mono">{{ (evidenceModal.avg_confidence * 100).toFixed(1) }}%</span>
            </div>
            <div class="evidence-row">
              <span class="evidence-label">Thời gian</span>
              <span class="mono">{{ formatTime(evidenceModal.created_at) }}</span>
            </div>
            <div class="evidence-row">
              <span class="evidence-label">Nguồn</span>
              <span>
                <span class="source-badge" :class="'source-badge--' + evidenceModal.source_type">{{ evidenceModal.source_type }}</span>
                {{ evidenceModal.camera_id }}
              </span>
            </div>
            <div class="evidence-row" v-if="evidenceModal.source_file">
              <span class="evidence-label">File</span>
              <span class="mono" style="font-size:0.78rem">{{ evidenceModal.source_file }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getPlateDetections, getPlateStats, deletePlateDetection, getEvidenceUrl } from '@/api/index.js'
import LucideIcon from '@/components/LucideIcon.vue'

const plates = ref([])
const total = ref(0)
const skip = ref(0)
const limit = ref(20)
const loading = ref(false)
const filterPlate = ref('')
const filterValid = ref('')
const filterSource = ref('')
const evidenceModal = ref(null)
const stats = ref({})

function getEvUrl(p) { return getEvidenceUrl(p) }
function confClass(c) { return c >= 0.8 ? 'conf-bar__fill--high' : c >= 0.5 ? 'conf-bar__fill--medium' : 'conf-bar__fill--low' }

function formatTime(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('vi-VN', { hour12: false })
}

const currentPage = computed(() => Math.floor(skip.value / limit.value) + 1)
const totalPages = computed(() => Math.ceil(total.value / limit.value))

let debounceTimer = null
function debouncedLoad() { clearTimeout(debounceTimer); debounceTimer = setTimeout(loadPlates, 500) }

async function loadPlates() {
  loading.value = true
  try {
    const params = { skip: skip.value, limit: limit.value }
    if (filterPlate.value) params.plate_text = filterPlate.value
    if (filterValid.value !== '') params.is_valid = filterValid.value === 'true'
    if (filterSource.value) params.source_type = filterSource.value
    const data = await getPlateDetections(params)
    plates.value = data.plates || []
    total.value = data.total || 0
  } catch (e) { console.error('Load plates error:', e) }
  finally { loading.value = false }
}

async function loadStats() {
  try {
    const data = await getPlateStats(24 * 7)
    stats.value = data
  } catch (e) { console.error('Load plate stats error:', e) }
}

function prevPage() { skip.value = Math.max(0, skip.value - limit.value); loadPlates() }
function nextPage() { skip.value += limit.value; loadPlates() }

async function handleDelete(id) {
  if (!confirm('Xóa biển số này?')) return
  try { await deletePlateDetection(id); await loadPlates(); await loadStats() }
  catch (e) { alert('Lỗi: ' + e.message) }
}

function showEvidence(item) { evidenceModal.value = item }

let refreshInterval
onMounted(async () => {
  await Promise.all([loadPlates(), loadStats()])
  refreshInterval = setInterval(() => {
    if (!evidenceModal.value && skip.value === 0 && !filterPlate.value) {
      loadPlates()
      loadStats()
    }
  }, 15000)
})

onUnmounted(() => {
  clearInterval(refreshInterval)
  clearTimeout(debounceTimer)
})
</script>

<style scoped>
.plate-raw-text {
  margin-top: 2px;
  font-size: 0.72rem;
  color: var(--text-muted);
}

.evidence-section {
  margin-bottom: var(--sp-lg);
}
.evidence-section__title {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--sp-sm);
}
.evidence-image-wrap {
  background: var(--bg-deeper);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--sp-sm);
}
.evidence-image-wrap img {
  max-width: 100%;
  max-height: 400px;
  object-fit: contain;
  display: block;
  border-radius: var(--radius-md);
}
.evidence-image-wrap--crop {
  padding: var(--sp-md);
}
.evidence-image-wrap--crop img {
  max-height: 140px;
}
.evidence-caption {
  font-size: 0.72rem;
  color: var(--text-muted);
  text-align: center;
  margin-top: var(--sp-xs);
}

.evidence-info {
  margin-top: var(--sp-lg);
  display: flex;
  flex-direction: column;
  gap: 0;
}
.evidence-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
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
