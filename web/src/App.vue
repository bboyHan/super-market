<script setup lang="ts">
import { onMounted } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useUserStore } from '@/stores/user'
import AppLayout from '@/components/layout/AppLayout.vue'

const themeStore = useThemeStore()
const userStore = useUserStore()

onMounted(() => {
  themeStore.init()
  // Restore user session on page refresh
  if (userStore.token && !userStore.user) {
    userStore.fetchUserInfo()
  }
})
</script>

<template>
  <AppLayout>
    <router-view />
  </AppLayout>
</template>
