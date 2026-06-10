<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const navItems = [
  { name: '仪表盘', path: '/dashboard', icon: 'dashboard' },
  { name: '采集任务', path: '/tasks', icon: 'tasks' },
  { name: '库存管理', path: '/inventory', icon: 'inventory' },
  { name: 'QQ账号', path: '/accounts', icon: 'accounts' },
  { name: '运行日志', path: '/logs', icon: 'logs' },
]

const activeRoute = computed(() => route.path)

function navigate(path: string) {
  router.push(path)
}

function logout() {
  localStorage.removeItem('agent-token')
  localStorage.removeItem('agent-info')
  router.push('/login')
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="logo">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--accent-primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10" />
          <circle cx="12" cy="12" r="3" />
          <line x1="12" y1="2" x2="12" y2="6" />
          <line x1="12" y1="18" x2="12" y2="22" />
          <line x1="2" y1="12" x2="6" y2="12" />
          <line x1="18" y1="12" x2="22" y2="12" />
        </svg>
        <span class="logo-text">凭证采集站</span>
      </div>
    </div>

    <nav class="sidebar-nav">
      <div
        v-for="item in navItems"
        :key="item.path"
        class="nav-item"
        :class="{ active: activeRoute === item.path }"
        @click="navigate(item.path)"
      >
        <div class="nav-indicator" />
        <div class="nav-icon">
          <svg v-if="item.icon === 'dashboard'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
          </svg>
          <svg v-else-if="item.icon === 'tasks'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
          </svg>
          <svg v-else-if="item.icon === 'inventory'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" />
          </svg>
          <svg v-else-if="item.icon === 'logs'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
          </svg>
          <svg v-else-if="item.icon === 'accounts'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        </div>
        <span class="nav-label">{{ item.name }}</span>
      </div>
    </nav>

    <div class="sidebar-footer">
      <div class="status-indicator">
        <span class="status-dot status-dot-green" />
        <div class="status-text">
          <span class="status-label">平台连接</span>
          <span class="status-value">已连接</span>
        </div>
      </div>
      <div class="logout-btn" @click="logout">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
        </svg>
        <span>退出登录</span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;top:0;left:0;width:var(--sidebar-width);height:100vh;
  background:var(--bg-secondary);border-right:1px solid var(--border-color);
  display:flex;flex-direction:column;z-index:100;
}
.sidebar-header{padding:20px 16px;border-bottom:1px solid var(--border-color)}
.logo{display:flex;align-items:center;gap:10px}
.logo-text{font-size:16px;font-weight:700;color:var(--text-primary);letter-spacing:-0.02em}
.sidebar-nav{flex:1;padding:8px;display:flex;flex-direction:column;gap:2px;overflow-y:auto}
.nav-item{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:var(--radius-md);cursor:pointer;position:relative;color:var(--text-secondary);font-size:13px;font-weight:500;transition:all .2s}
.nav-item:hover{background:var(--bg-hover);color:var(--text-primary)}
.nav-item.active{background:var(--bg-tertiary);color:var(--accent-primary)}
.nav-indicator{position:absolute;left:0;top:50%;transform:translateY(-50%);width:3px;height:0;background:var(--accent-primary);border-radius:0 3px 3px 0;transition:height .2s}
.nav-item.active .nav-indicator{height:20px}
.nav-icon{display:flex;align-items:center;justify-content:center;width:20px;height:20px;flex-shrink:0}
.nav-label{flex:1}
.sidebar-footer{padding:12px 16px;border-top:1px solid var(--border-color);display:flex;flex-direction:column;gap:10px}
.status-indicator{display:flex;align-items:center;gap:8px}
.status-text{display:flex;flex-direction:column;gap:1px}
.status-label{font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.03em}
.status-value{font-size:12px;color:var(--text-secondary);font-weight:500}
.logout-btn{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:var(--radius-sm);cursor:pointer;color:var(--text-muted);font-size:12px;transition:all .2s}
.logout-btn:hover{background:var(--bg-hover);color:var(--accent-red,#ef4444)}
</style>
