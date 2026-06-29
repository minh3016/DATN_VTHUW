<template>
  <div class="dashboard">
    <!-- Page header -->
    <div class="page-header">
      <div>
        <h1><span class="text-gradient">Phat hien Vi pham Giao thong</span></h1>
        <p class="page-sub">Traffic Violation Detection · YOLOv8n AI · 4 Models</p>
      </div>
      <div class="header-badges">
        <span class="badge badge--success" v-if="backendOk">AI Online</span>
        <span class="badge badge--danger" v-else>AI Offline</span>
      </div>
    </div>

    <!-- KPI Cards -->
    <div class="kpi-grid">
      <div class="kpi-card kpi-card--blue animate-fade-in" style="animation-delay:0ms">
        <div class="kpi-icon">🚗</div>
        <div class="kpi-body">
          <div class="kpi-value">{{ vehicleStats.total_detections || 0 }}</div>
          <div class="kpi-label">Tổng phương tiện</div>
        </div>
        <div class="kpi-trend">24h</div>
      </div>
      <div class="kpi-card kpi-card--red animate-fade-in" style="animation-delay:80ms">
        <div class="kpi-icon">⚠️</div>
        <div class="kpi-body">
          <div class="kpi-value">{{ violStats.total_violations || 0 }}</div>
          <div class="kpi-label">Tổng vi phạm</div>
        </div>
        <div class="kpi-trend">24h</div>
      </div>
      <div class="kpi-card kpi-card--yellow animate-fade-in" style="animation-delay:160ms">
        <div class="kpi-icon">🪖</div>
        <div class="kpi-body">
          <div class="kpi-value">{{ violStats.by_type?.no_helmet || 0 }}</div>
          <div class="kpi-label">Không đội MBH</div>
        </div>
        <div class="kpi-trend kpi-trend--sub">
          Dây: {{ violStats.by_type?.no_seatbelt || 0 }} · ĐT: {{ violStats.by_type?.using_phone || 0 }}
        </div>
      </div>
      <div class="kpi-card kpi-card--green animate-fade-in" style="animation-delay:240ms">
        <div class="kpi-icon">🔢</div>
        <div class="kpi-body">
          <div class="kpi-value">{{ vehicleStats.by_category?.oto || 0 }}</div>
          <div class="kpi-label">Xe ô tô</div>
        </div>
        <div class="kpi-trend kpi-trend--sub">
          Xe máy: {{ vehicleStats.by_category?.xe_may || 0 }}
        </div>
      </div>
    </div>

    <!-- Charts row -->
    <div class="charts-row">
      <!-- Vehicle Doughnut -->
      <div class="card chart-card">
        <h3>Phan bo loai xe (24h)</h3>
        <div class="chart-wrap">
          <Doughnut v-if="vehicleChartData" :data="vehicleChartData" :options="chartOptions" />
          <div v-else class="no-data">Chưa có dữ liệu</div>
        </div>
      </div>

      <!-- Violations Bar -->
      <div class="card chart-card">
        <h3>Vi pham giao thong (24h)</h3>
        <div class="chart-wrap">
          <Bar v-if="violationChartData" :data="violationChartData" :options="barOptions" />
          <div v-else class="no-data">Chưa có vi phạm</div>
        </div>
      </div>

      <!-- Quick action card -->
      <div class="card quick-card">
        <h3>He thong AI</h3>
        <p class="quick-desc">Hệ thống phát hiện vi phạm giao thông tích hợp 4 model AI</p>
        <router-link to="/upload" class="btn btn--primary quick-btn">
          Upload & Phan tich
        </router-link>
        <div class="quick-stats">
          <div class="qs-item">
            <span class="qs-val">4</span>
            <span class="qs-label">AI Models</span>
          </div>
          <div class="qs-item">
            <span class="qs-val">YOLOv8n</span>
            <span class="qs-label">Engine</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Recent detections table -->
    <DetectionTable />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Doughnut, Bar } from 'vue-chartjs'
import {
  Chart as ChartJS, ArcElement, Tooltip, Legend,
  BarElement, CategoryScale, LinearScale,
} from 'chart.js'
import DetectionTable from '@/components/DetectionTable.vue'
import { getStats, getViolationStats, getHealth } from '@/api/index.js'

ChartJS.register(ArcElement, Tooltip, Legend, BarElement, CategoryScale, LinearScale)

const vehicleStats = ref({ total_detections: 0, by_class: {}, by_category: {} })
const violStats = ref({ total_violations: 0, by_type: {} })
const backendOk = ref(false)

// ── Labels ──────────────────────────────────────────────────────
const CLASS_LABELS = {
  car: 'Xe con', truck: 'Xe tai', bus: 'Xe bus', motorcycle: 'Xe may',
}
const VIOL_LABELS = {
  no_helmet: 'Khong doi MBH',
  no_seatbelt: 'Khong that day',
  using_phone: 'Dung dien thoai',
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
      borderWidth: 0, hoverOffset: 8,
    }],
  }
})

