import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Dashboard from './views/Dashboard.vue'
import UploadAnalysis from './views/UploadAnalysis.vue'
import DetectionHistory from './views/DetectionHistory.vue'
import ViolationHistory from './views/ViolationHistory.vue'
import './assets/main.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard, meta: { title: 'Dashboard' } },
    { path: '/upload', component: UploadAnalysis, meta: { title: 'Upload & Phân tích' } },
    { path: '/violations', component: ViolationHistory, meta: { title: 'Lịch sử vi phạm' } },
    { path: '/history', component: DetectionHistory, meta: { title: 'Lịch sử phương tiện' } },
  ],
})

router.afterEach((to) => {
  document.title = `${to.meta.title || 'Dashboard'} | Traffic Violation AI`
})

const pinia = createPinia()
const app = createApp(App)
app.use(pinia)
app.use(router)
app.mount('#app')
