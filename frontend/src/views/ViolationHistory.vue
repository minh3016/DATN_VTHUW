<template>
  <div class="violation-history">
    <div class="page-header">
      <div>
        <h1>🚨 Lịch sử <span class="text-gradient">Vi phạm</span></h1>
        <p>Tra cứu và quản lý toàn bộ vi phạm đã ghi nhận</p>
      </div>
      <div class="header-actions">
        <select v-model="filterType" class="input" style="width:200px;">
          <option value="">Tất cả loại vi phạm</option>
          <option value="no_helmet">Không mũ bảo hiểm</option>
          <option value="wrong_lane">Sai làn đường</option>
          <option value="red_light">Vượt đèn đỏ</option>
          <option value="speeding">Tốc độ cao</option>
        </select>
        <select v-model="filterCamera" class="input" style="width:160px;">
          <option value="">Tất cả camera</option>
          <option value="CAM_01">CAM_01</option>
          <option value="CAM_02">CAM_02</option>
          <option value="CAM_03">CAM_03</option>
        </select>
        <button class="btn btn--primary" @click="load">🔍 Tìm kiếm</button>
      </div>
    </div>

    <!-- Stats row -->
    <div class="stats-row">
      <div class="stat-chip">
        <span>📊 Tổng:</span>
        <strong>{{ total }}</strong>
      </div>
      <div class="stat-chip">
        <span>🪖 Không MBH:</span>
        <strong>{{ countByType('no_helmet') }}</strong>
      </div>
    </div>

    <ViolationTable ref="tableRef" :auto-refresh="false" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import ViolationTable from '@/components/ViolationTable.vue'
import { getStats } from '@/api/index.js'

const statsData = ref({})
const filterType = ref('')
const filterCamera = ref('')
const total = ref(0)
const tableRef = ref(null)


function countByType(type) {
  return statsData.value?.by_type?.[type] ?? '—'
}

async function load() {
  try {
    const s = await getStats(24 * 30) // 30 ngày
    statsData.value = s
    total.value = s.total_violations || 0
  } catch {}
  tableRef.value?.load?.()
}

onMounted(load)
</script>

<style scoped>
.violation-history {
  padding: var(--sp-xl);
  display: flex;
  flex-direction: column;
  gap: var(--sp-xl);
}
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--sp-md);
}
.page-header h1 { margin: 0; }
.header-actions { display: flex; gap: var(--sp-sm); align-items: center; flex-wrap: wrap; }

.stats-row { display: flex; gap: var(--sp-md); flex-wrap: wrap; }
.stat-chip {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  padding: 6px 16px;
  font-size: 0.875rem;
  color: var(--text-secondary);
  display: flex;
  gap: var(--sp-sm);
}
.stat-chip strong { color: var(--text-primary); }
</style>
