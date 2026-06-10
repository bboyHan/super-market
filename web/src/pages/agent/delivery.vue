<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '@/utils/api'
import Badge from '@/components/ui/Badge.vue'
import { Package, RefreshCw, Send } from 'lucide-vue-next'

const orders = ref<any[]>([])
const loading = ref(true)
const activeTab = ref('all')
const delivering = ref<Record<string, boolean>>({})
const toast = ref('')

const statusLabels: Record<string, string> = {
  SUBMITTED: '待提交', PENDING: '待确认', DELIVERING: '交付中',
  SUCCESS: '已完成', CANCELLED: '已取消', EXPIRED: '已超时', FAILED: '失败',
}
const statusColors: Record<string, string> = {
  SUBMITTED: 'info', PENDING: 'pending', DELIVERING: 'processing',
  SUCCESS: 'success', CANCELLED: 'cancelled', EXPIRED: 'failed', FAILED: 'failed',
}

async function loadOrders() {
  loading.value = true
  try {
    const r = await api.get<{code: number; data: {items: any[]}}>(
      `/api/merchant/agent/orders?limit=50`)
    orders.value = r.data.items
  } catch { /* ignore */ }
  finally { loading.value = false }
}

async function deliverOrder(orderNo: string) {
  delivering.value[orderNo] = true
  try {
    const r = await api.post(`/api/merchant/orders/${orderNo}/deliver?delivery_content=DELIVER_${Date.now()}`, {})
    toast.value = r.message || '交付成功'
    await loadOrders()
  } catch (e: any) {
    toast.value = `交付失败: ${e.message || e}`
  } finally {
    delivering.value[orderNo] = false
    setTimeout(() => toast.value = '', 5000)
  }
}

const filteredOrders = computed(() => {
  if (activeTab === 'all') return orders.value
  return orders.value.filter(o => o.status === activeTab)
})

onMounted(loadOrders)
</script>

<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <div class="flex items-center gap-3">
        <Package class="w-6 h-6 text-[var(--color-accent)]" />
        <div>
          <h2 class="text-2xl font-bold text-[var(--color-text)]">交付管理</h2>
          <p class="text-sm text-[var(--color-text-muted)]">确认订单交付，将货品内容发送给API支付商</p>
        </div>
      </div>
      <button class="btn btn-outline btn-sm" @click="loadOrders"><RefreshCw class="w-3 h-3" /> 刷新</button>
    </div>

    <!-- Status tabs -->
    <div class="flex gap-1 bg-[var(--color-bg)] rounded-lg p-1 border border-[var(--color-border)] inline-flex">
      <button v-for="t in [{k:'all',l:'全部'},{k:'PENDING',l:'待确认'},{k:'DELIVERING',l:'待交付'},{k:'SUCCESS',l:'已完成'}]"
        :key="t.k"
        @click="activeTab = t.k"
        :class="['px-3 py-1.5 text-xs rounded-md font-medium transition-colors',
          activeTab === t.k ? 'bg-[var(--color-accent)] text-white' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]']">
        {{ t.l }}
      </button>
    </div>

    <div class="card p-0 overflow-hidden">
      <div v-if="loading" class="p-6 text-sm text-[var(--color-text-muted)]">加载中...</div>
      <table v-else class="w-full text-sm">
        <thead><tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">订单号</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">API支付商</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">货品</th>
          <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">金额</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">状态</th>
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
          <td class="p-3"><Badge :status="statusColors[o.status] || 'info'">{{ statusLabels[o.status] || o.status }}</Badge></td>
          <td class="p-3 text-xs text-[var(--color-text-muted)]">{{ o.created_at?.slice(5, 19) }}</td>
          <td class="p-3 text-right">
            <button v-if="o.status === 'DELIVERING'"
              class="btn btn-primary btn-sm" :disabled="delivering[o.order_no]" @click="deliverOrder(o.order_no)">
              <Send class="w-3 h-3" /> {{ delivering[o.order_no] ? '交付中...' : '确认交付' }}
            </button>
            <span v-else-if="o.status === 'SUCCESS'" class="text-xs text-[var(--color-success)]">已完成</span>
            <span v-else class="text-xs text-[var(--color-text-muted)]">等待确认</span>
          </td>
        </tr>
        </tbody>
      </table>
      <div v-if="!loading && !filteredOrders.length" class="p-6 text-center text-sm text-[var(--color-text-muted)]">暂无订单</div>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="fixed bottom-6 right-6 card p-3 max-w-sm z-50 shadow-xl"
         :class="toast.includes('失败') ? 'border-red-500/50' : 'border-[var(--color-success)]/50'">
      <p class="text-sm">{{ toast }}</p>
    </div>
  </div>
</template>
