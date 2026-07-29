<template>
  <div class="page-container">
    <!-- Page Title -->
    <div class="page-title-section">
      <div>
        <h1>Tổng quan hệ thống</h1>
        <p class="page-title-sub">Thống kê phát hiện vi phạm giao thông · 24 giờ qua</p>
      </div>
      <div class="header-actions">
        <button class="btn btn--primary" @click="showExportModal = true">
          <LucideIcon name="file-spreadsheet" :size="16" />
          Xuất dữ liệu Excel
        </button>
        <span class="badge" :class="backendOk ? 'badge--success' : 'badge--danger'">
          <span class="status-dot" :class="backendOk ? 'status-dot--online' : 'status-dot--offline'"></span>
          {{ backendOk ? 'AI Online' : 'AI Offline' }}
        </span>
      </div>
    </div>

    <!-- KPI Cards -->
    <div class="kpi-grid">
      <router-link to="/history" class="kpi-card kpi-card--blue animate-fade-in" style="text-decoration:none;color:inherit">
        <div class="kpi-icon-wrap kpi-icon-wrap--blue">
          <LucideIcon name="car" :size="22" />
        </div>
        <div class="kpi-body">
          <div class="kpi-value">{{ vehicleStats.total_detections || 0 }}</div>
          <div class="kpi-label">Tổng phương tiện</div>
        </div>
      </router-link>

      <div class="kpi-card kpi-card--green animate-fade-in" style="animation-delay:60ms">
        <div class="kpi-icon-wrap kpi-icon-wrap--green">
          <LucideIcon name="truck" :size="22" />
        </div>
        <div class="kpi-body">
          <div class="kpi-value">{{ vehicleStats.by_category?.oto || 0 }}</div>
          <div class="kpi-label">Xe ô tô</div>
        </div>
      </div>

      <div class="kpi-card kpi-card--red animate-fade-in" style="animation-delay:120ms">
        <div class="kpi-icon-wrap kpi-icon-wrap--red">
          <LucideIcon name="bike" :size="22" />
        </div>
        <div class="kpi-body">
          <div class="kpi-value">{{ vehicleStats.by_category?.xe_may || 0 }}</div>
          <div class="kpi-label">Xe máy</div>
        </div>
      </div>

      <router-link to="/violations" class="kpi-card kpi-card--yellow animate-fade-in" style="animation-delay:180ms;text-decoration:none;color:inherit">
        <div class="kpi-icon-wrap kpi-icon-wrap--yellow">
          <LucideIcon name="alert-triangle" :size="22" />
        </div>
        <div class="kpi-body">
          <div class="kpi-value">{{ violStats.total_violations || 0 }}</div>
          <div class="kpi-label">Tổng vi phạm</div>
        </div>
      </router-link>

      <div class="kpi-card kpi-card--purple animate-fade-in" style="animation-delay:240ms">
        <div class="kpi-icon-wrap kpi-icon-wrap--purple">
          <LucideIcon name="credit-card" :size="22" />
        </div>
        <div class="kpi-body">
          <div class="kpi-value">{{ plateCount }}</div>
          <div class="kpi-label">Biển số nhận diện</div>
        </div>
      </div>
    </div>

    <!-- Charts Grid -->
    <div class="charts-grid">
      <!-- Vehicle distribution Doughnut -->
      <div class="chart-card">
        <div class="chart-card__title">
          <LucideIcon name="pie-chart" :size="16" />
          Phân bố loại xe (24h)
        </div>
        <div class="chart-card__body">
          <Doughnut v-if="vehicleChartData" :data="vehicleChartData" :options="doughnutOptions" />
          <div v-else class="empty-state">
            <LucideIcon name="bar-chart-3" :size="36" />
            <p>Chưa có dữ liệu</p>
          </div>
        </div>
      </div>

      <!-- Violation Bar chart -->
      <div class="chart-card">
        <div class="chart-card__title">
          <LucideIcon name="alert-circle" :size="16" />
          Vi phạm theo loại (24h)
        </div>
        <div class="chart-card__body">
          <Bar v-if="violationChartData" :data="violationChartData" :options="barOptions" />
          <div v-else class="empty-state">
            <LucideIcon name="shield-check" :size="36" />
            <p>Chưa phát hiện vi phạm</p>
          </div>
        </div>
      </div>

      <!-- Violation by class breakdown -->
      <div class="chart-card">
        <div class="chart-card__title">
          <LucideIcon name="bar-chart-2" :size="16" />
          Phương tiện theo lớp (24h)
        </div>
        <div class="chart-card__body">
          <Bar v-if="classChartData" :data="classChartData" :options="classBarOptions" />
          <div v-else class="empty-state">
            <LucideIcon name="bar-chart-3" :size="36" />
            <p>Chưa có dữ liệu</p>
          </div>
        </div>
      </div>

      <!-- System Info Card -->
      <div class="chart-card system-card">
        <div class="chart-card__title">
          <LucideIcon name="cpu" :size="16" />
          Hệ thống AI
        </div>
        <div class="system-info">
          <div class="sys-row">
            <span class="sys-label">Engine</span>
            <span class="sys-value">YOLOv8n</span>
          </div>
          <div class="sys-row">
            <span class="sys-label">AI Models</span>
            <span class="sys-value">4 models</span>
          </div>
          <div class="sys-row">
            <span class="sys-label">Phát hiện xe</span>
            <span class="sys-value badge--mini" :class="backendOk ? 'badge--mini--ok' : 'badge--mini--off'">{{ backendOk ? 'Active' : 'Off' }}</span>
          </div>
          <div class="sys-row">
            <span class="sys-label">Vi phạm GT</span>
            <span class="sys-value badge--mini" :class="backendOk ? 'badge--mini--ok' : 'badge--mini--off'">{{ backendOk ? 'Active' : 'Off' }}</span>
          </div>
          <div class="sys-row">
            <span class="sys-label">Nhận diện biển số</span>
            <span class="sys-value badge--mini" :class="backendOk ? 'badge--mini--ok' : 'badge--mini--off'">{{ backendOk ? 'Active' : 'Off' }}</span>
          </div>
          <router-link to="/upload" class="btn btn--primary btn--lg" style="width:100%;margin-top:12px;text-decoration:none">
            <LucideIcon name="upload-cloud" :size="18" />
            Upload & Phân tích
          </router-link>
        </div>
      </div>
    </div>

    <!-- Recent Violations -->
    <div class="recent-section animate-fade-in" style="animation-delay:300ms">
      <div class="section-header">
        <h3>
          <LucideIcon name="alert-triangle" :size="18" />
          Vi phạm gần đây
        </h3>
        <router-link to="/violations" class="btn btn--ghost btn--sm">
          Xem tất cả
          <LucideIcon name="arrow-right" :size="14" />
        </router-link>
      </div>
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
            </tr>
          </thead>
          <tbody>
            <tr v-if="!recentViolations.length">
              <td colspan="6" class="table-empty">Chưa có vi phạm nào</td>
            </tr>
            <tr v-for="(v, i) in recentViolations" :key="v._id">
              <td class="mono">{{ i + 1 }}</td>
              <td class="mono">{{ formatTime(v.created_at) }}</td>
              <td>
                <span class="badge badge--violation" :class="'viol--' + v.violation_type">
                  {{ v.violation_label || violLabel(v.violation_type) }}
                </span>
              </td>
              <td>
                <span v-if="v.plate_text" class="plate-text">{{ v.plate_text }}</span>
                <span v-else class="text-muted">—</span>
              </td>
              <td>
                <div class="conf-bar">
                  <div class="conf-bar__track">
                    <div
                      class="conf-bar__fill"
                      :class="confClass(v.confidence)"
                      :style="{ width: (v.confidence * 100) + '%' }"
                    ></div>
                  </div>
                  <span class="conf-bar__label">{{ (v.confidence * 100).toFixed(0) }}%</span>
                </div>
              </td>
              <td>
                <span class="source-badge" :class="'source-badge--' + v.source_type">
                  {{ v.source_type }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Export Excel Modal -->
    <div v-if="showExportModal" class="modal-overlay" @click.self="showExportModal = false">
      <div class="modal-content" style="max-width:540px">
        <div class="modal-header">
          <h3 style="display:flex; align-items:center; gap:8px; margin:0">
            <LucideIcon name="file-spreadsheet" :size="20" />
            Xuất dữ liệu ra file Excel
          </h3>
          <button @click="showExportModal = false" class="modal-close">✕</button>
        </div>
        <div class="modal-body" style="display:flex; flex-direction:column; gap:18px">
          
          <!-- Data Type Selection -->
          <div class="export-group">
            <div style="display:flex; justify-content:space-between; align-items:center">
              <label class="export-label" style="margin:0">Loại dữ liệu cần xuất (Có thể chọn nhiều loại):</label>
              <span class="mono" style="font-size:0.75rem; color:var(--text-muted)">Đã chọn: {{ exportTypes.length }}/3</span>
            </div>
            <div class="export-options-grid">
              <div
                class="export-option-card"
                :class="{ 'export-option-card--active': exportTypes.includes('violations') }"
                @click="toggleExportType('violations')"
              >
                <div class="export-check-badge">
                  <LucideIcon :name="exportTypes.includes('violations') ? 'check-square' : 'square'" :size="16" />
                </div>
                <LucideIcon name="alert-triangle" :size="20" />
                <div class="export-option-title">Vi phạm giao thông</div>
                <div class="export-option-desc">Danh sách các lỗi vi phạm GT</div>
              </div>

              <div
                class="export-option-card"
                :class="{ 'export-option-card--active': exportTypes.includes('vehicles') }"
                @click="toggleExportType('vehicles')"
              >
                <div class="export-check-badge">
                  <LucideIcon :name="exportTypes.includes('vehicles') ? 'check-square' : 'square'" :size="16" />
                </div>
                <LucideIcon name="car" :size="20" />
                <div class="export-option-title">Phương tiện</div>
                <div class="export-option-desc">Lịch sử phát hiện xe lưu thông</div>
              </div>

              <div
                class="export-option-card"
                :class="{ 'export-option-card--active': exportTypes.includes('plates') }"
                @click="toggleExportType('plates')"
              >
                <div class="export-check-badge">
                  <LucideIcon :name="exportTypes.includes('plates') ? 'check-square' : 'square'" :size="16" />
                </div>
                <LucideIcon name="credit-card" :size="20" />
                <div class="export-option-title">Biển số xe</div>
                <div class="export-option-desc">Biển số xe được AI nhận diện</div>
              </div>
            </div>
          </div>

          <!-- Time range (Days) -->
          <div class="export-group">
            <label class="export-label">Khoảng thời gian (Tối đa 7 ngày gần nhất):</label>
            <div class="export-days-row">
              <button
                v-for="d in [1, 3, 5, 7]"
                :key="d"
                class="btn-day-select"
                :class="{ 'btn-day-select--active': exportDays === d }"
                @click="exportDays = d"
              >
                {{ d }} ngày gần nhất
              </button>
            </div>
          </div>

          <!-- Max Limit -->
          <div class="export-group">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px">
              <label class="export-label" style="margin:0">Số dòng tối đa mỗi loại (Tối đa 1000 dòng):</label>
              <span class="mono" style="font-weight:700; color:var(--accent-primary)">{{ exportLimit }} dòng / loại</span>
            </div>
            <input
              type="range"
              class="speed-slider"
              min="100"
              max="1000"
              step="100"
              v-model.number="exportLimit"
            />
          </div>

          <!-- Constraint Notice -->
          <div class="export-notice">
            <LucideIcon name="info" :size="15" />
            <span>Quy định hệ thống: Xuất dữ liệu tối đa 7 ngày gần nhất và không quá 1000 dòng cho mỗi loại dữ liệu. File Excel sẽ phân chia mỗi loại dữ liệu thành 1 Trang (Sheet) riêng biệt.</span>
          </div>

          <!-- Error message if any -->
          <div v-if="exportError" class="vc-error" style="margin:0">
            <LucideIcon name="alert-circle" :size="16" />
            <span>{{ exportError }}</span>
          </div>

          <!-- Actions -->
          <div style="display:flex; justify-content:flex-end; gap:12px; margin-top:8px">
            <button class="btn btn--ghost" @click="showExportModal = false">Hủy</button>
            <button class="btn btn--primary" @click="handleExport" :disabled="isExporting || !exportTypes.length">
              <LucideIcon :name="isExporting ? 'loader-2' : 'download'" :size="16" />
              {{ isExporting ? 'Đang xuất file...' : 'Tải về file Excel' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Doughnut, Bar } from 'vue-chartjs'
import {
  Chart as ChartJS, ArcElement, Tooltip, Legend,
  BarElement, CategoryScale, LinearScale,
} from 'chart.js'
import LucideIcon from '@/components/LucideIcon.vue'
import { getStats, getViolationStats, getHealth, getViolations, exportExcel } from '@/api/index.js'

ChartJS.register(ArcElement, Tooltip, Legend, BarElement, CategoryScale, LinearScale)

const vehicleStats = ref({ total_detections: 0, by_class: {}, by_category: {} })
const violStats = ref({ total_violations: 0, by_type: {} })
const backendOk = ref(false)
const recentViolations = ref([])
const plateCount = ref(0)

// Export Excel Modal State
const showExportModal = ref(false)
const exportTypes = ref(['violations', 'vehicles', 'plates']) // Multi-select array
const exportDays = ref(7)
const exportLimit = ref(1000)
const isExporting = ref(false)
const exportError = ref(null)

function toggleExportType(type) {
  const idx = exportTypes.value.indexOf(type)
  if (idx > -1) {
    if (exportTypes.value.length > 1) {
      exportTypes.value.splice(idx, 1)
    }
  } else {
    exportTypes.value.push(type)
  }
}

async function handleExport() {
  if (isExporting.value || !exportTypes.value.length) return
  isExporting.value = true
  exportError.value = null

  const days = Math.min(Math.max(1, exportDays.value), 7)
  const limit = Math.min(Math.max(1, exportLimit.value), 1000)

  try {
    const blobData = await exportExcel({
      dataTypes: exportTypes.value,
      days,
      limit,
    })

    const url = window.URL.createObjectURL(new Blob([blobData]))
    const link = document.createElement('a')
    link.href = url
    const timestamp = new Date().toISOString().slice(0, 10)
    link.setAttribute('download', `export_${exportTypes.value.join('_')}_${timestamp}.xlsx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)

    showExportModal.value = false
  } catch (err) {
    exportError.value = err.message || 'Xuất dữ liệu thất bại'
  } finally {
    isExporting.value = false
  }
}

const CLASS_LABELS = { car: 'Xe con', truck: 'Xe tải', bus: 'Xe bus', motorcycle: 'Xe máy' }
const VIOL_LABELS = { no_helmet: 'Không đội MBH', no_seatbelt: 'Không thắt dây', using_phone: 'Dùng điện thoại', red_light_violation: 'Vượt đèn đỏ', red_light: 'Vượt đèn đỏ' }
function violLabel(v) { return VIOL_LABELS[v] || v }

function confClass(c) {
  if (c >= 0.8) return 'conf-bar__fill--high'
  if (c >= 0.5) return 'conf-bar__fill--medium'
  return 'conf-bar__fill--low'
}

function formatTime(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('vi-VN', { hour12: false, day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit' })
}

// ── Vehicle Doughnut ────────────────────────────────────────────
const vehicleChartData = computed(() => {
  const byClass = vehicleStats.value.by_class || {}
  const keys = Object.keys(byClass)
  if (!keys.length) return null
  return {
    labels: keys.map(k => CLASS_LABELS[k] || k),
    datasets: [{
      data: keys.map(k => byClass[k]),
      backgroundColor: ['#22c55e', '#f59e0b', '#06b6d4', '#ef4444'],
      borderWidth: 0, hoverOffset: 6,
    }],
  }
})

const doughnutOptions = {
  responsive: true, maintainAspectRatio: false,
  cutout: '65%',
  plugins: {
    legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 11, family: 'Inter' }, padding: 12, usePointStyle: true, pointStyleWidth: 8 } },
    tooltip: { backgroundColor: '#1e293b', borderColor: 'rgba(148,163,184,0.2)', borderWidth: 1, titleFont: { family: 'Inter' }, bodyFont: { family: 'Inter' } },
  },
}

// ── Violations Bar ──────────────────────────────────────────────
const violationChartData = computed(() => {
  const byType = violStats.value.by_type || {}
  const keys = Object.keys(byType)
  if (!keys.length) return null
  return {
    labels: keys.map(k => VIOL_LABELS[k] || k),
    datasets: [{
      label: 'Vi phạm',
      data: keys.map(k => byType[k]),
      backgroundColor: ['#f59e0b', '#ef4444', '#a855f7'],
      borderRadius: 6, borderSkipped: false,
      barThickness: 24,
    }],
  }
})

const barOptions = {
  responsive: true, maintainAspectRatio: false,
  indexAxis: 'y',
  plugins: {
    legend: { display: false },
    tooltip: { backgroundColor: '#1e293b', borderColor: 'rgba(148,163,184,0.2)', borderWidth: 1 },
  },
  scales: {
    x: { grid: { color: 'rgba(148,163,184,0.06)' }, ticks: { color: '#64748b', font: { size: 11 } } },
    y: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 12 } } },
  },
}

// ── Class breakdown bar ─────────────────────────────────────────
const classChartData = computed(() => {
  const byClass = vehicleStats.value.by_class || {}
  const keys = Object.keys(byClass)
  if (!keys.length) return null
  const colors = { car: '#22c55e', truck: '#f59e0b', bus: '#06b6d4', motorcycle: '#ef4444' }
  return {
    labels: keys.map(k => CLASS_LABELS[k] || k),
    datasets: [{
      label: 'Số lượng',
      data: keys.map(k => byClass[k]),
      backgroundColor: keys.map(k => colors[k] || '#64748b'),
      borderRadius: 6, borderSkipped: false,
      barThickness: 28,
    }],
  }
})
const classBarOptions = {
  responsive: true, maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: { backgroundColor: '#1e293b' },
  },
  scales: {
    x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 11 } } },
    y: { grid: { color: 'rgba(148,163,184,0.06)' }, ticks: { color: '#64748b', font: { size: 11 } }, beginAtZero: true },
  },
}

// ── Load ────────────────────────────────────────────────────────
async function loadStats() {
  try { vehicleStats.value = await getStats(24) } catch {}
  try { violStats.value = await getViolationStats(24) } catch {}
  try {
    const h = await getHealth()
    backendOk.value = h.status === 'ok'
  } catch { backendOk.value = false }
  try {
    const data = await getViolations({ limit: 5 })
    recentViolations.value = data.violations || []
  } catch {}
}

let timer = null
onMounted(() => { loadStats(); timer = setInterval(loadStats, 30000) })
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
/* Charts Grid */
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-lg);
  margin-top: var(--sp-xl);
}
@media (max-width: 1100px) { .charts-grid { grid-template-columns: 1fr; } }

/* System info card */
.system-card .chart-card__body { height: auto; }
.system-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.sys-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.85rem;
  padding: 6px 0;
  border-bottom: 1px solid var(--border-color);
}
.sys-row:last-of-type { border-bottom: none; }
.sys-label { color: var(--text-muted); }
.sys-value { color: var(--text-primary); font-weight: 600; font-size: 0.85rem; }
.badge--mini {
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 0.72rem;
  font-weight: 600;
}
.badge--mini--ok  { background: rgba(16,185,129,0.12); color: #34d399; }
.badge--mini--off { background: rgba(239,68,68,0.12);  color: #f87171; }

/* Section header */
.recent-section {
  margin-top: var(--sp-xl);
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-md);
}
.section-header h3 {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  font-size: 1rem;
  margin: 0;
}

/* Header actions */
.header-actions { display: flex; gap: var(--sp-sm); align-items: center; }

/* Export Modal Styles */
.export-group { display: flex; flex-direction: column; gap: 8px; }
.export-label { font-size: 0.85rem; font-weight: 600; color: var(--text-primary); }
.export-options-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.export-option-card {
  position: relative;
  background: var(--bg-inset); border: 1px solid var(--border-color); border-radius: var(--radius-md);
  padding: 14px 10px; text-align: center; cursor: pointer; transition: all var(--transition-fast);
  display: flex; flex-direction: column; align-items: center; gap: 6px; color: var(--text-muted);
}
.export-check-badge { position: absolute; top: 8px; right: 8px; color: var(--text-muted); opacity: 0.5; }
.export-option-card:hover { border-color: var(--accent-primary); color: var(--text-primary); background: rgba(37,99,235,0.03); }
.export-option-card--active {
  border-color: var(--accent-primary); background: rgba(37,99,235,0.1); color: var(--accent-primary); font-weight: 600;
}
.export-option-card--active .export-check-badge { color: var(--accent-primary); opacity: 1; }
.export-option-title { font-size: 0.85rem; font-weight: 600; color: var(--text-primary); }
.export-option-desc { font-size: 0.72rem; color: var(--text-muted); line-height: 1.3; }

.export-days-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.btn-day-select {
  padding: 8px 10px; border-radius: var(--radius-md); border: 1px solid var(--border-color);
  background: var(--bg-inset); color: var(--text-secondary); font-size: 0.8rem; font-weight: 600;
  cursor: pointer; transition: all var(--transition-fast); text-align: center;
}
.btn-day-select:hover { border-color: var(--accent-primary); color: var(--text-primary); }
.btn-day-select--active { background: var(--accent-primary); color: #fff; border-color: var(--accent-primary); }

.export-notice {
  display: flex; align-items: flex-start; gap: 8px; padding: 10px 14px;
  background: rgba(37,99,235,0.06); border: 1px solid rgba(37,99,235,0.15); border-radius: var(--radius-md);
  font-size: 0.78rem; color: var(--text-secondary); line-height: 1.4;
}
</style>
