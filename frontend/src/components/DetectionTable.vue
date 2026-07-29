<template>
  <div class="dtable card">
    <!-- Header -->
    <div class="dtable-header">
      <h3><LucideIcon name="list" :size="16" /> Lịch sử phát hiện</h3>
      <div class="dtable-controls">
        <select v-model="filterClass" class="input input--sm" @change="loadData">
          <option value="">Tất cả loại xe</option>
          <option value="car">Xe con</option>
          <option value="truck">Xe tải</option>
          <option value="bus">Xe buýt</option>
          <option value="motorcycle">Xe máy</option>
        </select>
        <select v-model="filterCategory" class="input input--sm" @change="loadData">
          <option value="">Tất cả nhóm</option>
          <option value="oto">Xe ô tô</option>
          <option value="xe_may">Xe máy</option>
        </select>
        <button class="btn--icon" @click="loadData" title="Tải lại">
          <LucideIcon name="refresh-cw" :size="16" />
        </button>
      </div>
    </div>

    <!-- Table -->
    <div class="table-wrap">
      <table class="data-table">
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
            <td colspan="8" class="table-empty">
              <span class="spinner"></span> Đang tải...
            </td>
          </tr>
          <tr v-else-if="!detections.length">
            <td colspan="8" class="table-empty">
              <div class="empty-state">
                <LucideIcon name="search-x" :size="36" />
                <p>Chưa có dữ liệu phát hiện</p>
              </div>
            </td>
          </tr>
          <tr v-for="(d, idx) in detections" :key="d._id">
            <td class="mono">{{ skip + idx + 1 }}</td>
            <td class="mono" style="white-space:nowrap;font-size:0.82rem">{{ formatDate(d.created_at) }}</td>
            <td>
              <span class="badge" :class="classBadge(d.vehicle_class)">
                {{ classLabel(d.vehicle_class) }}
              </span>
            </td>
            <td>
              <span class="cat-label" :class="`cat--${d.category}`">{{ categoryLabel(d.category) }}</span>
            </td>
            <td>
              <div class="conf-bar">
                <div class="conf-bar__track">
                  <div class="conf-bar__fill" :class="confClass(d.confidence)" :style="{ width: ((d.confidence||0) * 100) + '%' }"></div>
                </div>
                <span class="conf-bar__label">{{ d.confidence ? `${(d.confidence * 100).toFixed(0)}%` : '--' }}</span>
              </div>
            </td>
            <td class="mono">{{ d.camera_id || '--' }}</td>
            <td>
              <img v-if="d.evidence_path" :src="getEvUrl(d.evidence_path)" class="evidence-thumb" @click="showEvidence(d.evidence_path)" alt="evidence" />
              <span v-else class="text-muted">–</span>
            </td>
            <td>
              <button class="btn--icon" @click="removeItem(d._id)" title="Xóa">
                <LucideIcon name="trash-2" :size="15" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div class="pagination" v-if="total > pageSize">
      <button class="btn btn--ghost btn--sm" :disabled="skip === 0" @click="prevPage">
        <LucideIcon name="chevron-left" :size="14" /> Trước
      </button>
      <span class="page-info">
        Trang {{ currentPage }}/{{ totalPages }} · {{ skip + 1 }}–{{ Math.min(skip + pageSize, total) }} / {{ total }}
      </span>
      <button class="btn btn--ghost btn--sm" :disabled="skip + pageSize >= total" @click="nextPage">
        Sau <LucideIcon name="chevron-right" :size="14" />
      </button>
    </div>

    <!-- Evidence modal -->
    <Teleport to="body">
      <div v-if="modalSrc" class="modal-overlay" @click="modalSrc = null">
        <div class="lightbox-card" @click.stop>
          <img :src="modalSrc" alt="evidence" class="lightbox-img" />
          <button class="modal-close" @click="modalSrc = null">✕</button>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { getDetections, deleteDetection, getEvidenceUrl } from '@/api/index.js'
