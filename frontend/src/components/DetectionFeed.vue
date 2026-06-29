<template>
  <div class="dfeed">
    <!-- Header -->
    <div class="dfeed-header">
      <div class="dfeed-title">
        <span class="dfeed-icon">Car</span>
        <h3>Phát hiện Realtime</h3>
        <span v-if="items.length" class="count-badge">{{ items.length }}</span>
      </div>
      <div class="dfeed-actions">
        <span v-if="newCount > 0" class="new-badge animate-bounce">+{{ newCount }} mới</span>
        <button class="btn btn--ghost btn--sm" @click="clearFeed" title="Xoa feed">X</button>
      </div>
    </div>

    <!-- Feed list -->
    <div class="dfeed-list" ref="listRef">
      <!-- Empty state -->
      <div v-if="!items.length" class="dfeed-empty">
        <div class="empty-icon">Search</div>
        <p>Chưa phát hiện phương tiện</p>
        <p class="empty-sub">Kết quả sẽ xuất hiện ở đây realtime</p>
      </div>

      <!-- Detection items -->
      <TransitionGroup name="feed-item" tag="div" class="feed-items">
        <div
          v-for="item in items"
          :key="item.id"
          class="feed-item"
          :class="[`feed-item--${item.category}`, { 'feed-item--new': item.isNew }]"
        >
          <!-- Icon -->
          <div class="item-icon" :class="`icon--${item.category}`">
            {{ categoryIcon(item.category) }}
          </div>

          <!-- Info -->
          <div class="item-info">
            <div class="item-top">
              <span class="badge" :class="classBadge(item.class_name)">
                {{ classLabel(item.class_name) }}
              </span>
              <span class="item-conf mono">{{ (item.conf * 100).toFixed(0) }}%</span>
            </div>
            <div class="item-bottom">
              <span class="item-category">{{ categoryLabel(item.category) }}</span>
              <span class="item-time">{{ formatTime(item.timestamp) }}</span>
            </div>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onUnmounted } from 'vue'

const props = defineProps({
  maxItems: { type: Number, default: 60 },
})

// ── State ──────────────────────────────────────────────────────
const items    = ref([])
const newCount = ref(0)
const listRef  = ref(null)

let newCountTimer = null

// ── Labels ─────────────────────────────────────────────────────
const CLASS_LABELS = {
  car: 'Xe con', truck: 'Xe tải', bus: 'Xe buýt',
  motorcycle: 'Xe máy', bicycle: 'Xe đạp',
}
const CLASS_BADGES = {
  car: 'badge--success', truck: 'badge--warning', bus: 'badge--info',
  motorcycle: 'badge--danger', bicycle: 'badge--primary',
}
const CATEGORY_LABELS = {
  oto: 'Xe ô tô', xe_may: 'Xe máy', xe_dap: 'Xe đạp',
}
const CATEGORY_ICONS = {
  oto: 'Car', xe_may: 'Moto', xe_dap: 'Bike',
}

function classLabel(cls) { return CLASS_LABELS[cls] || cls }
function classBadge(cls) { return CLASS_BADGES[cls] || 'badge--info' }
function categoryLabel(cat) { return CATEGORY_LABELS[cat] || cat }
function categoryIcon(cat) { return CATEGORY_ICONS[cat] || 'Car' }

// ── API ────────────────────────────────────────────────────────
function addDetections(vehicles, timestamp) {
  if (!vehicles?.length) return

  const now = timestamp || new Date().toISOString()
  let added = 0

  for (const v of vehicles) {
    const item = {
      id: Date.now() + Math.random(),
      class_name: v.class_name,
      category: v.category,
      conf: v.bbox?.conf || 0,
      timestamp: now,
      isNew: true,
    }
    items.value.unshift(item)
    added++

    // Remove isNew after animation
    setTimeout(() => {
      const idx = items.value.findIndex(i => i.id === item.id)
      if (idx !== -1) items.value[idx].isNew = false
    }, 2000)
  }

  // Trim
  if (items.value.length > props.maxItems) {
    items.value = items.value.slice(0, props.maxItems)
  }

  // New count badge
  newCount.value += added
  clearTimeout(newCountTimer)
  newCountTimer = setTimeout(() => { newCount.value = 0 }, 3000)

  // Scroll top
  nextTick(() => {
    if (listRef.value) listRef.value.scrollTop = 0
  })
}

