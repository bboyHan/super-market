<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '@/utils/api'
import { Wallet, TrendingUp, ArrowUpRight, ArrowDownRight, BarChart3, RefreshCw } from 'lucide-vue-next'

// ── Tab state ──
const activeTab = ref<'wallet' | 'reconciliation'>('wallet')
const reconSubTab = ref<'merchant' | 'category'>('merchant')

// ── Wallet data ──
const wallet = ref({ balance: 0, frozen: 0, total_recharge: 0, total_consumed: 0, total_transferred_out: 0, available: 0 })
const txns = ref<any[]>([])
const loading = ref(true)

const typeLabels: Record<string, string> = {
  RECHARGE: '充值', CONSUME: '消费', TRANSFER_OUT: '划出',
  TRANSFER_IN: '划入', FREEZE: '冻结', REFUND: '退款',
}
const typeColors: Record<string, string> = {
  RECHARGE: 'text-[var(--color-success)]',
  CONSUME: 'text-[var(--color-danger)]',
  TRANSFER_OUT: 'text-[var(--color-warning)]',
  TRANSFER_IN: 'text-[var(--color-success)]',
  FREEZE: 'text-[var(--color-text-muted)]',
}

// ── Reconciliation data ──
const selectedDate = ref(new Date().toISOString().slice(0, 10))
const merchantStats = ref<any[]>([])
const categoryStats = ref<any[]>([])
const reconLoading = ref(false)
const refreshing = ref(false)

