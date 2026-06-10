import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { ThemeMode } from '@/types'

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>('dark')

  function init() {
    const saved = localStorage.getItem('theme-mode') as ThemeMode | null
    if (saved === 'light' || saved === 'dark') {
      mode.value = saved
    } else {
      mode.value = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    }
    applyTheme()
  }

  function applyTheme() {
    if (mode.value === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    localStorage.setItem('theme-mode', mode.value)
  }

  function toggle() {
    mode.value = mode.value === 'dark' ? 'light' : 'dark'
  }

  function setTheme(newMode: ThemeMode) {
    mode.value = newMode
  }

  // Sync theme changes
  watch(mode, () => {
    applyTheme()
  })

  return { mode, init, toggle, setTheme }
})
