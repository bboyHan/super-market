import { createRouter, createWebHistory } from 'vue-router'
import EasyMode from '../pages/EasyMode.vue'

const routes = [
  { path: '/', name: 'EasyMode', component: EasyMode },
  { path: '/dashboard', name: 'Dashboard', component: () => import('../pages/Dashboard.vue') },
  { path: '/settings', name: 'Settings', component: () => import('../pages/Settings.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
