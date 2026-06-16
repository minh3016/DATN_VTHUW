<template>
  <div class="vfeed">
    <!-- Header -->
    <div class="vfeed-header">
      <div class="vfeed-title">
        <span class="vfeed-icon">🚨</span>
        <h3>Vi phạm Realtime</h3>
        <span v-if="items.length" class="count-badge">{{ items.length }}</span>
      </div>
      <div class="vfeed-actions">
        <span v-if="newCount > 0" class="new-badge animate-bounce">+{{ newCount }} mới</span>
        <button class="btn btn--ghost btn--sm" @click="clearFeed" title="Xóa feed">🗑</button>
      </div>
    </div>

    <!-- Feed list -->
    <div class="vfeed-list" ref="listRef">
      <!-- Empty state -->
      <div v-if="!items.length" class="vfeed-empty">
        <div class="empty-icon">✅</div>
        <p>Chưa phát hiện vi phạm</p>
        <p class="empty-sub">Vi phạm sẽ xuất hiện ở đây realtime</p>
      </div>

      <!-- Violation items -->
      <TransitionGroup name="feed-item" tag="div" class="feed-items">
        <div
          v-for="item in items"
          :key="item.id"
          class="feed-item"
          :class="{ 'feed-item--new': item.isNew }"
        >
          <!-- Thumbnail -->
          <div class="item-thumb">
            <img
              v-if="item.frame_base64"
              :src="`data:image/jpeg;base64,${item.frame_base64}`"
              class="thumb-img"
              alt="Vi phạm"
              @click="openModal(item)"
            />
            <div v-else class="thumb-placeholder">📷</div>
          </div>

          <!-- Info -->
          <div class="item-info">
            <div class="item-top">
              <span class="badge badge--danger violation-badge">
                {{ violationLabel(item.violation_type) }}
              </span>
              <span class="item-cam">{{ item.camera_id }}</span>
            </div>

            <div v-if="item.plates?.length" class="item-plates">
              <span v-for="p in item.plates" :key="p.text" class="plate-chip mono">
                {{ p.text || '???' }}
              </span>
            </div>

            <div class="item-time">
              {{ formatTime(item.timestamp) }}
              <span v-if="item.location" class="item-loc">• {{ item.location }}</span>
            </div>
          </div>
        </div>
      </TransitionGroup>
    </div>

    <!-- Image modal -->
    <Teleport to="body">
      <div v-if="modalItem" class="modal-overlay" @click.self="modalItem = null">
        <div class="modal-box">
          <button class="modal-close" @click="modalItem = null">✕</button>
          <img
            :src="`data:image/jpeg;base64,${modalItem.frame_base64}`"
            class="modal-img"
            alt="Ảnh vi phạm"
          />
          <div class="modal-info">
            <span class="badge badge--danger">{{ violationLabel(modalItem.violation_type) }}</span>
            <span class="mono" v-if="modalItem.plates?.length">
              Biển số: {{ modalItem.plates.map(p=>p.text).join(', ') }}
            </span>
            <span>Camera: {{ modalItem.camera_id }}</span>
            <span>{{ formatTime(modalItem.timestamp) }}</span>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, nextTick, onUnmounted } from 'vue'

const props = defineProps({
  /** WebSocket object đang kết nối (truyền từ Dashboard) */
  websocket: { type: Object, default: null },
  maxItems: { type: Number, default: 50 },
})

// ── State ──────────────────────────────────────────────────────
const items    = ref([])
const newCount = ref(0)
const listRef  = ref(null)
const modalItem = ref(null)

let newCountTimer = null

// ── API công khai ──────────────────────────────────────────────

/** Thêm 1 violation event vào feed (gọi từ bên ngoài) */
function addViolation(data) {
  const item = {
    id: Date.now() + Math.random(),
    violation_type: data.violation_type || 'no_helmet',
    camera_id: data.camera_id || 'CAM_01',
    location: data.location || null,
    plates: data.plates || [],
    frame_base64: data.frame_base64 || null,
    no_helmet_count: data.no_helmet_count || 0,
    timestamp: data.timestamp || new Date().toISOString(),
    isNew: true,
  }

  // Thêm đầu danh sách (mới nhất trên đầu)
  items.value.unshift(item)

  // Giới hạn số items
  if (items.value.length > props.maxItems) {
    items.value = items.value.slice(0, props.maxItems)
  }

  // Tăng counter
  newCount.value++
  clearTimeout(newCountTimer)
  newCountTimer = setTimeout(() => { newCount.value = 0 }, 3000)

  // Xóa isNew sau animation
  setTimeout(() => {
    const idx = items.value.findIndex(i => i.id === item.id)
    if (idx !== -1) items.value[idx].isNew = false
  }, 2000)

  // Scroll lên đầu
  nextTick(() => {
    if (listRef.value) listRef.value.scrollTop = 0
  })
}

/** Xóa toàn bộ feed */
function clearFeed() {
  items.value = []
  newCount.value = 0
}

