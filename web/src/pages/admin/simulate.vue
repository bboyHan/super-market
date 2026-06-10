<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/utils/api'
import Badge from '@/components/ui/Badge.vue'
import { Terminal as TerminalIcon, Send, RefreshCw, Bell } from 'lucide-vue-next'

const apiPayers = ref<any[]>([])
const products = ref<any[]>([])
const orders = ref<any[]>([])
const loading = ref(true)

const simForm = ref({ api_payer_id: 1, product_id: 1, quantity: 1, client_order_id: '', callback_url: '' })
const simResult = ref<string>('')
const simLog = ref<string[]>([])

const activeOrderTab = ref<'all' | 'pending' | 'success'>('all')

function addLog(msg: string) {
  simLog.value.unshift(`[${new Date().toLocaleTimeString()}] ${msg}`)
  if (simLog.value.length > 50) simLog.value.pop()
}

async function loadData() {
  loading.value = true
  try {
    const [pR, prR, oR] = await Promise.all([
      api.get<{code: number; data: any[]}>('/api/admin/simulate/api-payers'),
      api.get<{code: number; data: any[]}>('/api/admin/simulate/products'),
      api.get<{code: number; data: {items: any[]}}>('/api/admin/simulate/orders?limit=20'),
    ])
    apiPayers.value = pR.data
    products.value = prR.data
    orders.value = oR.data.items
    if (apiPayers.value.length) simForm.value.api_payer_id = apiPayers.value[0].id
    if (products.value.length) simForm.value.product_id = products.value[0].id
    addLog('数据加载完成')
  } catch (e) {
    addLog('❌ 数据加载失败')
  } finally {
    loading.value = false
  }
}

async function createSimOrder() {
  simResult.value = ''
  try {
    const r = await api.post<{code: number; data: any; message: string}>('/api/admin/simulate/create-order', simForm.value)
    simResult.value = JSON.stringify(r.data, null, 2)
    addLog(`✅ 订单创建成功: ${r.data.platform_order_id} (${r.data.product_name} × ${r.data.quantity}, ${r.data.total_amount}积分)`)
    addLog(`  代理商: ${r.data.agent_name} | 回调: ${r.data.callback_url}`)
    await refreshOrders()
  } catch (e: any) {
    simResult.value = `❌ 失败: ${e.message || e}`
    addLog(`❌ 订单创建失败: ${e.message || e}`)
  }
}

async function confirmOrder(orderNo: string) {
  try {
    const r = await api.post<{code: number; message: string}>(`/api/merchant/orders/${orderNo}/confirm`, {})
    addLog(`✅ 确认收款: ${orderNo} → ${r.message}`)
    // Auto deliver after short delay
    setTimeout(() => deliverOrder(orderNo), 1500)
    await refreshOrders()
  } catch (e: any) {
    addLog(`❌ 确认失败: ${e.message || e}`)
  }
}

async function deliverOrder(orderNo: string) {
  try {
    const r = await api.post<{code: number; data: any; message: string}>(`/api/merchant/orders/${orderNo}/deliver`, {})
    addLog(`✅ 交付成功: ${orderNo} → ${r.data.delivery_content}`)
    addLog(`📡 回调已触发: ${orderNo}`)
    await refreshOrders()
  } catch (e: any) {
    addLog(`❌ 交付失败: ${e.message || e}`)
  }
}

async function refreshOrders() {
  const r = await api.get<{code: number; data: {items: any[]}}>('/api/admin/simulate/orders?limit=20')
  orders.value = r.data.items
  addLog('📋 订单列表已刷新')
}

async function triggerCallback(orderNo: string) {
  try {
    await api.post(`/api/admin/simulate/callback/${orderNo}`, {})
    addLog(`📡 回调已触发: ${orderNo}`)
    await refreshOrders()
  } catch (e: any) {
    addLog(`❌ 回调失败: ${e.message || e}`)
  }
}

const filteredOrders = ref<any[]>([])

