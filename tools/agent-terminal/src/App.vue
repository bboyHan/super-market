<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const sidebarOpen = ref(true)

const navItems = [
  { path: '/', name: 'EasyMode', label: '🎯 简易模式', icon: '🎯' },
  { path: '/dashboard', name: 'Dashboard', label: '📊 仪表盘', icon: '📊' },
  { path: '/settings', name: 'Settings', label: '⚙️ 设置', icon: '⚙️' },
]

const currentLabel = computed(() => {
  const item = navItems.find(n => n.name === route.name)
  return item?.label || 'DataProbe'
})
</script>

<template>
  <div class="app-shell">
    <!-- Sidebar -->
    <aside class="sidebar" :class="{ collapsed: !sidebarOpen }">
      <div class="sidebar-header">
        <div class="logo">⚡</div>
        <div v-if="sidebarOpen" class="logo-text">DataProbe</div>
      </div>
      <nav class="sidebar-nav">
        <div
          v-for="item in navItems"
          :key="item.name"
          class="nav-item"
          :class="{ active: route.name === item.name }"
          @click="router.push(item.path)"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span v-if="sidebarOpen" class="nav-label">{{ item.label }}</span>
        </div>
      </nav>
      <div class="sidebar-footer">
        <button class="collapse-btn" @click="sidebarOpen = !sidebarOpen">
          {{ sidebarOpen ? '◀' : '▶' }}
        </button>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app { height: 100%; width: 100%; }

.app-shell {
  display: flex;
  height: 100vh;
  background: #0d1117;
  color: #c9d1d9;
}

.sidebar {
  width: 220px;
  background: #161b22;
  border-right: 1px solid #30363d;
  display: flex;
  flex-direction: column;
  transition: width 0.2s;
  flex-shrink: 0;
}

.sidebar.collapsed { width: 60px; }

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  border-bottom: 1px solid #30363d;
}

.logo { font-size: 24px; }
.logo-text { font-size: 16px; font-weight: 700; color: #58a6ff; }

.sidebar-nav { flex: 1; padding: 8px; }

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: 2px;
  color: #8b949e;
}

.nav-item:hover { background: #21262d; color: #c9d1d9; }
.nav-item.active { background: #1c2d4e; color: #58a6ff; }

.nav-icon { font-size: 16px; width: 24px; text-align: center; }
.nav-label { font-size: 13px; font-weight: 500; white-space: nowrap; }

.sidebar-footer { padding: 12px; border-top: 1px solid #30363d; }

.collapse-btn {
  width: 100%; padding: 6px; background: #21262d; border: 1px solid #30363d;
  border-radius: 6px; color: #8b949e; cursor: pointer; font-size: 12px;
}
.collapse-btn:hover { background: #30363d; }

.main-content { flex: 1; overflow-y: auto; }
</style>
