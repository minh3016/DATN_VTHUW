<template>
  <div class="app-layout" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <!-- Sidebar -->
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar__logo">
        <div class="logo-icon">
          <LucideIcon name="shield-check" :size="22" />
        </div>
        <div class="logo-text" v-show="!sidebarCollapsed">
          <span class="logo-title">TrafficAI</span>
          <span class="logo-sub">Giám sát vi phạm</span>
        </div>
      </div>

      <div class="sidebar__section-label" v-show="!sidebarCollapsed">ĐIỀU HƯỚNG</div>
      <nav class="sidebar__nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          active-class="nav-item--active"
          :exact="item.exact"
          :title="item.label"
        >
          <LucideIcon :name="item.icon" :size="20" />
          <span class="nav-label" v-show="!sidebarCollapsed">{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar__section-label" v-show="!sidebarCollapsed">HỆ THỐNG</div>
      <div class="sidebar__status" v-show="!sidebarCollapsed">
        <div class="status-row">
          <span class="status-dot" :class="backendOnline ? 'status-dot--online' : 'status-dot--offline'"></span>
          <span class="status-name">Backend API</span>
          <span class="status-val" :class="backendOnline ? 'text-success' : 'text-danger'">
            {{ backendOnline ? 'Online' : 'Offline' }}
          </span>
        </div>
        <div class="status-row">
          <span class="status-dot" :class="modelsStatus.vehicle ? 'status-dot--online' : 'status-dot--offline'"></span>
          <span class="status-name">Vehicle AI</span>
          <span class="status-val">{{ modelsStatus.vehicle ? '✓' : '✗' }}</span>
        </div>
        <div class="status-row">
          <span class="status-dot" :class="modelsStatus.violation ? 'status-dot--online' : 'status-dot--offline'"></span>
          <span class="status-name">Violation AI</span>
          <span class="status-val">{{ modelsStatus.violation ? '✓' : '✗' }}</span>
        </div>
        <div class="status-row">
          <span class="status-dot" :class="modelsStatus.plate ? 'status-dot--online' : 'status-dot--offline'"></span>
          <span class="status-name">Plate AI</span>
          <span class="status-val">{{ modelsStatus.plate ? '✓' : '✗' }}</span>
        </div>
      </div>

      <div class="sidebar__footer" v-show="!sidebarCollapsed">
        <span class="version-tag">v4.0 · YOLOv8n</span>
      </div>
    </aside>

    <!-- Main area -->
    <div class="main-wrapper">
      <!-- Top Header -->
      <header class="top-header">
        <div class="header-left">
          <button class="btn--icon header-toggle" @click="sidebarCollapsed = !sidebarCollapsed" title="Thu gọn sidebar">
            <LucideIcon :name="sidebarCollapsed ? 'panel-left-open' : 'panel-left-close'" :size="20" />
          </button>
          <div class="breadcrumb">
            <LucideIcon name="home" :size="15" />
            <span class="breadcrumb-sep">/</span>
            <span class="breadcrumb-current">{{ currentPageTitle }}</span>
          </div>
        </div>
        <div class="header-right">
          <div class="header-status" v-if="backendOnline">
            <span class="status-dot status-dot--online"></span>
            <span>{{ modelCount }}/3 AI Models</span>
          </div>
          <div class="header-status header-status--danger" v-else>
            <span class="status-dot status-dot--offline"></span>
            <span>Offline</span>
          </div>
          <div class="header-clock">
            <LucideIcon name="clock" :size="15" />
            <span class="mono">{{ currentTime }}</span>
          </div>
        </div>
      </header>

      <!-- Main Content -->
      <main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { getHealth } from '@/api/index.js'
import LucideIcon from '@/components/LucideIcon.vue'

const route = useRoute()

const sidebarCollapsed = ref(false)
const backendOnline = ref(false)
const currentTime = ref('')
const modelsStatus = reactive({
  vehicle: false,
  violation: false,
  plate: false,
})

const navItems = [
  { path: '/', icon: 'layout-dashboard', label: 'Tổng quan', exact: true },
  { path: '/upload', icon: 'film', label: 'Phân tích Video', exact: false },
  { path: '/violations', icon: 'alert-triangle', label: 'Vi phạm giao thông', exact: false },
  { path: '/history', icon: 'car', label: 'Lịch sử phương tiện', exact: false },
  { path: '/plates', icon: 'credit-card', label: 'Biển số xe', exact: false },
]

const currentPageTitle = computed(() => {
  const item = navItems.find(n => n.path === route.path)
  return item?.label || route.meta?.title || 'Tổng quan'
})

const modelCount = computed(() => {
  return [modelsStatus.vehicle, modelsStatus.violation, modelsStatus.plate].filter(Boolean).length
})

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('vi-VN', { hour12: false })
}

