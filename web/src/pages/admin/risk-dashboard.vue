<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/utils/api'
import { TrendingUp, AlertTriangle, Activity } from 'lucide-vue-next'

const today = ref({ total_orders: 0, total_amount: 0, success_orders: 0, pending_orders: 0, failed_orders: 0, success_rate: 0 })
const trend = ref<any[]>([])
const topSuppliers = ref<any[]>([])
const abnormalOrders = ref<any[]>([])
const health = ref({ orders: { total: 0, today: 0, last_10min: 0 }, callback_queue: { pending: 0, failed: 0 } })
const loading = ref(true)
let timer: ReturnType<typeof setInterval> | null = null

async function load() {
  try {
    const [dash, abnormal, h] = await Promise.all([
      api.get('/api/admin/risk/dashboard?days=7'),
      api.get('/api/admin/risk/abnormal-orders?limit=10'),
      api.get('/api/admin/risk/health'),
    ])
    if (dash.data) {
      today.value = dash.data.today
      trend.value = dash.data.trend || []
      topSuppliers.value = dash.data.top_suppliers || []
    }
    abnormalOrders.value = abnormal.data?.items || []
    health.value = h.data || health.value
  } catch (e) { console.error('Risk load failed', e) }
  loading.value = false
}

onMounted(() => { load(); timer = setInterval(load, 15000) })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="p-6 space-y-6">
    <h2 class="text-xl font-bold text-[var(--color-text)]">风控大盘</h2>

    <div v-if="loading" class="text-center py-12 text-[var(--color-text-muted)]">加载中...</div>

    <template v-else>
      <!-- Today Summary -->
      <div class="grid grid-cols-2 lg:grid-cols-6 gap-3">
        <div class="card"><div class="label">今日订单</div><div class="value blue">{{ today.total_orders }}</div></div>
        <div class="card"><div class="label">交易额</div><div class="value green">{{ today.total_amount }}</div></div>
        <div class="card"><div class="label">成功率</div><div class="value" :class="today.success_rate >= 90 ? 'green' : today.success_rate >= 50 ? 'orange' : 'red'">{{ today.success_rate }}%</div></div>
        <div class="card"><div class="label">待处理</div><div class="value orange">{{ today.pending_orders }}</div></div>
        <div class="card"><div class="label">失败</div><div class="value red">{{ today.failed_orders }}</div></div>
        <div class="card"><div class="label">系统健康</div><div class="value green">{{ health.status || 'healthy' }}</div></div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Trend -->
        <div class="card p-4">
          <h3 class="text-sm font-semibold mb-3 flex items-center gap-2"><TrendingUp class="w-4 h-4" /> 近7日趋势</h3>
          <div v-if="trend.length === 0" class="text-xs text-[var(--color-text-muted)] text-center py-4">暂无数据</div>
          <div v-for="t in trend" :key="t.date" class="flex items-center gap-2 py-1.5 text-xs border-b border-[var(--color-border)] last:border-0">
            <span class="w-24 text-[var(--color-text-muted)]">{{ t.date }}</span>
            <div class="flex-1 h-4 bg-[var(--color-bg)] rounded-full overflow-hidden">
              <div class="h-full bg-[var(--color-primary)] rounded-full transition-all" :style="{ width: Math.min(100, (t.success / Math.max(t.orders,1)) * 100) + '%' }"></div>
            </div>
            <span class="w-16 text-right">{{ t.orders }}单</span>
            <span class="w-20 text-right text-[var(--color-text-muted)]">{{ t.amount }}分</span>
          </div>
        </div>

        <!-- Top Suppliers -->
        <div class="card p-4">
          <h3 class="text-sm font-semibold mb-3 flex items-center gap-2"><Activity class="w-4 h-4" /> Top 供应商</h3>
          <div v-if="topSuppliers.length === 0" class="text-xs text-[var(--color-text-muted)] text-center py-4">暂无数据</div>
          <div v-for="(s, i) in topSuppliers" :key="s.id" class="flex items-center gap-2 py-1.5 text-xs border-b border-[var(--color-border)] last:border-0">
            <span class="w-5 text-[var(--color-text-muted)]">{{ i + 1 }}</span>
            <span class="flex-1 truncate">{{ s.name }}</span>
            <span class="w-16 text-right">{{ s.orders }}单</span>
            <span class="w-20 text-right text-[var(--color-text-muted)]">{{ s.amount }}分</span>
          </div>
        </div>
      </div>

      <!-- Abnormal Orders -->
      <div class="card p-4">
        <h3 class="text-sm font-semibold mb-3 flex items-center gap-2"><AlertTriangle class="w-4 h-4" /> 异常订单</h3>
        <div v-if="abnormalOrders.length === 0" class="text-xs text-[var(--color-text-muted)] text-center py-4">暂无异</div>
        <table v-else class="w-full text-xs">
          <thead><tr class="border-b border-[var(--color-border)]">
            <th class="text-left p-2 text-[var(--color-text-muted)]">订单号</th>
            <th class="text-left p-2 text-[var(--color-text-muted)]">供应商</th>
            <th class="text-left p-2 text-[var(--color-text-muted)]">状态</th>
            <th class="text-right p-2 text-[var(--color-text-muted)]">金额</th>
            <th class="text-right p-2 text-[var(--color-text-muted)]">超时</th>
          </tr></thead>
          <tbody>
            <tr v-for="o in abnormalOrders" :key="o.order_no" class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
              <td class="p-2 font-mono">{{ o.order_no }}</td>
              <td class="p-2">{{ o.supplier_name }}</td>
              <td class="p-2"><span :class="o.status === 'SUCCESS' ? 'text-[var(--color-success)]' : o.status === 'PENDING' ? 'text-[var(--color-warning)]' : 'text-[var(--color-danger)]'">{{ o.status }}</span></td>
              <td class="p-2 text-right">{{ o.amount }}</td>
              <td class="p-2 text-right"><span v-if="o.is_timeout" class="text-[var(--color-danger)]">⚠ 超时</span><span v-else class="text-[var(--color-text-muted)]">-</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- System Health -->
      <div class="grid grid-cols-3 gap-3">
        <div class="card"><div class="label">累计订单</div><div class="value blue">{{ health.orders?.total || 0 }}</div></div>
        <div class="card"><div class="label">回调待处理</div><div class="value orange">{{ health.callback_queue?.pending || 0 }}</div></div>
        <div class="card"><div class="label">回调失败</div><div class="value red">{{ health.callback_queue?.failed || 0 }}</div></div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.card { background: var(--color-card); border: 1px solid var(--color-border); border-radius: 8px; padding: 14px; }
.card .label { font-size: 10px; color: var(--color-text-muted); text-transform: uppercase; margin-bottom: 4px; }
.card .value { font-size: 16px; font-weight: 700; }
.green { color: var(--color-success); } .blue { color: var(--color-accent); }
.orange { color: #d29922; } .red { color: #f85149; }
</style>