const chartOptions = {
  responsive: true, maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 11 }, padding: 12 } },
    tooltip: { backgroundColor: '#1a2235', borderColor: 'rgba(99,102,241,0.3)', borderWidth: 1 },
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
      label: 'Vi pham',
      data: keys.map(k => byType[k]),
      backgroundColor: ['#ef4444', '#f59e0b', '#a855f7'],
      borderRadius: 8, borderSkipped: false,
    }],
  }
})

const barOptions = {
  responsive: true, maintainAspectRatio: false,
  indexAxis: 'y',
  plugins: {
    legend: { display: false },
    tooltip: { backgroundColor: '#1a2235' },
  },
  scales: {
    x: { grid: { color: 'rgba(99,102,241,0.08)' }, ticks: { color: '#64748b' } },
    y: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 12 } } },
  },
}

// ── Load ────────────────────────────────────────────────────────
async function loadStats() {
  try {
    vehicleStats.value = await getStats(24)
  } catch {}
  try {
    violStats.value = await getViolationStats(24)
  } catch {}
  try {
    const h = await getHealth()
    backendOk.value = h.status === 'ok'
  } catch { backendOk.value = false }
}

let timer = null
onMounted(() => { loadStats(); timer = setInterval(loadStats, 30000) })
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.dashboard {
  padding: var(--sp-xl);
  display: flex; flex-direction: column; gap: var(--sp-xl);
  animation: fadeIn 0.4s ease;
}

/* Header */
.page-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  flex-wrap: wrap; gap: var(--sp-md);
}
.page-header h1 { margin: 0; }
.page-sub { margin: 4px 0 0; color: var(--text-muted); font-size: 0.875rem; }
.header-badges { display: flex; gap: var(--sp-sm); }

/* KPI */
.kpi-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--sp-md);
}
.kpi-card {
  display: flex; align-items: center; gap: var(--sp-md);
  padding: var(--sp-lg); border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  position: relative; overflow: hidden;
  transition: transform 0.2s, box-shadow 0.2s;
}
.kpi-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-lg); }
.kpi-card::before { content:''; position:absolute; top:0; left:0; right:0; height:2px; }
.kpi-card--blue   { background: linear-gradient(135deg, rgba(59,130,246,0.1), var(--bg-card)); }
.kpi-card--blue::before   { background: var(--gradient-primary); }
.kpi-card--green  { background: linear-gradient(135deg, rgba(34,197,94,0.1), var(--bg-card)); }
.kpi-card--green::before  { background: var(--gradient-success); }
.kpi-card--red    { background: linear-gradient(135deg, rgba(239,68,68,0.1), var(--bg-card)); }
.kpi-card--red::before    { background: var(--gradient-danger); }
.kpi-card--yellow { background: linear-gradient(135deg, rgba(245,158,11,0.1), var(--bg-card)); }
.kpi-card--yellow::before { background: linear-gradient(135deg, #f59e0b, #d97706); }
.kpi-card--purple { background: linear-gradient(135deg, rgba(139,92,246,0.1), var(--bg-card)); }
.kpi-card--purple::before { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
.kpi-icon  { font-size: 1.8rem; }
.kpi-body  { flex: 1; }
.kpi-value { font-size: 2rem; font-weight: 800; line-height: 1; }
.kpi-label { font-size: 0.78rem; color: var(--text-muted); margin-top: 4px; }
.kpi-trend {
  font-size: 0.68rem; color: var(--text-muted);
  background: rgba(255,255,255,0.05); border-radius: var(--radius-full);
  padding: 2px 8px; border: 1px solid var(--border-color);
}
.kpi-trend--sub { font-size: 0.65rem; max-width: 110px; text-align: center; line-height: 1.3; }

/* Charts row */
.charts-row {
  display: grid; grid-template-columns: 1fr 1fr 280px; gap: var(--sp-lg); align-items: start;
}
@media (max-width: 1100px) { .charts-row { grid-template-columns: 1fr 1fr; } .quick-card { display: none; } }
@media (max-width: 700px)  { .charts-row { grid-template-columns: 1fr; } }

.chart-card { padding: var(--sp-lg); }
.chart-card h3 { font-size: 0.9rem; margin: 0 0 var(--sp-md); color: var(--text-secondary); }
.chart-wrap { height: 200px; position: relative; }

/* Quick card */
.quick-card { padding: var(--sp-lg); display: flex; flex-direction: column; gap: var(--sp-md); }
.quick-card h3 { font-size: 0.9rem; margin: 0; color: var(--text-secondary); }
.quick-desc { font-size: 0.82rem; color: var(--text-muted); margin: 0; line-height: 1.4; }
.quick-btn {
  display: block; text-align: center; text-decoration: none;
  padding: 12px; font-size: 0.9rem; font-weight: 600;
  border-radius: var(--radius-md);
}
.quick-stats {
  display: flex; gap: var(--sp-md); border-top: 1px solid var(--border-color); padding-top: var(--sp-md);
}
.qs-item { flex: 1; text-align: center; }
.qs-val { display: block; font-size: 1.1rem; font-weight: 700; color: var(--text-primary); }
.qs-label { display: block; font-size: 0.7rem; color: var(--text-muted); margin-top: 2px; }

.no-data {
  display: flex; align-items: center; justify-content: center;
  height: 100%; color: var(--text-muted); font-size: 0.82rem;
}
</style>
