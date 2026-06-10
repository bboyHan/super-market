<script setup lang="ts">
import StatCard from '@/components/ui/StatCard.vue'
import DataTable from '@/components/ui/DataTable.vue'
import Badge from '@/components/ui/Badge.vue'
import { ref, onMounted } from 'vue'
import api from '@/utils/api'

interface DashboardData {
  today_amount: number
  yesterday_amount: number
  agent_count: number
  apayer_count: number
}

interface OrderItem {
  order_no: string
  amount: number
  status: string
  confirm_mode: string
  created_at: string
  api_payer_name: string
  product_name: string
}

interface ProductItem {
  id: number
  name: string
  category: string
  face_value: number
  suggested_price: number
}

const stats = ref({ today_amount: 0, yesterday_amount: 0, agent_count: 0, apayer_count: 0 })
const recentOrders = ref<OrderItem[]>([])
const products = ref<ProductItem[]>([])
const loading = ref(true)

const orderColumns = [
  { key: 'order_no', label: '订单号' },
  { key: 'api_payer_name', label: 'API支付商' },
  { key: 'product_name', label: '货品' },
  { key: 'amount', label: '金额(积分)', align: 'right' as const },
  { key: 'status', label: '状态' },
  { key: 'created_at', label: '时间' },
]

function formatTime(iso: string) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const statusMap: Record<string, string> = {
  SUBMITTED: '待提交',
  PENDING: '待确认',
  DELIVERING: '交付中',
  SUCCESS: '已完成',
  CANCELLED: '已取消',
  EXPIRED: '已超时',
  FAILED: '失败',
}

const statusTypeMap: Record<string, string> = {
  SUBMITTED: 'info',
  PENDING: 'warning',
  DELIVERING: 'warning',
  SUCCESS: 'success',
  CANCELLED: 'danger',
  EXPIRED: 'danger',
  FAILED: 'danger',
}

onMounted(async () => {
  try {
    const [dashRes, prodRes, orderRes] = await Promise.all([
      api.get<{code: number; data: DashboardData}>('/api/merchant/dashboard'),
      api.get<{code: number; data: ProductItem[]}>('/api/merchant/products'),
      api.get<{code: number; data: {items: OrderItem[]}}>('/api/merchant/orders?limit=5'),
    ])
    stats.value = dashRes.data
    products.value = prodRes.data
    recentOrders.value = orderRes.data.items
  } catch (e) {
    console.error('Failed to load dashboard data', e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-2xl font-bold text-[var(--color-text)]">供应商仪表盘</h2>
      <p class="mt-1 text-sm text-[var(--color-text-muted)]">今日概览与交易数据</p>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard title="今日交易额" :value="stats.today_amount + ' 积分'" unit="积分" />
      <StatCard title="昨日交易额" :value="stats.yesterday_amount + ' 积分'" unit="积分" />
      <StatCard title="代理商总数" :value="stats.agent_count" unit="个" />
      <StatCard title="API支付商" :value="stats.apayer_count" unit="个" />
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div class="lg:col-span-2 card p-4">
        <h3 class="text-sm font-semibold text-[var(--color-text)] mb-3">最近订单</h3>
        <div v-if="loading" class="text-sm text-[var(--color-text-muted)] py-4">加载中...</div>
        <DataTable v-else :columns="orderColumns" :data="recentOrders">
          <template #cell-status="{ row }">
            <Badge :status="statusTypeMap[row.status] || 'info'">
              {{ statusMap[row.status] || row.status }}
            </Badge>
          </template>
          <template #cell-created_at="{ row }">
            <span class="text-xs">{{ formatTime(row.created_at) }}</span>
          </template>
        </DataTable>
        <p v-if="!loading && recentOrders.length === 0" class="text-sm text-[var(--color-text-muted)] py-4">暂无订单数据</p>
      </div>

      <div class="card p-4">
        <h3 class="text-sm font-semibold text-[var(--color-text)] mb-3">已授权货品</h3>
        <div v-if="loading" class="text-sm text-[var(--color-text-muted)] py-2">加载中...</div>
        <div v-else class="space-y-2">
          <div v-for="p in products" :key="p.id"
               class="flex justify-between items-center p-2 rounded-lg hover:bg-[var(--color-border)]/20 transition-colors">
            <div>
              <div class="text-sm font-medium text-[var(--color-text)]">{{ p.name }}</div>
              <div class="text-xs text-[var(--color-text-muted)]">{{ p.category }}</div>
            </div>
            <div class="text-right">
              <div class="text-sm font-semibold text-[var(--color-accent)]">{{ p.face_value }} 积分</div>
              <div class="text-xs text-[var(--color-text-muted)]">建议售价: {{ p.suggested_price }}</div>
            </div>
          </div>
          <p v-if="products.length === 0" class="text-sm text-[var(--color-text-muted)] py-2">暂无授权货品</p>
        </div>
      </div>
    </div>
  </div>
</template>
