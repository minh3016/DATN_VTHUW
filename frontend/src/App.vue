<template>
  <div class="app-layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar__logo">
        <div class="logo-icon">🚦</div>
        <div class="logo-text">
          <span class="logo-title">TrafficAI</span>
          <span class="logo-sub">Violation Detection</span>
        </div>
      </div>

      <nav class="sidebar__nav">
        <router-link to="/" class="nav-item" active-class="nav-item--active" :exact="true">
          <span class="nav-icon">📊</span>
          <span>Dashboard</span>
        </router-link>
        <router-link to="/upload" class="nav-item" active-class="nav-item--active">
          <span class="nav-icon">📤</span>
          <span>Upload & Phân tích</span>
        </router-link>
        <router-link to="/violations" class="nav-item" active-class="nav-item--active">
          <span class="nav-icon">⚠️</span>
          <span>Vi phạm</span>
        </router-link>
        <router-link to="/history" class="nav-item" active-class="nav-item--active">
          <span class="nav-icon">🚗</span>
          <span>Phương tiện</span>
        </router-link>
      </nav>

      <div class="sidebar__status">
        <div class="status-item">
          <span class="status-dot" :class="backendOnline ? 'status-dot--online' : 'status-dot--offline'"></span>
          <span>Backend</span>
          <span class="status-val">{{ backendOnline ? 'Online' : 'Offline' }}</span>
        </div>
        <div class="status-item">
          <span class="status-dot" :class="modelsStatus.vehicle ? 'status-dot--online' : 'status-dot--offline'"></span>
          <span>Vehicle AI</span>
          <span class="status-val">{{ modelsStatus.vehicle ? '✓' : '✗' }}</span>
        </div>
        <div class="status-item">
          <span class="status-dot" :class="modelsStatus.violation ? 'status-dot--online' : 'status-dot--offline'"></span>
          <span>Violation AI</span>
          <span class="status-val">{{ modelsStatus.violation ? '✓' : '✗' }}</span>
        </div>
        <div class="status-item">
          <span class="status-dot" :class="modelsStatus.plate ? 'status-dot--online' : 'status-dot--offline'"></span>
          <span>Plate AI</span>
          <span class="status-val">{{ modelsStatus.plate ? '✓' : '✗' }}</span>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="main-content">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { getHealth } from '@/api/index.js'

const backendOnline = ref(false)
const modelsStatus = reactive({
  vehicle: false,
  violation: false,
  plate: false,
})

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
onMounted(() => {
  checkHealth()
  healthTimer = setInterval(checkHealth, 15000)
})
onUnmounted(() => clearInterval(healthTimer))
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

/* Sidebar */
.sidebar {
  width: 240px;
  min-width: 240px;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  padding: var(--sp-lg) 0;
  position: sticky;
  top: 0;
  height: 100vh;
}

.sidebar__logo {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
  padding: 0 var(--sp-lg) var(--sp-lg);
  border-bottom: 1px solid var(--border-color);
  margin-bottom: var(--sp-lg);
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: var(--gradient-primary);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.3rem;
  box-shadow: var(--shadow-glow);
}

.logo-title {
  display: block;
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
}
.logo-sub {
  display: block;
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: var(--sp-xs);
  padding: 0 var(--sp-sm);
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  padding: 10px 14px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 0.9rem;
  font-weight: 500;
  transition: all var(--transition-fast);
  text-decoration: none;
}
.nav-item:hover {
  background: rgba(59,130,246,0.1);
  color: var(--text-primary);
}
.nav-item--active {
  background: rgba(59,130,246,0.15);
  color: var(--accent-primary);
  border-left: 3px solid var(--accent-primary);
}
.nav-icon { font-size: 1.1rem; }

.sidebar__status {
  padding: var(--sp-md) var(--sp-lg);
  border-top: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: var(--sp-sm);
}
.status-item {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  font-size: 0.8rem;
  color: var(--text-secondary);
}
.status-val {
  margin-left: auto;
  font-weight: 600;
  font-size: 0.75rem;
}

/* Main */
.main-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

/* Page transition */
.page-enter-active,
.page-leave-active {
  transition: all 0.25s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateX(10px);
}
.page-leave-to {
  opacity: 0;
  transform: translateX(-10px);
}

@media (max-width: 768px) {
  .sidebar { width: 60px; min-width: 60px; }
  .logo-text, .nav-item span:last-child, .sidebar__status .status-val { display: none; }
  .nav-item { justify-content: center; }
  .sidebar__logo { justify-content: center; }
}
</style>