const statusMap: Record<string, string> = {
  SUBMITTED: '待提交', PENDING: '待确认', DELIVERING: '交付中',
  SUCCESS: '已完成', CANCELLED: '已取消', EXPIRED: '已超时', FAILED: '失败',
}
const statusColor: Record<string, string> = {
  SUBMITTED: 'info', PENDING: 'warning', DELIVERING: 'warning',
  SUCCESS: 'success', CANCELLED: 'danger', EXPIRED: 'danger', FAILED: 'danger',
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-3">
      <TerminalIcon class="w-6 h-6 text-[var(--color-accent)]" />
      <div>
        <h2 class="text-2xl font-bold text-[var(--color-text)]">模拟终端</h2>
        <p class="text-sm text-[var(--color-text-muted)]">模拟 API 支付商创建订单、查询订单、接收回调</p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <!-- Order form -->
      <div class="card p-4">
        <h3 class="text-sm font-semibold text-[var(--color-text)] mb-3 flex items-center gap-2">
          <Send class="w-4 h-4" /> 创建订单
        </h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">API支付商</label>
            <select v-model="simForm.api_payer_id" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm text-[var(--color-text)]">
              <option v-for="p in apiPayers" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">货品</label>
            <select v-model="simForm.product_id" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm text-[var(--color-text)]">
              <option v-for="p in products" :key="p.id" :value="p.id">{{ p.name }} ({{ p.face_value }}积分)</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">数量</label>
            <input v-model.number="simForm.quantity" type="number" min="1" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm text-[var(--color-text)]" />
          </div>
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">客户端订单号（可选）</label>
            <input v-model="simForm.client_order_id" placeholder="留空自动生成" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm text-[var(--color-text)]" />
          </div>
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">回调地址（可选）</label>
            <input v-model="simForm.callback_url" placeholder="留空使用默认地址" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm text-[var(--color-text)]" />
          </div>
          <button class="btn btn-primary w-full justify-center" @click="createSimOrder">
            <Send class="w-4 h-4" /> 模拟下单
          </button>
        </div>
      </div>

      <!-- Result panel -->
      <div class="card p-4 lg:col-span-2">
        <h3 class="text-sm font-semibold text-[var(--color-text)] mb-3">操作日志</h3>
        <div class="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg p-3 max-h-64 overflow-y-auto font-mono text-xs space-y-1">
          <div v-for="(log, i) in simLog" :key="i" class="text-[var(--color-text-muted)]"
            :class="{ 'text-[var(--color-accent)]': log.includes('✅'), 'text-[var(--color-danger)]': log.includes('❌') }">
            {{ log }}
          </div>
          <div v-if="!simLog.length" class="text-[var(--color-text-muted)]">等待操作...</div>
        </div>

        <div v-if="simResult" class="mt-3">
          <h4 class="text-xs font-semibold text-[var(--color-text-muted)] mb-1">返回数据</h4>
          <pre class="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg p-3 text-xs font-mono text-[var(--color-text)] overflow-x-auto max-h-48">{{ simResult }}</pre>
        </div>
      </div>
    </div>

    <!-- Orders list -->
    <div class="card p-4">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-[var(--color-text)]">订单列表</h3>
        <button class="btn btn-outline btn-sm" @click="refreshOrders"><RefreshCw class="w-3 h-3" /> 刷新</button>
      </div>

      <!-- Status tabs -->
      <div class="flex gap-1 mb-3 border-b border-[var(--color-border)]">
        <button v-for="t in [{k:'all',l:'全部'},{k:'PENDING',l:'待确认'},{k:'DELIVERING',l:'交付中'},{k:'SUCCESS',l:'已完成'}]" :key="t.k"
          @click="activeOrderTab = t.k as any"
          :class="['px-3 py-1.5 text-xs font-medium border-b-2 transition-colors',
            activeOrderTab === t.k ? 'border-[var(--color-accent)] text-[var(--color-accent)]' : 'border-transparent text-[var(--color-text-muted)]']">
          {{ t.l }}
        </button>
      </div>

      <div v-if="loading" class="py-4 text-sm text-[var(--color-text-muted)]">加载中...</div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-xs">
          <thead><tr class="border-b border-[var(--color-border)]">
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">订单号</th>
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">API支付商</th>
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">货品</th>
            <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">金额</th>
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">状态</th>
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">代理商</th>
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">回调</th>
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">时间</th>
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">操作</th>
          </tr></thead>
          <tbody>
          <tr v-for="o in orders" :key="o.order_no"
            v-show="activeOrderTab === 'all' || o.status === activeOrderTab"
            class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
            <td class="p-2 font-mono">{{ o.order_no?.slice(-12) }}</td>
            <td class="p-2">{{ o.api_payer_name }}</td>
            <td class="p-2">{{ o.product_name }}</td>
            <td class="p-2 text-right font-mono">{{ o.amount }}</td>
            <td class="p-2"><Badge :type="statusColor[o.status] || 'info'">{{ statusMap[o.status] || o.status }}</Badge></td>
            <td class="p-2 text-[var(--color-text-muted)]">{{ o.agent_name }}</td>
            <td class="p-2">
              <Badge :type="o.callback_status === 'SUCCESS' ? 'success' : 'info'">{{ o.callback_status }}</Badge>
            </td>
            <td class="p-2 text-[var(--color-text-muted)]">{{ o.created_at?.slice(11, 19) }}</td>
            <td class="p-2">
              <button v-if="o.status === 'PENDING'"
                class="btn btn-primary btn-sm" @click="confirmOrder(o.order_no)">确认收款</button>
              <button v-else-if="o.status === 'DELIVERING'"
                class="btn btn-success btn-sm" @click="deliverOrder(o.order_no)">交付</button>
              <button v-else-if="o.status === 'SUCCESS' && o.callback_status !== 'SUCCESS'"
                class="btn btn-outline btn-sm" @click="triggerCallback(o.order_no)">
                <Bell class="w-3 h-3" /> 回调
              </button>
              <span v-else class="text-[var(--color-text-muted)] text-xs">-</span>
            </td>
          </tr>
          <tr v-if="!orders.length"><td colspan="9" class="p-4 text-center text-[var(--color-text-muted)]">暂无订单</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
