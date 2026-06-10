import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserInfo } from '@/types'
import api from '@/utils/api'

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(localStorage.getItem('auth-token'))
  const user = ref<UserInfo | null>(null)

  const isAuthenticated = computed(() => !!token.value)
  const role = computed<string | null>(() => user.value?.role ?? null)
  const isSupplier = computed(() => role.value === 'SUPPLIER' || role.value === 'ADMIN')
  const isAdmin = computed(() => role.value === 'ADMIN')

  function setToken(newToken: string) {
    token.value = newToken
    localStorage.setItem('auth-token', newToken)
  }

  function setUser(userInfo: UserInfo) {
    user.value = userInfo
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('auth-token')
  }

  async function fetchUserInfo() {
    if (!token.value) return
    try {
      const res = await api.get<{code: number; data: UserInfo}>('/api/auth/profile')
      if (res.code === 0) {
        setUser(res.data)
      }
    } catch {
      logout()
    }
  }

  return { token, user, isAuthenticated, role, isSupplier, isAdmin, setToken, setUser, logout, fetchUserInfo }
})