async function checkHealth() {
  try {
    const data = await getHealth()
    backendOnline.value = data.status === 'ok'
    modelsStatus.vehicle = data.models?.vehicle_detector === true
    modelsStatus.violation = data.models?.violation_detector === true
    modelsStatus.plate = data.models?.plate_recognizer === true
  } catch {
    backendOnline.value = false
    modelsStatus.vehicle = false
    modelsStatus.violation = false
    modelsStatus.plate = false
  }
}

let healthTimer = null
let clockTimer = null

onMounted(() => {
  checkHealth()
  updateClock()
  healthTimer = setInterval(checkHealth, 15000)
  clockTimer = setInterval(updateClock, 1000)
})
onUnmounted(() => {
  clearInterval(healthTimer)
  clearInterval(clockTimer)
})
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

/* ── Sidebar ─────────────────────────────────────────────────── */
.sidebar {
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  background: var(--bg-surface);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0;
  left: 0;
  height: 100vh;
  z-index: 100;
  transition: width var(--transition-med), min-width var(--transition-med);
  overflow-x: hidden;
  overflow-y: auto;
}
.sidebar.collapsed {
  width: var(--sidebar-collapsed);
  min-width: var(--sidebar-collapsed);
}

.sidebar__logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
  min-height: 68px;
}
.logo-icon {
  width: 40px; height: 40px;
  background: var(--gradient-primary);
  border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  color: white;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(37,99,235,0.3);
}
.logo-title {
  display: block;
  font-size: 1.05rem;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}
.logo-sub {
  display: block;
  font-size: 0.68rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-top: 1px;
}

.sidebar__section-label {
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 16px 20px 6px;
}

.sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0 10px;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 500;
  transition: all var(--transition-fast);
  text-decoration: none;
  position: relative;
  white-space: nowrap;
}
.nav-item:hover {
  background: rgba(37,99,235,0.08);
  color: var(--text-primary);
}
.nav-item--active {
  background: rgba(37,99,235,0.12);
  color: var(--accent-primary);
}
.nav-item--active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px; bottom: 6px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--accent-primary);
}
.collapsed .nav-item { justify-content: center; padding: 10px; }

.sidebar__status {
  padding: 12px 20px;
  border-top: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.78rem;
  color: var(--text-secondary);
}
.status-name { flex: 1; }
.status-val {
  font-weight: 600;
  font-size: 0.72rem;
}

.sidebar__footer {
  padding: 12px 20px;
  border-top: 1px solid var(--border-color);
  text-align: center;
}
.version-tag {
  font-size: 0.68rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

/* ── Main wrapper ────────────────────────────────────────────── */
.main-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-left: var(--sidebar-width);
  transition: margin-left var(--transition-med);
  min-height: 100vh;
}
.sidebar-collapsed .main-wrapper {
  margin-left: var(--sidebar-collapsed);
}

/* ── Top Header ──────────────────────────────────────────────── */
.top-header {
  height: var(--header-height);
  min-height: var(--header-height);
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--sp-lg);
  position: sticky;
  top: 0;
  z-index: 50;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
}
.header-toggle {
  width: 36px; height: 36px;
  display: flex; align-items: center; justify-content: center;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.header-toggle:hover { background: var(--bg-elevated); color: var(--text-primary); }

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  color: var(--text-muted);
}
.breadcrumb-sep { color: var(--text-muted); opacity: 0.4; }
.breadcrumb-current { color: var(--text-primary); font-weight: 600; }

.header-right {
  display: flex;
  align-items: center;
  gap: var(--sp-lg);
}
.header-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8rem;
  color: var(--text-secondary);
  padding: 4px 12px;
  background: rgba(16,185,129,0.08);
  border-radius: var(--radius-full);
  border: 1px solid rgba(16,185,129,0.15);
}
.header-status--danger {
  background: rgba(239,68,68,0.08);
  border-color: rgba(239,68,68,0.15);
  color: #f87171;
}
.header-clock {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8rem;
  color: var(--text-muted);
}

/* ── Main Content ────────────────────────────────────────────── */
.main-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--bg-base);
}

/* ── Page transition ─────────────────────────────────────────── */
.page-enter-active,
.page-leave-active {
  transition: all 0.2s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 1024px) {
  .sidebar { width: var(--sidebar-collapsed); min-width: var(--sidebar-collapsed); }
  .sidebar .logo-text,
  .sidebar .nav-label,
  .sidebar .sidebar__status,
  .sidebar .sidebar__section-label,
  .sidebar .sidebar__footer { display: none !important; }
  .sidebar .nav-item { justify-content: center; padding: 10px; }
  .sidebar .sidebar__logo { justify-content: center; padding: 16px 10px; }
  .main-wrapper { margin-left: var(--sidebar-collapsed); }
  .header-toggle { display: none; }
}

@media (max-width: 768px) {
  .sidebar { display: none; }
  .main-wrapper { margin-left: 0; }
  .header-clock { display: none; }
}
</style>