import LucideIcon from '@/components/LucideIcon.vue'

const props = defineProps({
  autoRefresh: { type: Boolean, default: false },
  camera: { type: String, default: '' },
})

const detections = ref([])
const loading = ref(false)
const total = ref(0)
const skip = ref(0)
const pageSize = 15
const filterClass = ref('')
const filterCategory = ref('')
const modalSrc = ref(null)

const CLASS_LABELS = { car: 'Xe con', truck: 'Xe tải', bus: 'Xe buýt', motorcycle: 'Xe máy' }
const CLASS_BADGES = { car: 'badge--success', truck: 'badge--warning', bus: 'badge--info', motorcycle: 'badge--danger' }
const CAT_LABELS = { oto: 'Xe ô tô', xe_may: 'Xe máy' }

function classLabel(c) { return CLASS_LABELS[c] || c }
function classBadge(c) { return CLASS_BADGES[c] || 'badge--info' }
function categoryLabel(c) { return CAT_LABELS[c] || c }
function getEvUrl(p) { return getEvidenceUrl(p) }
function confClass(c) { return c >= 0.8 ? 'conf-bar__fill--high' : c >= 0.5 ? 'conf-bar__fill--medium' : 'conf-bar__fill--low' }

const currentPage = computed(() => Math.floor(skip.value / pageSize) + 1)
const totalPages = computed(() => Math.ceil(total.value / pageSize))

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
  } catch (e) { console.error('Load detections error:', e) }
  finally { loading.value = false }
}

function prevPage() { skip.value = Math.max(0, skip.value - pageSize); loadData() }
function nextPage() { skip.value += pageSize; loadData() }

async function removeItem(id) {
  try { await deleteDetection(id); detections.value = detections.value.filter(d => d._id !== id); total.value = Math.max(0, total.value - 1) }
  catch (e) { console.error('Delete error:', e) }
}

function showEvidence(path) { modalSrc.value = getEvUrl(path) }

function formatDate(d) {
  if (!d) return '--'
  try {
    // Backend lưu UTC, chuỗi ISO có thể thiếu suffix 'Z' → thêm 'Z' để JS Date hiểu đúng là UTC
    let isoStr = String(d)
    if (isoStr && !isoStr.endsWith('Z') && !isoStr.includes('+') && !isoStr.includes('-', 10)) {
      isoStr += 'Z'
    }
    return new Date(isoStr).toLocaleString('vi-VN', { day:'2-digit', month:'2-digit', year:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit' })
  }
  catch { return d }
}

let refreshTimer = null
watch(() => props.autoRefresh, (v) => { clearInterval(refreshTimer); if (v) refreshTimer = setInterval(loadData, 30000) }, { immediate: true })

onMounted(loadData)
onUnmounted(() => clearInterval(refreshTimer))
defineExpose({ loadData })
</script>

<style scoped>
.dtable { padding: 0; overflow: hidden; }

.dtable-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px var(--sp-lg); border-bottom: 1px solid var(--border-color); background: var(--bg-surface);
}
.dtable-header h3 { margin: 0; font-size: 0.9rem; display: flex; align-items: center; gap: 8px; }
.dtable-controls { display: flex; gap: var(--sp-sm); align-items: center; }

.table-wrap { overflow-x: auto; }

.cat-label {
  font-size: 0.72rem; padding: 2px 8px; border-radius: var(--radius-full); font-weight: 600;
}
.cat--oto    { background: rgba(34,197,94,0.1);  color: #22c55e; }
.cat--xe_may { background: rgba(239,68,68,0.1);  color: #ef4444; }

.lightbox-card { position: relative; max-width: 90vw; max-height: 90vh; }
.lightbox-img { max-width: 100%; max-height: 85vh; border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); display: block; }
.lightbox-card .modal-close { position: absolute; top: -12px; right: -12px; }
</style>
