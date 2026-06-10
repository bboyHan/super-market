<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '@/utils/api'
import Badge from '@/components/ui/Badge.vue'
import { ShoppingCart, RefreshCw, Search, CheckCircle, Package } from 'lucide-vue-next'

const orders = ref<any[]>([])
const loading = ref(true)
const activeTab = ref('all')
const searchText = ref('')
const page = ref(1)
const limit = 20
const total = ref(0)

const statusLabels: Record<string, string> = {
  SUBMITTED: '待提交', PENDING: '待确认', DELIVERING: '交付中',
  SUCCESS: '已完成', CANCELLED: '已取消', EXPIRED: '已超时', FAILED: '失败',
}
const statusColors: Record<string, string> = {
  SUBMITTED: 'info', PENDING: 'pending', DELIVERING: 'processing',
  SUCCESS: 'success', CANCELLED: 'cancelled', EXPIRED: 'failed', FAILED: 'failed',
}

const filteredOrders = computed(() => {
  let list = orders.value
  if (activeTab !== 'all') {
    list = list.filter(o => o.status === activeTab)
  }
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(o => o.order_no?.toLowerCase().includes(q))
  }
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / limit)))

async function loadOrders() {
  loading.value = true
  try {
    const r = await api.get<{code: number; data: {items: any[]; total: number}}>(
      `/api/merchant/orders?page=${page.value}&limit=${limit}`)
    orders.value = r.data.items
    total.value = r.data.total || 0
  } catch { /* ignore */ }
  finally { loading.value = false }
}

async function confirmOrder(orderNo: string) {
  try {
    const r = await api.post(`/api/merchant/orders/${orderNo}/confirm`, {})
    // Refresh after confirm
    await loadOrders()
  } catch { /* ignore */ }
}

onMounted(loadOrders)
</script>

<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <div>
        <h2 class="text-2xl font-bold text-[var(--color-text)]">订单管理</h2>
        <p class="text-sm text-[var(--color-text-muted)]">查看和管理所有订单，确认收款并跟踪交付进度</p>
      </div>
      <button class="btn btn-outline btn-sm" @click="loadOrders"><RefreshCw class="w-3 h-3" /> 刷新</button>
    </div>

    <!-- Search + Status tabs -->
    <div class="flex flex-wrap items-center gap-3 justify-between">
      <div class="flex gap-1 bg-[var(--color-bg)] rounded-lg p-1 border border-[var(--color-border)]">
        <button v-for="t in [{k:'all',l:'全部'},{k:'PENDING',l:'待确认'},{k:'DELIVERING',l:'交付中'},{k:'SUCCESS',l:'已完成'}]"
          :key="t.k"
          @click="activeTab = t.k"
          :class="['px-3 py-1.5 text-xs rounded-md font-medium transition-colors',
            activeTab === t.k ? 'bg-[var(--color-accent)] text-white' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]']">
          {{ t.l }}
        </button>
      </div>
      <div class="relative w-full sm:w-64">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-muted)]" />
        <input v-model="searchText" placeholder="搜索订单号..."
          class="w-full pl-9 pr-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm text-[var(--color-text)]" />
      </div>
    </div>

    <!-- Orders table -->
    <div class="card p-0 overflow-hidden">
      <div v-if="loading" class="p-6 text-sm text-[var(--color-text-muted)]">加载中...</div>
      <table v-else class="w-full text-sm">
        <thead><tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">订单号</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">API支付商</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">货品</th>
          <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">金额</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">模式</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">状态</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">代理商</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">时间</th>
          <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">操作</th>
        </tr></thead>
        <tbody>
        <tr v-for="o in filteredOrders" :key="o.order_no"
          class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
          <td class="p-3 font-mono text-xs text-[var(--color-text-muted)]">{{ o.order_no?.slice(-16) }}</td>
          <td class="p-3">{{ o.api_payer_name || '-' }}</td>
          <td class="p-3">{{ o.product_name || '-' }}</td>
          <td class="p-3 text-right font-mono font-semibold">{{ o.amount?.toLocaleString() }}</td>
          <td class="p-3">
            <span class="text-xs px-1.5 py-0.5 rounded bg-[var(--color-bg)] text-[var(--color-text-muted)]">
              {{ o.confirm_mode === 'AUTO' ? '自动' : '手动' }}
            </span>
          </td>
          <td class="p-3"><Badge :status="statusColors[o.status] || 'info'">{{ statusLabels[o.status] || o.status }}</Badge></td>
          <td class="p-3 text-[var(--color-text-muted)]">{{ o.agent_name || '-' }}</td>
          <td class="p-3 text-xs text-[var(--color-text-muted)]">{{ o.created_at?.slice(5, 19) }}</td>
          <td class="p-3 text-right">
            <button v-if="o.status === 'PENDING'"
              class="btn btn-primary btn-sm" @click="confirmOrder(o.order_no)">
              <CheckCircle class="w-3 h-3" /> 确认收款
            </button>
            <span v-else class="text-xs text-[var(--color-text-muted)]">-</span>
          </td>
        </tr>
        </tbody>
      </table>
      <div v-if="!loading && !filteredOrders.length" class="p-6 text-center text-sm text-[var(--color-text-muted)]">
        {{ searchText ? '未找到匹配的订单' : '暂无订单' }}
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="total > limit" class="flex items-center justify-between text-sm text-[var(--color-text-muted)]">
      <span>共 {{ total }} 条记录，第 {{ page }} / {{ totalPages }} 页</span>
      <div class="flex gap-2">
        <button :disabled="page <= 1" class="btn btn-outline btn-sm" @click="page--; loadOrders()">上一页</button>
        <button :disabled="page >= totalPages" class="btn btn-outline btn-sm" @click="page++; loadOrders()">下一页</button>
      </div>
    </div>
  </div>
</template>
