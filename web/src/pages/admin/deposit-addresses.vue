<script setup lang="ts">
import { ref, onMounted } from 'vue'

// This page is deprecated — per-user deposit addresses are no longer used.
// Platform uses unified wallet addresses configured by the admin.
const loading = ref(true)
const message = '此页面已弃用，积分充值请使用侧边栏「积分充值」功能'

onMounted(() => { loading.value = false })
</script>

<template>
  <div class="card p-6 text-center">
    <h2 class="text-lg font-semibold text-[var(--color-text)] mb-2">页面已迁移</h2>
    <p class="text-sm text-[var(--color-text-muted)]">{{ message }}</p>
  </div>
</template>