function clearFeed() {
  items.value = []
  newCount.value = 0
}

// ── Helpers ────────────────────────────────────────────────────
function formatTime(ts) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return ts }
}

defineExpose({ addDetections, clearFeed })
onUnmounted(() => clearTimeout(newCountTimer))
</script>

<style scoped>
.dfeed {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
}

/* Header */
.dfeed-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px var(--sp-md);
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.dfeed-title { display: flex; align-items: center; gap: var(--sp-sm); }
.dfeed-icon  { font-size: 1.1rem; }
.dfeed-title h3 { font-size: 0.9rem; margin: 0; }
.dfeed-actions { display: flex; align-items: center; gap: var(--sp-sm); }

.count-badge {
  background: rgba(59,130,246,0.2);
  color: #60a5fa;
  border: 1px solid rgba(59,130,246,0.3);
  border-radius: var(--radius-full);
  font-size: 0.7rem;
  padding: 1px 7px;
  font-weight: 700;
}
.new-badge {
  background: #3b82f6;
  color: #fff;
  border-radius: var(--radius-full);
  font-size: 0.7rem;
  padding: 2px 8px;
  font-weight: 700;
}
@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
}
.animate-bounce { animation: bounce 0.6s ease infinite; }

/* List */
.dfeed-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--sp-sm);
  scroll-behavior: smooth;
}
.dfeed-list::-webkit-scrollbar { width: 4px; }
.dfeed-list::-webkit-scrollbar-track { background: transparent; }
.dfeed-list::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 2px; }

/* Empty */
.dfeed-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-sm);
  padding: var(--sp-2xl) var(--sp-lg);
  color: var(--text-muted);
}
.empty-icon { font-size: 2.5rem; opacity: 0.5; }
.empty-sub  { font-size: 0.78rem; opacity: 0.7; }

/* Transition */
.feed-item-enter-active { transition: all 0.35s ease; }
.feed-item-enter-from   { opacity: 0; transform: translateY(-12px); }
.feed-item-leave-active { transition: all 0.25s ease; position: absolute; }
.feed-item-leave-to     { opacity: 0; transform: translateX(20px); }

/* Feed item */
.feed-item {
  display: flex;
  gap: var(--sp-sm);
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  margin-bottom: 6px;
  background: var(--bg-surface);
  transition: border-color 0.3s, background 0.3s;
  align-items: center;
}
.feed-item--new {
  border-color: rgba(59,130,246,0.5);
  background: rgba(59,130,246,0.06);
  animation: itemFlash 0.5s ease;
}
@keyframes itemFlash {
  0%  { background: rgba(59,130,246,0.25); }
  100%{ background: rgba(59,130,246,0.06); }
}

/* Category border accent */
.feed-item--oto    { border-left: 3px solid #22c55e; }
.feed-item--xe_may { border-left: 3px solid #ef4444; }
.feed-item--xe_dap { border-left: 3px solid #8b5cf6; }

/* Icon */
.item-icon {
  width: 36px; height: 36px;
  border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  font-size: 1.2rem;
  flex-shrink: 0;
}
.icon--oto    { background: rgba(34,197,94,0.12); }
.icon--xe_may { background: rgba(239,68,68,0.12); }
.icon--xe_dap { background: rgba(139,92,246,0.12); }

/* Info */
.item-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.item-top  { display: flex; align-items: center; gap: var(--sp-xs); }
.item-conf { font-size: 0.68rem; color: var(--text-muted); margin-left: auto; }
.item-bottom { display: flex; align-items: center; gap: var(--sp-sm); font-size: 0.7rem; color: var(--text-muted); }
.item-category { opacity: 0.7; }
.item-time { margin-left: auto; }

.mono { font-family: var(--font-mono); }
.btn--sm { padding: 6px 10px; font-size: 0.8rem; }
</style>
