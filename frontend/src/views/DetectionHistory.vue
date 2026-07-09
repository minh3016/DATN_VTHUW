<template>
  <div class="page-container">
    <div class="page-title-section">
      <div>
        <h1>Lịch sử phát hiện phương tiện</h1>
        <p class="page-title-sub">Tra cứu lịch sử phát hiện phương tiện từ camera và video upload</p>
      </div>
    </div>

    <!-- Stats -->
    <div class="kpi-grid" style="margin-bottom:var(--sp-xl)">
      <div class="kpi-card kpi-card--blue animate-fade-in">
        <div class="kpi-icon-wrap kpi-icon-wrap--blue"><LucideIcon name="car" :size="22" /></div>
        <div class="kpi-body">
          <div class="kpi-value">{{ stats.total_detections || 0 }}</div>
          <div class="kpi-label">Tổng phát hiện (24h)</div>
        </div>
      </div>
      <div class="kpi-card kpi-card--green animate-fade-in" style="animation-delay:60ms">
        <div class="kpi-icon-wrap kpi-icon-wrap--green"><LucideIcon name="truck" :size="22" /></div>
        <div class="kpi-body">
          <div class="kpi-value">{{ stats.by_category?.oto || 0 }}</div>
          <div class="kpi-label">Xe ô tô</div>
        </div>
      </div>
      <div class="kpi-card kpi-card--red animate-fade-in" style="animation-delay:120ms">
        <div class="kpi-icon-wrap kpi-icon-wrap--red"><LucideIcon name="bike" :size="22" /></div>
        <div class="kpi-body">
          <div class="kpi-value">{{ stats.by_category?.xe_may || 0 }}</div>
          <div class="kpi-label">Xe máy</div>
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
import LucideIcon from '@/components/LucideIcon.vue'
import { getStats } from '@/api/index.js'

const stats = ref({ total_detections: 0, by_class: {}, by_category: {} })

onMounted(async () => {
  try { stats.value = await getStats(24) } catch {}
})
</script>
