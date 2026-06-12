<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/utils/api'

const logs = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const actionFilter = ref('')
const loading = ref(true)
const limit = 20

async function load() {
  loading.value = true
  try {
    let path = `/api/admin/audit-logs?page=${page.value}&limit=${limit}`
    if (actionFilter.value) path += `&action=${actionFilter.value}`
    const r = await api.get(path)
    logs.value = r.data?.items || []
    total.value = r.data?.total || 0
  } catch (e) { console.error(e) }
  loading.value = false
}

const filters = [
  { value: '', label: '全部' },
  { value: 'login', label: '登录' },
  { value: 'error', label: '失败' },
  { value: 'force_complete', label: '强制完成' },
]

function setFilter(v: string) { actionFilter.value = v; page.value = 1; load() }

onMounted(load)
</script>

<template>
  <div class="p-6">
    <h2 class="text-xl font-bold text-[var(--color-text)] mb-4">审计日志</h2>
    <div class="flex gap-2 mb-4">
      <button v-for="f in filters" :key="f.value"
        class="px-3 py-1.5 text-xs font-medium rounded transition-colors"
        :class="actionFilter === f.value ? 'bg-[var(--color-primary)] text-white' : 'bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]'"
        @click="setFilter(f.value)">{{ f.label }}</button>
    </div>
    <div v-if="loading" class="text-center py-12 text-[var(--color-text-muted)]">加载中...</div>
    <div v-else-if="logs.length === 0" class="text-center py-12 text-[var(--color-text-muted)]">暂无日志</div>
    <div v-else class="overflow-x-auto">
      <table class="w-full text-xs">
        <thead><tr class="border-b border-[var(--color-border)]">
          <th class="text-left p-2 text-[var(--color-text-muted)]">时间</th>
          <th class="text-left p-2 text-[var(--color-text-muted)]">用户</th>
          <th class="text-left p-2 text-[var(--color-text-muted)]">IP</th>
          <th class="text-left p-2 text-[var(--color-text-muted)]">状态</th>
          <th class="text-left p-2 text-[var(--color-text-muted)]">备注</th>
        </tr></thead>
        <tbody>
          <tr v-for="l in logs" :key="l.id" class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
            <td class="p-2 text-[var(--color-text-muted)] font-mono">{{ l.created_at?.slice(0, 19) || '-' }}</td>
            <td class="p-2">{{ l.username || '-' }}</td>
            <td class="p-2 font-mono text-[var(--color-text-muted)]">{{ l.ip_address || '-' }}</td>
            <td class="p-2"><span :class="l.success ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'">{{ l.success ? '✓' : '✗' }}</span></td>
            <td class="p-2 text-[var(--color-text-muted)] max-w-xs truncate">{{ l.fail_reason || '-' }}</td>
          </tr>
        </tbody>
      </table>
      <div class="flex items-center justify-between mt-4">
        <span class="text-xs text-[var(--color-text-muted)]">共 {{ total }} 条</span>
        <div class="flex gap-2">
          <button class="px-3 py-1 text-xs rounded bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] disabled:opacity-30" :disabled="page <= 1" @click="page--; load()">上一页</button>
          <span class="px-3 py-1 text-xs text-[var(--color-text-muted)]">{{ page }}</span>
          <button class="px-3 py-1 text-xs rounded bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] disabled:opacity-30" :disabled="page * limit >= total" @click="page++; load()">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>
