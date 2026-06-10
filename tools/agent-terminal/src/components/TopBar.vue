<script setup lang="ts">
import { useThemeStore } from '@/stores/theme'

const theme = useThemeStore()

defineProps<{
  title: string
}>()

const emits = defineEmits<{
  (e: 'select-account', id: string): void
  (e: 'select-emulator', id: string): void
}>()

const accounts = [
  { id: 'acc-1', name: '京东账号 #001', platform: '京东' },
  { id: 'acc-2', name: '淘宝账号 #001', platform: '淘宝' },
  { id: 'acc-3', name: '抖音账号 #001', platform: '抖音' },
]

const emulators = [
  { id: 'em-1', name: '夜神模拟器', status: '运行中' },
  { id: 'em-2', name: 'BlueStacks', status: '已停止' },
]
</script>

<template>
  <header class="topbar">
    <h1 class="topbar-title">{{ title }}</h1>

    <div class="topbar-actions">
      <div class="topbar-select-group">
        <select class="select select-sm" @change="($event) => emits('select-account', ($event.target as HTMLSelectElement).value)">
          <option value="" disabled selected>选择账号</option>
          <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
            {{ acc.name }} ({{ acc.platform }})
          </option>
        </select>

        <select class="select select-sm" @change="($event) => emits('select-emulator', ($event.target as HTMLSelectElement).value)">
          <option value="" disabled selected>模拟器</option>
          <option v-for="em in emulators" :key="em.id" :value="em.id">
            {{ em.name }} — {{ em.status }}
          </option>
        </select>
      </div>

      <button class="theme-toggle" @click="theme.toggle()" :title="theme.isDark ? '切换到浅色模式' : '切换到深色模式'">
        <!-- Sun icon (light mode) -->
        <svg v-if="!theme.isDark" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5" />
          <line x1="12" y1="1" x2="12" y2="3" />
          <line x1="12" y1="21" x2="12" y2="23" />
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
          <line x1="1" y1="12" x2="3" y2="12" />
          <line x1="21" y1="12" x2="23" y2="12" />
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
        </svg>
        <!-- Moon icon (dark mode) -->
        <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      </button>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  height: 60px;
}

.topbar-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.topbar-select-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.select-sm {
  padding: 6px 28px 6px 10px;
  font-size: 12px;
  min-width: 140px;
}

.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.theme-toggle:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--border-light);
}
</style>
