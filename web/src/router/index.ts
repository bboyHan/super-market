import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/login.vue'),
    meta: { layout: 'blank' },
  },
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/pages/dashboard/index.vue'),
    meta: { title: '仪表盘', icon: 'LayoutDashboard' },
  },
  {
    path: '/orders',
    name: 'Orders',
    component: () => import('@/pages/orders/index.vue'),
    meta: { title: '订单管理', icon: 'ShoppingCart' },
  },
  {
    path: '/agents',
    name: 'Agents',
    component: () => import('@/pages/agents/index.vue'),
    meta: { title: '代理商管理', icon: 'Users' },
  },
  {
    path: '/finance',
    name: 'Finance',
    component: () => import('@/pages/finance/index.vue'),
    meta: { title: '财务管理', icon: 'Wallet' },
  },
  {
    path: '/apichannel',
    name: 'ApiChannel',
    component: () => import('@/pages/apichannel/index.vue'),
    meta: { title: 'API渠道', icon: 'Globe' },
  },
  // ── Admin Routes ──
  {
    path: '/admin/accounts',
    name: 'AdminAccounts',
    component: () => import('@/pages/admin/accounts.vue'),
    meta: { title: '账号管理', icon: 'Shield', role: 'ADMIN' },
  },
  {
    path: '/admin/simulate',
    name: 'AdminSimulate',
    component: () => import('@/pages/admin/simulate.vue'),
    meta: { title: '模拟终端', icon: 'Terminal', role: 'ADMIN' },
  },
  {
    path: '/admin/deposits',
    name: 'AdminDeposits',
    component: () => import('@/pages/admin/deposits.vue'),
    meta: { title: '充值审核', icon: 'DollarSign', role: 'ADMIN' },
  },
  {
    path: '/admin/product-configs',
    name: 'AdminProductConfigs',
    component: () => import('@/pages/admin/product-configs.vue'),
    meta: { title: '商品配置', icon: 'Settings', role: 'ADMIN' },
  },
  {
    path: '/admin/auth-tokens',
    name: 'AdminAuthTokens',
    component: () => import('@/pages/admin/auth-tokens.vue'),
    meta: { title: '工具授权', icon: 'Key', role: 'ADMIN' },
  },
  {
    path: '/admin/risk-dashboard',
    name: 'AdminRiskDashboard',
    component: () => import('@/pages/admin/risk-dashboard.vue'),
    meta: { title: '风控大盘', role: 'ADMIN' },
  },
  {
    path: '/admin/audit-logs',
    name: 'AdminAuditLogs',
    component: () => import('@/pages/admin/audit-logs.vue'),
    meta: { title: '审计日志', role: 'ADMIN' },
  },
  {
    path: '/admin/announcements',
    name: 'AdminAnnouncements',
    component: () => import('@/pages/admin/announcements.vue'),
    meta: { title: '系统公告', role: 'ADMIN' },
  },
  {
    path: '/admin/fee-config',
    name: 'AdminFeeConfig',
    component: () => import('@/pages/admin/fee-config.vue'),
    meta: { title: '手续费率', role: 'ADMIN' },
  },
  {
    path: '/products/:id/routing',
    name: 'ProductRouting',
    component: () => import('@/pages/products/routing-config.vue'),
    meta: { title: '路由策略' },
  },
  {
    path: '/agent/auth-tokens',
    name: 'AgentAuthTokens',
    component: () => import('@/pages/agent/auth-tokens.vue'),
    meta: { title: '工具授权', icon: 'Key', role: 'AGENT' },
  },
  {
    path: '/suppliers',
    name: 'Suppliers',
    component: () => import('@/pages/suppliers/index.vue'),
    meta: { title: '供应商管理', icon: 'Store' },
  },
  {
    path: '/deposit',
    name: 'Deposit',
    component: () => import('@/pages/deposit/index.vue'),
    meta: { title: '积分充值', icon: 'DollarSign' },
  },
  {
    path: '/products',
    name: 'Products',
    component: () => import('@/pages/products/index.vue'),
    meta: { title: '货品管理', icon: 'Package' },
  },
  {
    path: '/agent',
    children: [
      {
        path: 'dashboard',
        name: 'AgentDashboard',
        component: () => import('@/pages/agent/dashboard.vue'),
        meta: { title: '代理商仪表盘', icon: 'BarChart3' },
      },
      {
        path: 'delivery',
        name: 'AgentDelivery',
        component: () => import('@/pages/agent/delivery.vue'),
        meta: { title: '交付管理', icon: 'Package' },
      },
      {
        path: 'inventory',
        name: 'AgentInventory',
        component: () => import('@/pages/agent/inventory.vue'),
        meta: { title: '库存管理', icon: 'Warehouse' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/pages/dashboard/index.vue'),
    meta: { title: '404 - 页面未找到' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guard - redirect to login if not authenticated
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('auth-token')
  if (to.name !== 'Login' && !token) {
    next({ name: 'Login' })
  } else if (to.name === 'Login' && token) {
    next({ name: 'Dashboard' })
  } else {
    next()
  }
})

export default router
