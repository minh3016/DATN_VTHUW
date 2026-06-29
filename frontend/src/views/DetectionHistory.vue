<template>
  <div class="history-page">
    <!-- Header -->
    <div class="page-header">
      <h1><span class="text-gradient">Lich su Phat hien</span></h1>
      <p>Tra cứu lịch sử phát hiện phương tiện từ camera và video upload</p>
    </div>

    <!-- Stats chips -->
    <div class="stats-row">
      <div class="stat-chip stat-chip--blue">
        <span class="stat-icon">Car</span>
        <div>
          <div class="stat-val">{{ stats.total_detections || 0 }}</div>
          <div class="stat-label">Tổng (24h)</div>
        </div>
      </div>
      <div class="stat-chip stat-chip--green">
        <span class="stat-icon">Oto</span>
        <div>
          <div class="stat-val">{{ stats.by_category?.oto || 0 }}</div>
          <div class="stat-label">Xe ô tô</div>
        </div>
      </div>
      <div class="stat-chip stat-chip--red">
        <span class="stat-icon">Moto</span>
        <div>
          <div class="stat-val">{{ stats.by_category?.xe_may || 0 }}</div>
          <div class="stat-label">Xe máy</div>
        </div>
      </div>
      <div class="stat-chip stat-chip--purple">
        <span class="stat-icon">Bike</span>
        <div>
          <div class="stat-val">{{ stats.by_category?.xe_dap || 0 }}</div>
          <div class="stat-label">Xe đạp</div>
        </div>
      </div>
    </div>

    <!-- Detection table -->
    <DetectionTable />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import DetectionTable from '@/components/DetectionTable.vue'
import { getStats } from '@/api/index.js'

const stats = ref({ total_detections: 0, by_class: {}, by_category: {} })

onMounted(async () => {
  try {
    stats.value = await getStats(24)
  } catch {}
})
</script>

<style scoped>
.history-page {
  padding: var(--sp-xl);
  display: flex;
  flex-direction: column;
  gap: var(--sp-xl);
  animation: fadeIn 0.4s ease;
}

.page-header h1 { margin: 0; }
.page-header p  { margin: 4px 0 0; color: var(--text-muted); font-size: 0.875rem; }

/* Stats row */
.stats-row {
  display: flex;
  gap: var(--sp-md);
  flex-wrap: wrap;
}
.stat-chip {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  padding: 10px 16px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  min-width: 140px;
  transition: transform 0.2s;
}
.stat-chip:hover { transform: translateY(-2px); }
.stat-icon { font-size: 1.5rem; }
.stat-val  { font-size: 1.4rem; font-weight: 800; line-height: 1; }
.stat-label{ font-size: 0.72rem; color: var(--text-muted); margin-top: 2px; }

.stat-chip--blue   { background: linear-gradient(135deg, rgba(59,130,246,0.1) 0%, var(--bg-card) 100%); }
.stat-chip--green  { background: linear-gradient(135deg, rgba(34,197,94,0.1) 0%, var(--bg-card) 100%); }
.stat-chip--red    { background: linear-gradient(135deg, rgba(239,68,68,0.1) 0%, var(--bg-card) 100%); }
.stat-chip--purple { background: linear-gradient(135deg, rgba(139,92,246,0.1) 0%, var(--bg-card) 100%); }
</style>
