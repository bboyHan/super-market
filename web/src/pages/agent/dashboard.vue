<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/utils/api'
import StatCard from '@/components/ui/StatCard.vue'
import DataTable from '@/components/ui/DataTable.vue'
import Badge from '@/components/ui/Badge.vue'
import type { Order } from '@/types'

const loading = ref(true)

// Dashboard data
const stats = ref({
  todayDeliveries: 0,
  pendingDeliveries: 0,
  totalInventory: 0,
  balance: 0,
})

const deliveries = ref<any[]>([])
const inventorySummary = ref<any[]>([])

const statusLabels: Record<string, string> = {
  SUBMITTED: '待提交', PENDING: '待确认', DELIVERING: '交付中',
  SUCCESS: '已完成', CANCELLED: '已取消', EXPIRED: '已超时', FAILED: '失败',
}
const statusColors: Record<string, string> = {
  SUBMITTED: 'info', PENDING: 'pending', DELIVERING: 'processing',
  SUCCESS: 'success', CANCELLED: 'cancelled', EXPIRED: 'failed', FAILED: 'failed',
}

async function loadDashboard() {
  loading.value = true
  try {
    const results = await Promise.allSettled([
      // All orders for stats and recent list
      api.get<{code: number; data: {items: any[]; total: number}}>('/api/merchant/agent/orders?limit=20'),
      // Pending deliveries count
      api.get<{code: number; data: {items: any[]; total: number}}>('/api/merchant/agent/orders?status=DELIVERING&limit=1'),
      // Inventory summary
      api.get<{code: number; data: any[]}>('/api/merchant/agent/inventory'),
      // Wallet info
      api.get<{code: number; data: {balance: number}}>('/api/merchant/agent/wallet'),
    ])

    // Process orders
    if (results[0].status === 'fulfilled') {
      const items = results[0].value.data.items || []
      deliveries.value = items

      // Count today's deliveries
      const today = new Date().toISOString().slice(0, 10)
      stats.value.todayDeliveries = items.filter(
        (o: any) => o.status === 'SUCCESS' && o.created_at?.startsWith(today)
      ).length
    }

    // Process pending deliveries
    if (results[1].status === 'fulfilled') {
      stats.value.pendingDeliveries = results[1].value.data.items?.length || 0
    }

    // Process inventory
    if (results[2].status === 'fulfilled') {
      const invData = results[2].value.data || []
      inventorySummary.value = invData
      stats.value.totalInventory = invData.reduce((sum: number, item: any) => sum + (item.available || 0), 0)
    }

    // Process wallet
    if (results[3].status === 'fulfilled') {
      stats.value.balance = results[3].value.data?.balance || 0
    }
  } catch {
    // Keep defaults (zeros)
  } finally {
    loading.value = false
  }
}

const columns = [
  { key: 'order_no', label: '交付编号', sortable: true },
  { key: 'api_payer_name', label: 'API支付商' },
  { key: 'product_name', label: '货品' },
  { key: 'amount', label: '金额', align: 'right' as const },
  { key: 'status', label: '状态' },
  { key: 'created_at', label: '时间' },
]

onMounted(loadDashboard)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <h2 class="text-2xl font-bold text-[var(--color-text)]">代理商仪表盘</h2>
      <p class="mt-1 text-sm text-[var(--color-text-muted)]">查看您的业绩和交付情况</p>
    </div>

    <!-- Stats cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard
        title="今日交付"
        :value="loading ? '' : `${stats.todayDeliveries} 单`"
        :loading="loading"
      />
      <StatCard
        title="待交付"
        :value="loading ? '' : `${stats.pendingDeliveries} 单`"
        :loading="loading"
      />
      <StatCard
        title="库存可用"
        :value="loading ? '' : `${stats.totalInventory}`"
        :loading="loading"
      />
      <StatCard
        title="积分余额"
        :value="loading ? '' : `${stats.balance}`"
        :loading="loading"
      />
    </div>

    <!-- Recent deliveries table -->
    <div>
      <h3 class="text-lg font-semibold text-[var(--color-text)] mb-3">最近交付</h3>
      <DataTable :columns="columns" :data="deliveries" :loading="loading" empty-text="暂无交付订单">
        <template #cell-status="{ value }">
          <Badge :status="statusColors[value] || 'info'">{{ statusLabels[value] || value }}</Badge>
        </template>
        <template #cell-amount="{ value }">
          <span class="font-medium font-mono">{{ value?.toLocaleString() || '-' }}</span>
        </template>
        <template #cell-order_no="{ value }">
          <span class="font-mono text-xs text-[var(--color-text-muted)]">{{ value?.slice(-16) || '-' }}</span>
        </template>
        <template #cell-created_at="{ value }">
          <span class="text-xs text-[var(--color-text-muted)]">{{ value?.slice(5, 19) || '-' }}</span>
        </template>
      </DataTable>
    </div>

    <!-- Inventory overview -->
    <div>
      <h3 class="text-lg font-semibold text-[var(--color-text)] mb-3">库存概览</h3>
      <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div v-for="i in 3" :key="i" class="card p-4 animate-pulse">
          <div class="h-4 w-24 bg-[var(--color-border)] rounded" />
          <div class="mt-3 h-10 bg-[var(--color-border)] rounded" />
        </div>
      </div>
      <div v-else-if="inventorySummary.length" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div v-for="s in inventorySummary" :key="s.product_id || s.product_name" class="card p-4">
          <div class="text-sm font-medium text-[var(--color-text)]">{{ s.product_name || s.product_id }}</div>
          <div class="mt-3 grid grid-cols-3 gap-2 text-center">
            <div>
              <div class="text-lg font-bold text-[var(--color-text)]">{{ s.total || s.available + (s.used || 0) }}</div>
              <div class="text-xs text-[var(--color-text-muted)]">总数</div>
            </div>
            <div>
              <div class="text-lg font-bold text-[var(--color-success)]">{{ s.available || 0 }}</div>
              <div class="text-xs text-[var(--color-text-muted)]">可用</div>
            </div>
            <div>
              <div class="text-lg font-bold text-[var(--color-text-muted)]">{{ s.used || 0 }}</div>
              <div class="text-xs text-[var(--color-text-muted)]">已用</div>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="card p-6 text-center text-sm text-[var(--color-text-muted)]">
        暂无库存数据
      </div>
    </div>
  </div>
</template>