/** Mở modal xem ảnh vi phạm */
function openModal(item) {
  if (item.frame_base64) modalItem.value = item
}

// ── Expose cho parent ──────────────────────────────────────────
defineExpose({ addViolation, clearFeed })

// ── Helpers ────────────────────────────────────────────────────
function violationLabel(type) {
  return {
    no_helmet:   '🪖 Không MBH',
    wrong_lane:  '↔ Sai làn',
    red_light:   '🔴 Vượt đèn đỏ',
    speeding:    '⚡ Tốc độ cao',
  }[type] || type
}

function formatTime(ts) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return ts }
}

onUnmounted(() => clearTimeout(newCountTimer))
</script>

<style scoped>
.vfeed {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
}

/* Header */
.vfeed-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px var(--sp-md);
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.vfeed-title { display: flex; align-items: center; gap: var(--sp-sm); }
.vfeed-icon  { font-size: 1.1rem; }
.vfeed-title h3 { font-size: 0.9rem; margin: 0; }
.vfeed-actions { display: flex; align-items: center; gap: var(--sp-sm); }

.count-badge {
  background: rgba(239,68,68,0.2);
  color: #ef4444;
  border: 1px solid rgba(239,68,68,0.3);
  border-radius: var(--radius-full);
  font-size: 0.7rem;
  padding: 1px 7px;
  font-weight: 700;
}
.new-badge {
  background: #ef4444;
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
.vfeed-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--sp-sm);
  scroll-behavior: smooth;
}
.vfeed-list::-webkit-scrollbar { width: 4px; }
.vfeed-list::-webkit-scrollbar-track { background: transparent; }
.vfeed-list::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 2px; }

/* Empty */
.vfeed-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-sm);
  padding: var(--sp-2xl) var(--sp-lg);
  color: var(--text-muted);
}
.empty-icon { font-size: 2.5rem; opacity: 0.5; }
.empty-sub  { font-size: 0.78rem; opacity: 0.7; }

/* Feed items transition */
.feed-item-enter-active { transition: all 0.35s ease; }
.feed-item-enter-from   { opacity: 0; transform: translateY(-12px); }
.feed-item-leave-active { transition: all 0.25s ease; position: absolute; }
.feed-item-leave-to     { opacity: 0; transform: translateX(20px); }

/* Feed item */
.feed-item {
  display: flex;
  gap: var(--sp-sm);
  padding: var(--sp-sm);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  margin-bottom: var(--sp-sm);
  background: var(--bg-surface);
  transition: border-color 0.3s, background 0.3s;
}
.feed-item--new {
  border-color: rgba(239,68,68,0.5);
  background: rgba(239,68,68,0.06);
  animation: itemFlash 0.5s ease;
}
@keyframes itemFlash {
  0%  { background: rgba(239,68,68,0.25); }
  100%{ background: rgba(239,68,68,0.06); }
}

/* Thumbnail */
.item-thumb { flex-shrink: 0; width: 80px; height: 56px; }
.thumb-img {
  width: 100%; height: 100%;
  object-fit: cover;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: transform 0.15s;
}
.thumb-img:hover { transform: scale(1.05); }
.thumb-placeholder {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-base);
  border-radius: var(--radius-sm);
  font-size: 1.5rem; opacity: 0.4;
}

/* Info */
.item-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.item-top  { display: flex; align-items: center; gap: var(--sp-xs); flex-wrap: wrap; }
.violation-badge { font-size: 0.72rem; }
.item-cam  { font-size: 0.7rem; color: var(--text-muted); margin-left: auto; }

.item-plates { display: flex; flex-wrap: wrap; gap: 3px; }
.plate-chip {
  background: rgba(59,130,246,0.1);
  color: var(--text-accent);
  border: 1px solid rgba(59,130,246,0.3);
  border-radius: var(--radius-sm);
  padding: 1px 6px;
  font-size: 0.72rem;
}

.item-time {
  font-size: 0.7rem;
  color: var(--text-muted);
}
.item-loc { opacity: 0.7; }

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
  animation: fadeIn 0.2s ease;
}
.modal-box {
  position: relative;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--sp-lg);
  max-width: 700px;
  width: 95%;
  animation: slideUp 0.25s ease;
}
@keyframes slideUp { from { transform: translateY(20px); opacity: 0; } }
.modal-close {
  position: absolute;
  top: var(--sp-sm);
  right: var(--sp-sm);
  background: rgba(255,255,255,0.1);
  border: none;
  color: var(--text-primary);
  width: 28px; height: 28px;
  border-radius: 50%;
  cursor: pointer;
  font-size: 0.9rem;
  display: flex; align-items: center; justify-content: center;
}
.modal-img { width: 100%; border-radius: var(--radius-md); display: block; }
.modal-info {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
  margin-top: var(--sp-sm);
  flex-wrap: wrap;
  font-size: 0.85rem;
  color: var(--text-secondary);
}
</style>
