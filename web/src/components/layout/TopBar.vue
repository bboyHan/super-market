<script setup lang="ts">
import { useThemeStore } from '@/stores/theme'
import { useUserStore } from '@/stores/user'
import { Moon, Sun, Menu, Bell, LogOut, User } from 'lucide-vue-next'

const emit = defineEmits<{
  toggleMobileSidebar: []
}>()

const themeStore = useThemeStore()
const userStore = useUserStore()
</script>

<template>
  <header
    class="flex items-center justify-between h-16 px-4 md:px-6 border-b border-[var(--color-border)] bg-[var(--color-card)] transition-colors duration-300"
  >
    <!-- Left side -->
    <div class="flex items-center gap-3">
      <!-- Mobile hamburger -->
      <button
        class="lg:hidden p-2 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-all duration-200"
        @click="emit('toggleMobileSidebar')"
      >
        <Menu class="w-5 h-5" />
      </button>

      <!-- Page title from route -->
      <h1 class="text-lg font-semibold text-[var(--color-text)] hidden sm:block">
        {{ $route.meta?.title || 'Super Market' }}
      </h1>
    </div>

    <!-- Right side -->
    <div class="flex items-center gap-2">
      <!-- Theme toggle -->
      <button
        class="p-2 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-all duration-200"
        @click="themeStore.toggle()"
        :title="themeStore.mode === 'dark' ? '切换到浅色模式' : '切换到深色模式'"
      >
        <Sun v-if="themeStore.mode === 'dark'" class="w-5 h-5" />
        <Moon v-else class="w-5 h-5" />
      </button>

      <!-- Notifications -->
      <button
        class="relative p-2 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-all duration-200"
        title="通知"
      >
        <Bell class="w-5 h-5" />
        <span class="absolute top-1.5 right-1.5 w-2 h-2 bg-brand-danger rounded-full" />
      </button>

      <!-- User info -->
      <div class="flex items-center gap-2 ml-2 pl-2 border-l border-[var(--color-border)]">
        <div
          class="w-8 h-8 rounded-full bg-[var(--color-accent)]/20 flex items-center justify-center text-[var(--color-accent)] text-sm font-medium"
        >
          {{ (userStore.user?.username || 'U').charAt(0).toUpperCase() }}
        </div>
        <div class="hidden md:block">
          <p class="text-sm font-medium text-[var(--color-text)]">
            {{ userStore.user?.username || '用户' }}
          </p>
          <p class="text-xs text-[var(--color-text-muted)]">
            {{ userStore.user?.role === 'ADMIN' ? '管理员' : userStore.user?.role === 'SUPPLIER' ? '供应商' : userStore.user?.role === 'AGENT' ? '代理商' : '' }}
          </p>
        </div>
        <button
          class="p-2 rounded-lg text-[var(--color-text-muted)] hover:text-brand-danger hover:bg-brand-danger/10 transition-all duration-200"
          title="退出登录"
          @click="userStore.logout(); $router.push('/login')"
        >
          <LogOut class="w-4 h-4" />
        </button>
      </div>
    </div>
  </header>
</template>