// Helper: format date N days ago
function daysAgo(n: number): string {
  const d = new Date(selectedDate.value)
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

// ── Pivoted merchant rows: group by api_payer_id across 3 days ──
interface MerchantRow {
  api_payer_id: number
  merchant_name: string
  d0_orders: number; d0_amount: number
  d1_orders: number; d1_amount: number
  d2_orders: number; d2_amount: number
}

const merchantRows = computed<MerchantRow[]>(() => {
  const map = new Map<number, MerchantRow>()
  for (const s of merchantStats.value) {
    const id = s.api_payer_id
    if (!map.has(id)) {
      map.set(id, {
        api_payer_id: id,
        merchant_name: s.merchant_name,
        d0_orders: 0, d0_amount: 0,
        d1_orders: 0, d1_amount: 0,
        d2_orders: 0, d2_amount: 0,
      })
    }
    const row = map.get(id)!
    // Determine which day offset: check the stat_date from the API or use s.date if present
    // Since we fetched 3 dates sequentially, the data has no date marker. Let's use the approach
    // of storing fetched data with date tags. Actually, let's restructure this.
  }
  return Array.from(map.values())
})

// Better approach: store stats per date
const merchantStatsByDate = ref<Record<string, any[]>>({})
const categoryStatsByDate = ref<Record<string, any[]>>({})

const dateLabels = computed(() => [
  { key: 'd0', label: '今日', date: selectedDate.value },
  { key: 'd1', label: '昨日', date: daysAgo(1) },
  { key: 'd2', label: '前日', date: daysAgo(2) },
])

interface PivotMerchantRow {
  api_payer_id: number
  merchant_name: string
  d0_orders: number; d0_amount: number
  d1_orders: number; d1_amount: number
  d2_orders: number; d2_amount: number
  total_orders: number; total_amount: number
}

const pivotMerchantRows = computed<PivotMerchantRow[]>(() => {
  const map = new Map<number, PivotMerchantRow>()
  const dates = [selectedDate.value, daysAgo(1), daysAgo(2)]
  const keys = ['d0', 'd1', 'd2'] as const

  for (let i = 0; i < 3; i++) {
    const arr = merchantStatsByDate.value[dates[i]] || []
    for (const s of arr) {
      const id = s.api_payer_id
      if (!map.has(id)) {
        map.set(id, {
          api_payer_id: id,
          merchant_name: s.merchant_name,
          d0_orders: 0, d0_amount: 0,
          d1_orders: 0, d1_amount: 0,
          d2_orders: 0, d2_amount: 0,
          total_orders: 0, total_amount: 0,
        })
      }
      const row = map.get(id)!
      row[`${keys[i]}_orders`] = s.total_orders || 0
      row[`${keys[i]}_amount`] = s.total_amount || 0
    }
  }
  const result = Array.from(map.values())
  for (const r of result) {
    r.total_orders = r.d0_orders + r.d1_orders + r.d2_orders
    r.total_amount = r.d0_amount + r.d1_amount + r.d2_amount
  }
  return result
})

interface PivotCategoryRow {
  product_id: number
  product_name: string
  category: string
  d0_orders: number; d0_amount: number
  d1_orders: number; d1_amount: number
  d2_orders: number; d2_amount: number
  total_orders: number; total_amount: number
  ratio: string
}

const pivotCategoryRows = computed<PivotCategoryRow[]>(() => {
  const map = new Map<number, PivotCategoryRow>()
  const dates = [selectedDate.value, daysAgo(1), daysAgo(2)]
  const keys = ['d0', 'd1', 'd2'] as const
  let grandTotal = 0

  // First pass: aggregate
  for (let i = 0; i < 3; i++) {
    const arr = categoryStatsByDate.value[dates[i]] || []
    for (const s of arr) {
      const id = s.product_id
      if (!map.has(id)) {
        map.set(id, {
          product_id: id,
          product_name: s.product_name,
          category: s.category,
          d0_orders: 0, d0_amount: 0,
          d1_orders: 0, d1_amount: 0,
          d2_orders: 0, d2_amount: 0,
          total_orders: 0, total_amount: 0,
          ratio: '0%',
        })
      }
      const row = map.get(id)!
      row[`${keys[i]}_orders`] = s.total_orders || 0
      row[`${keys[i]}_amount`] = s.total_amount || 0
    }
  }
  const result = Array.from(map.values())
  for (const r of result) {
    r.total_orders = r.d0_orders + r.d1_orders + r.d2_orders
    r.total_amount = r.d0_amount + r.d1_amount + r.d2_amount
    grandTotal += r.total_amount
  }
  // Compute ratio
  for (const r of result) {
    r.ratio = grandTotal > 0 ? ((r.total_amount / grandTotal) * 100).toFixed(1) + '%' : '0%'
  }
  return result
})

// ── Load reconciliation data ──
async function loadReconciliation() {
  reconLoading.value = true
  try {
    const dates = [selectedDate.value, daysAgo(1), daysAgo(2)]
    const results = await Promise.all(
      dates.map(async (d) => {
        const [mRes, cRes] = await Promise.all([
          api.get<{code: number; data: any[]}>(`/api/merchant/daily-stats/merchant?date=${d}`),
          api.get<{code: number; data: any[]}>(`/api/merchant/daily-stats/category?date=${d}`),
        ])
        return { date: d, merchant: mRes.data || [], category: cRes.data || [] }
      })
    )
    merchantStatsByDate.value = {}
    categoryStatsByDate.value = {}
    for (const r of results) {
      merchantStatsByDate.value[r.date] = r.merchant
      categoryStatsByDate.value[r.date] = r.category
    }
  } finally {
    reconLoading.value = false
  }
}

async function refreshDailyStats() {
  refreshing.value = true
  try {
    await api.post('/api/merchant/daily-stats/refresh')
    await loadReconciliation()
  } finally {
    refreshing.value = false
  }
}

// ── Init ──
onMounted(async () => {
  try {
    const [wr, tr] = await Promise.all([
      api.get<{code: number; data: any}>('/api/merchant/wallet'),
      api.get<{code: number; data: {items: any[]}}>('/api/merchant/wallet/transactions?limit=50'),
    ])
    wallet.value = wr.data
    txns.value = tr.data.items
  } finally { loading.value = false }
  // Load reconciliation data in background
  await loadReconciliation()
})

function formatAmount(v: number): string {
  return (v || 0).toLocaleString()
}
</script>

<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-bold text-[var(--color-text)]">财务管理</h2>

    <!-- Tabs -->
    <div class="flex gap-1 border-b border-[var(--color-border)]">
      <button
        class="px-4 py-2 text-sm font-medium transition-colors rounded-t-lg"
        :class="activeTab === 'wallet'
          ? 'bg-[var(--color-bg-elevated)] text-[var(--color-primary)] border-b-2 border-[var(--color-primary)]'
          : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'"
        @click="activeTab = 'wallet'"
      >
        <Wallet class="w-4 h-4 inline mr-1" /> 钱包总览
      </button>
      <button
        class="px-4 py-2 text-sm font-medium transition-colors rounded-t-lg"
        :class="activeTab === 'reconciliation'
          ? 'bg-[var(--color-bg-elevated)] text-[var(--color-primary)] border-b-2 border-[var(--color-primary)]'
          : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'"
        @click="activeTab = 'reconciliation'"
      >
        <BarChart3 class="w-4 h-4 inline mr-1" /> 对账看板
      </button>
    </div>

    <!-- ════════════ Wallet Tab ════════════ -->
    <template v-if="activeTab === 'wallet'">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="card p-4">
          <div class="flex items-center gap-2 text-[var(--color-text-muted)] text-xs mb-2"><Wallet class="w-4 h-4" /> 可用余额</div>
          <div class="text-2xl font-bold text-[var(--color-text)]">{{ wallet.available?.toLocaleString() }}</div>
          <div class="text-xs text-[var(--color-text-muted)] mt-1">冻结: {{ wallet.frozen }}</div>
        </div>
        <div class="card p-4">
          <div class="flex items-center gap-2 text-[var(--color-text-muted)] text-xs mb-2"><TrendingUp class="w-4 h-4" /> 总充值</div>
          <div class="text-2xl font-bold text-[var(--color-success)]">{{ wallet.total_recharge?.toLocaleString() }}</div>
        </div>
        <div class="card p-4">
          <div class="flex items-center gap-2 text-[var(--color-text-muted)] text-xs mb-2"><ArrowUpRight class="w-4 h-4" /> 累计消费</div>
          <div class="text-2xl font-bold text-[var(--color-danger)]">{{ wallet.total_consumed?.toLocaleString() }}</div>
        </div>
        <div class="card p-4">
          <div class="flex items-center gap-2 text-[var(--color-text-muted)] text-xs mb-2"><ArrowDownRight class="w-4 h-4" /> 累计划出</div>
          <div class="text-2xl font-bold text-[var(--color-warning)]">{{ wallet.total_transferred_out?.toLocaleString() }}</div>
        </div>
      </div>

      <div class="card p-4">
        <h3 class="text-sm font-semibold text-[var(--color-text)] mb-3">交易流水</h3>
        <div v-if="loading" class="text-sm text-[var(--color-text-muted)]">加载中...</div>
        <table v-else class="w-full text-xs">
          <thead><tr class="border-b border-[var(--color-border)]">
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">类型</th>
            <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">金额</th>
            <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">变动前</th>
            <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">变动后</th>
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">备注</th>
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">时间</th>
          </tr></thead>
          <tbody>
          <tr v-for="t in txns" :key="t.id" class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
            <td class="p-2"><span :class="typeColors[t.type] || ''">{{ typeLabels[t.type] || t.type }}</span></td>
            <td class="p-2 text-right font-mono font-semibold"
              :class="['RECHARGE','TRANSFER_IN'].includes(t.type) ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'">
              {{ ['RECHARGE','TRANSFER_IN'].includes(t.type) ? '+' : '-' }}{{ Math.abs(t.amount) }}
            </td>
            <td class="p-2 text-right font-mono text-[var(--color-text-muted)]">{{ t.balance_before }}</td>
            <td class="p-2 text-right font-mono">{{ t.balance_after }}</td>
            <td class="p-2 text-[var(--color-text-muted)] max-w-[200px] truncate">{{ t.remark }}</td>
            <td class="p-2 text-[var(--color-text-muted)]">{{ t.created_at?.slice(5, 19) }}</td>
          </tr>
          </tbody>
        </table>
        <div v-if="!loading && !txns.length" class="py-4 text-center text-sm text-[var(--color-text-muted)]">暂无交易记录</div>
      </div>
    </template>

    <!-- ════════════ Reconciliation Tab ════════════ -->
    <template v-if="activeTab === 'reconciliation'">
      <!-- Controls -->
      <div class="flex flex-wrap items-center gap-3">
        <div class="flex items-center gap-2">
          <label class="text-xs text-[var(--color-text-muted)]">统计日期</label>
          <input
            type="date"
            v-model="selectedDate"
            class="px-3 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-bg)] text-[var(--color-text)]"
            @change="loadReconciliation"
          />
        </div>
        <button
          class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded transition-colors"
          :class="refreshing
            ? 'bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] cursor-not-allowed'
            : 'bg-[var(--color-primary)] text-white hover:opacity-90'"
          :disabled="refreshing"
          @click="refreshDailyStats"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': refreshing }" />
          {{ refreshing ? '刷新中...' : '刷新当日统计' }}
        </button>
        <a
          :href="`/api/merchant/daily-stats/merchant/export?date=${selectedDate}`"
          class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded transition-colors bg-[var(--color-bg-elevated)] text-[var(--color-text)] hover:bg-[var(--color-border)] border border-[var(--color-border)]"
          target="_blank"
        >
          📥 导出 CSV
        </a>
      </div>

      <!-- Sub-tabs -->
      <div class="flex gap-4 mt-4">
        <button
          class="px-3 py-1.5 text-sm font-medium rounded transition-colors"
          :class="reconSubTab === 'merchant'
            ? 'bg-[var(--color-primary)] text-white'
            : 'bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]'"
          @click="reconSubTab = 'merchant'"
        >按API支付商</button>
        <button
          class="px-3 py-1.5 text-sm font-medium rounded transition-colors"
          :class="reconSubTab === 'category'
            ? 'bg-[var(--color-primary)] text-white'
            : 'bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]'"
          @click="reconSubTab = 'category'"
        >按品类</button>
      </div>

      <!-- Loading -->
      <div v-if="reconLoading" class="text-sm text-[var(--color-text-muted)] py-4">加载中...</div>

      <!-- ============ Merchant Table ============ -->
      <div v-else-if="reconSubTab === 'merchant'" class="card p-4 mt-2 overflow-x-auto">
        <table class="w-full text-xs whitespace-nowrap">
          <thead>
            <tr class="border-b border-[var(--color-border)]">
              <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">商户名称</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">今日订单数</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">今日金额</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">昨日订单数</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">昨日金额</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">前日订单数</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">前日金额</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">汇总订单数</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">汇总金额</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in pivotMerchantRows" :key="r.api_payer_id"
                class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
              <td class="p-2 font-medium text-[var(--color-text)]">{{ r.merchant_name }}</td>
              <td class="p-2 text-right">{{ r.d0_orders }}</td>
              <td class="p-2 text-right font-mono">{{ formatAmount(r.d0_amount) }}</td>
              <td class="p-2 text-right">{{ r.d1_orders }}</td>
              <td class="p-2 text-right font-mono">{{ formatAmount(r.d1_amount) }}</td>
              <td class="p-2 text-right">{{ r.d2_orders }}</td>
              <td class="p-2 text-right font-mono">{{ formatAmount(r.d2_amount) }}</td>
              <td class="p-2 text-right font-semibold">{{ r.total_orders }}</td>
              <td class="p-2 text-right font-mono font-semibold text-[var(--color-primary)]">{{ formatAmount(r.total_amount) }}</td>
            </tr>
            <tr v-if="!pivotMerchantRows.length">
              <td colspan="9" class="p-4 text-center text-[var(--color-text-muted)]">暂无数据</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ============ Category Table ============ -->
      <div v-else-if="reconSubTab === 'category'" class="card p-4 mt-2 overflow-x-auto">
        <table class="w-full text-xs whitespace-nowrap">
          <thead>
            <tr class="border-b border-[var(--color-border)]">
              <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">品类名称</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">今日销量</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">今日金额</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">占比</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">昨日销量</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">昨日金额</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">前日销量</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">前日金额</th>
              <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">汇总金额</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in pivotCategoryRows" :key="r.product_id"
                class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
              <td class="p-2 font-medium text-[var(--color-text)]">{{ r.product_name }}
                <span class="text-[var(--color-text-muted)] ml-1">({{ r.category }})</span>
              </td>
              <td class="p-2 text-right">{{ r.d0_orders }}</td>
              <td class="p-2 text-right font-mono">{{ formatAmount(r.d0_amount) }}</td>
              <td class="p-2 text-right font-mono text-[var(--color-primary)]">{{ r.ratio }}</td>
              <td class="p-2 text-right">{{ r.d1_orders }}</td>
              <td class="p-2 text-right font-mono">{{ formatAmount(r.d1_amount) }}</td>
              <td class="p-2 text-right">{{ r.d2_orders }}</td>
              <td class="p-2 text-right font-mono">{{ formatAmount(r.d2_amount) }}</td>
              <td class="p-2 text-right font-mono font-semibold text-[var(--color-primary)]">{{ formatAmount(r.total_amount) }}</td>
            </tr>
            <tr v-if="!pivotCategoryRows.length">
              <td colspan="9" class="p-4 text-center text-[var(--color-text-muted)]">暂无数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
