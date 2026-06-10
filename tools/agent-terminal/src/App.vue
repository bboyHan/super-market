<script setup lang="ts">
import { onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { useTasksStore } from '@/stores/tasks'
import UserBadge from '@/components/UserBadge.vue'

const theme = useThemeStore()
const tasks = useTasksStore()
const route = useRoute()

const isLoginPage = computed(() => route.name === 'Login')
const isDashboard = computed(() => route.name === 'Dashboard')

onMounted(() => {
  theme.init()
  tasks.connectSSE()
})

onUnmounted(() => {
  tasks.disconnectSSE()
})
</script>

<template>
  <!-- Login page -->
  <div v-if="isLoginPage" class="full-page" :class="{ light: !theme.isDark }">
    <router-view />
  </div>

  <!-- Dashboard (has its own topbar + layout) -->
  <router-view v-else-if="isDashboard" />

  <!-- Other pages: uses simple topbar + content -->
  <div v-else class="page-frame" :class="{ light: !theme.isDark }">
    <router-view />
  </div>

  <!-- 全局用户信息（非登录页右上角显示） -->
  <div v-if="!isLoginPage" class="global-user-badge">
    <UserBadge />
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app { height: 100%; width: 100%; }

.full-page, .page-frame {
  min-height: 100vh;
  background: #0f0f1a;
  color: #e0e0e0;
}
.light { background: #f5f5f5; color: #333; }

/* 全局用户信息定位 */
.global-user-badge {
  position: fixed;
  top: 12px;
  right: 16px;
  z-index: 9999;
}

/* Shared transitions */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
