<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/utils/api'
import Badge from '@/components/ui/Badge.vue'
import { useUserStore } from '@/stores/user'
import { Package } from 'lucide-vue-next'

const userStore = useUserStore()
const inventory = ref<any[]>([])
const summary = ref<any[]>([])
const products = ref<any[]>([])
const loading = ref(true)

const activeTab = ref<'list' | 'summary'>('list')

async function loadData() {
  loading.value = true
  try {
    const [invRes, sumRes, prodRes] = await Promise.all([
      api.get('/api/terminal/inventory?limit=200'),
      api.get('/api/terminal/inventory/summary'),
      api.get('/api/terminal/products'),
    ])
    inventory.value = invRes?.data?.items || invRes?.data || []
    summary.value = sumRes?.data || []
    products.value = prodRes?.data || []
  } catch (e) {
    console.error('Failed to load inventory:', e)
  }
  loading.value = false
}

async function removeItem(id: number) {
  if (!confirm('确认删除该库存项？')) return
  try {
    await api.delete(`/api/terminal/inventory/${id}`)
    await loadData()
  } catch (e) {
    console.error('Failed to delete:', e)
  }
}

function copyContent(text: string) {
  navigator.clipboard.writeText(text).catch(() => {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  })
}

onMounted(loadData)

function statusBadge(status: string): string {
  const map: Record<string, string> = {
    AVAILABLE: 'success', USED: 'info', EXPIRED: 'danger',
  }
  return map[status] || 'default'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    AVAILABLE: '可用', USED: '已消耗', EXPIRED: '已过期',
  }
  return map[status] || status
}

function productName(pid: number): string {
  const p = products.value.find((x: any) => x.id === pid || x.product_id === pid)
  return p?.name || `货品 #${pid}`
}

function formatTime(t: string | null): string {
  if (!t) return '—'
  return t.substring(0, 19).replace('T', ' ')
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-3">
      <Package class="w-6 h-6 text-[var(--color-accent)]" />
      <div>
        <h2 class="text-2xl font-bold text-[var(--color-text)]">库存管理</h2>
        <p class="text-sm text-[var(--color-text-muted)]">查看已采集并上传的库存资源</p>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 border-b border-[var(--color-border)]">
      <button v-for="t in [{k:'list',l:'库存列表'},{k:'summary',l:'库存概览'}]"
        :key="t.k" @click="activeTab = t.k"
        :class="['px-4 py-2.5 text-sm font-medium border-b-2 transition-colors',
          activeTab === t.k ? 'border-[var(--color-accent)] text-[var(--color-accent)]' : 'border-transparent text-[var(--color-text-muted)]']">
        {{ t.l }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-12 text-sm text-[var(--color-text-muted)]">加载中...</div>

    <!-- ── Inventory List ── -->
    <div v-else-if="activeTab === 'list'">
      <div v-if="inventory.length === 0" class="text-center py-12">
        <p class="text-sm text-[var(--color-text-muted)]">暂无库存数据</p>
        <p class="text-xs text-[var(--color-text-muted)] mt-1">通过工具端采集凭证后会自动上传到这里</p>
      </div>
      <div v-else class="grid gap-3">
        <div v-for="item in inventory" :key="item.id"
          class="card p-4 flex items-start gap-4">
          <!-- QR preview -->
          <div v-if="item.content?.startsWith('data:image')" class="shrink-0">
            <img :src="item.content" class="w-16 h-16 rounded border border-[var(--color-border)] object-cover" alt="凭证" />
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <span class="font-medium text-sm">{{ productName(item.product_id) }}</span>
              <Badge :type="statusBadge(item.status)">{{ statusLabel(item.status) }}</Badge>
            </div>
            <div class="text-xs text-[var(--color-text-muted)] truncate font-mono">{{ item.content?.substring(0, 80) }}{{ item.content?.length > 80 ? '...' : '' }}</div>
            <div class="text-xs text-[var(--color-text-muted)] mt-1">
              上传于 {{ formatTime(item.created_at) }}
            </div>
          </div>
          <div class="flex gap-2 shrink-0">
            <button class="btn btn-sm btn-outline" @click="copyContent(item.content)" title="复制">📋</button>
            <button v-if="item.status === 'AVAILABLE'" class="btn btn-sm btn-danger" @click="removeItem(item.id)" title="删除">🗑</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Inventory Summary ── -->
    <div v-else-if="activeTab === 'summary'">
      <div v-if="summary.length === 0" class="text-center py-12 text-sm text-[var(--color-text-muted)]">暂无概览数据</div>
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="s in summary" :key="s.product_id"
          class="card p-4">
          <div class="text-xs text-[var(--color-text-muted)] mb-1">{{ productName(s.product_id) }}</div>
          <div class="text-2xl font-bold">{{ s.total || 0 }}</div>
          <div class="text-xs text-[var(--color-text-muted)] mt-1">可用: {{ s.available || 0 }} | 已用: {{ s.used || 0 }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
