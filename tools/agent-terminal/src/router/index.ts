import { createRouter, createWebHistory } from 'vue-router'
import DashboardPage from '@/pages/DashboardPage.vue'
import TasksPage from '@/pages/TasksPage.vue'
import InventoryPage from '@/pages/InventoryPage.vue'
import LogsPage from '@/pages/LogsPage.vue'
import LoginPage from '@/pages/LoginPage.vue'
import AccountsPage from '@/pages/AccountsPage.vue'
import CollectorBrowser from '@/pages/CollectorBrowser.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: LoginPage,
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: DashboardPage,
    meta: { requiresAuth: true, title: '采集控制台' },
  },
  {
    path: '/collector/browser',
    name: 'CollectorBrowser',
    component: CollectorBrowser,
    meta: { requiresAuth: true, title: '浏览器采集' },
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: TasksPage,
    meta: { requiresAuth: true, title: '采集任务' },
  },
  {
    path: '/inventory',
    name: 'Inventory',
    component: InventoryPage,
    meta: { requiresAuth: true, title: '库存管理' },
  },
  {
    path: '/accounts',
    name: 'Accounts',
    component: AccountsPage,
    meta: { requiresAuth: true, title: '账号管理' },
  },
  {
    path: '/logs',
    name: 'Logs',
    component: LogsPage,
    meta: { requiresAuth: true, title: '运行日志' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ── Auth guard ──
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('agent-token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.name === 'Login' && token) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
