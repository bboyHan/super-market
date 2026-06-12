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

const activeTab = ref<'list' | 'summary' | 'alerts'>('list')
const alertsConfig = ref<any[]>([])
const alertThresholds = ref<Record<number, number>>({})
const alertEnabled = ref<Record<number, boolean>>({})
const savingAlert = ref(false)

async function loadAlerts() {
  try {
    const r = await api.get('/api/terminal/inventory/alerts')
    alertsConfig.value = r?.data || []
    for (const a of (r?.data || [])) {
      alertThresholds.value[a.product_id] = a.threshold
      alertEnabled.value[a.product_id] = a.enabled
    }
    // Fill in products that don't have alerts
    for (const p of (products.value || [])) {
      if (!(p.id in alertThresholds.value)) {
        alertThresholds.value[p.id] = 10
        alertEnabled.value[p.id] = true
      }
    }
  } catch (e) { console.error('Failed to load alerts:', e) }
}

async function saveAlert(productId: number) {
  savingAlert.value = true
  try {
    await api.put('/api/terminal/inventory/alerts/' + productId, {
      product_id: productId,
      threshold: alertThresholds.value[productId] || 10,
      enabled: alertEnabled.value[productId] ?? true,
    })
  } catch (e) { console.error('Save alert failed:', e) }
  savingAlert.value = false
}

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

onMounted(() => { loadData(); loadAlerts(); })

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
  <!-- ════════════ Alerts Tab ════════════ -->
  <div v-else-if="activeTab === 'alerts'" class="space-y-3">
    <div class="flex items-center justify-between mb-2">
      <h3 class="text-sm font-semibold text-[var(--color-text)]">库存预警设置</h3>
      <span class="text-xs text-[var(--color-text-muted)]">低于阈值时提醒补货</span>
    </div>
    <div v-for="p in (products || [])" :key="p.id" class="flex items-center gap-3 p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
      <div class="flex-1 min-w-0">
        <div class="text-sm font-medium text-[var(--color-text)] truncate">{{ p.name }}</div>
        <div class="text-xs text-[var(--color-text-muted)]">建议售价: {{ p.settlement_price || p.suggested_price }} 积分</div>
      </div>
      <div class="flex items-center gap-2">
        <label class="text-xs text-[var(--color-text-muted)]">低于</label>
        <input type="number" v-model.number="alertThresholds[p.id]" min="1" max="9999"
          class="w-16 px-2 py-1 text-xs text-center bg-[var(--color-bg-elevated)] border border-[var(--color-border)] rounded text-[var(--color-text)]"
          @change="saveAlert(p.id)"
        />
        <label class="text-xs text-[var(--color-text-muted)]">条时提醒</label>
      </div>
      <label class="relative inline-flex items-center cursor-pointer">
        <input type="checkbox" v-model="alertEnabled[p.id]" class="sr-only peer" @change="saveAlert(p.id)" />
        <div class="w-8 h-4 bg-[var(--color-bg-elevated)] rounded-full peer peer-checked:bg-[var(--color-primary)] after:content-[''] after:absolute after:top-0.5 after:start-0.5 after:bg-white after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:after:translate-x-4"></div>
      </label>
    </div>
    <div v-if="!(products || []).length" class="text-sm text-[var(--color-text-muted)] text-center py-8">暂无授权货品</div>
  </div>

</template>
