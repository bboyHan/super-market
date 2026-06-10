<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { useUserStore } from '@/stores/user'
import { Store, Moon, Sun, Eye, EyeOff } from 'lucide-vue-next'
import type { UserInfo } from '@/types'
import api from '@/utils/api'

const router = useRouter()
const themeStore = useThemeStore()
const userStore = useUserStore()

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const rememberMe = ref(false)
const loading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  if (!username.value || !password.value) {
    errorMsg.value = '请输入用户名和密码'
    return
  }

  loading.value = true
  errorMsg.value = ''

  try {
    const res = await api.post<{
      access_token: string
      token_type: string
      user_id: number
      username: string
      role: string
      reference_id: number | null
    }>('/api/auth/login', {
      username: username.value,
      password: password.value,
    })

    userStore.setToken(res.access_token)
    userStore.setUser({
      id: String(res.user_id),
      username: res.username,
      role: res.role,
      reference_id: res.reference_id,
    } as UserInfo)

    // Redirect based on role
    if (res.role === 'ADMIN' || res.role === 'SUPPLIER') {
      await router.push('/')
    } else if (res.role === 'AGENT') {
      await router.push('/agent/dashboard')
    } else {
      await router.push('/')
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '登录失败，请检查用户名和密码'
    errorMsg.value = msg
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-[var(--color-bg)] transition-colors duration-300">
    <!-- Theme toggle (top right) -->
    <button
      class="fixed top-4 right-4 p-2 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-card)] transition-all duration-200"
      @click="themeStore.toggle()"
      :title="themeStore.mode === 'dark' ? '切换到浅色模式' : '切换到深色模式'"
    >
      <Sun v-if="themeStore.mode === 'dark'" class="w-5 h-5" />
      <Moon v-else class="w-5 h-5" />
    </button>

    <div class="w-full max-w-sm mx-4">
      <!-- Logo -->
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-[var(--color-accent)]/10 mb-4">
          <Store class="w-7 h-7 text-[var(--color-accent)]" />
        </div>
        <h1 class="text-2xl font-bold text-[var(--color-text)]">Super Market</h1>
        <p class="mt-1.5 text-sm text-[var(--color-text-muted)]">供应商管理系统</p>
      </div>

      <!-- Login form -->
      <div class="card p-6">
        <form @submit.prevent="handleLogin" class="space-y-4">
          <!-- Error message -->
          <div
            v-if="errorMsg"
            class="p-3 rounded-lg text-sm text-brand-danger bg-brand-danger/10 border border-brand-danger/20"
          >
            {{ errorMsg }}
          </div>

          <!-- Username -->
          <div>
            <label class="block text-sm font-medium text-[var(--color-text)] mb-1.5">用户名</label>
            <input
              v-model="username"
              type="text"
              class="input-field"
              placeholder="请输入用户名"
              autocomplete="username"
            />
          </div>

          <!-- Password -->
          <div>
            <label class="block text-sm font-medium text-[var(--color-text)] mb-1.5">密码</label>
            <div class="relative">
              <input
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                class="input-field pr-10"
                placeholder="请输入密码"
                autocomplete="current-password"
              />
              <button
                type="button"
                class="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                @click="showPassword = !showPassword"
              >
                <Eye v-if="!showPassword" class="w-4 h-4" />
                <EyeOff v-else class="w-4 h-4" />
              </button>
            </div>
          </div>

          <!-- Remember me -->
          <div class="flex items-center justify-between">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                v-model="rememberMe"
                type="checkbox"
                class="rounded border-[var(--color-border)] text-[var(--color-accent)] focus:ring-[var(--color-accent)]"
              />
              <span class="text-sm text-[var(--color-text-muted)]">记住我</span>
            </label>
            <a href="#" class="text-sm text-[var(--color-accent)] hover:underline">忘记密码？</a>
          </div>

          <!-- Submit -->
          <button
            type="submit"
            :disabled="loading"
            class="btn-primary w-full flex items-center justify-center gap-2"
          >
            <div v-if="loading" class="loading-spinner w-4 h-4 border-white border-t-transparent" />
            <span>{{ loading ? '登录中...' : '登录' }}</span>
          </button>
        </form>
      </div>

      <p class="mt-6 text-center text-xs text-[var(--color-text-muted)]">
        &copy; 2024 Super Market. All rights reserved.
      </p>
    </div>
  </div>
</template>
