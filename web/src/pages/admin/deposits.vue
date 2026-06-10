<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/utils/api'
import Badge from '@/components/ui/Badge.vue'
import {
  CheckCircle, XCircle, Plus, Copy, Trash2,
  Wallet, Activity, RefreshCw, ExternalLink, Bell, BellRing
} from 'lucide-vue-next'

// ── Tab state ────────────────────────────────────────
const activeTab = ref<'review' | 'addresses' | 'monitor'>('review')

// ── Toast ────────────────────────────────────────────
const toast = ref('')
function showToast(msg: string, duration = 3000) {
  toast.value = msg
  setTimeout(() => toast.value = '', duration)
}

// ══════════════════════════════════════════════════════
// TAB 1: Deposit Review
// ══════════════════════════════════════════════════════
const deposits = ref<any[]>([])
const loading = ref(true)
const filterStatus = ref('PENDING')
const confirmDialog = ref<{deposit: any; note: string; show: boolean}>({ deposit: null, note: '', show: false })
const rejectDialog = ref<{deposit: any; note: string; show: boolean}>({ deposit: null, note: '', show: false })
const confirmLoading = ref(false)

const depositStatusLabels: Record<string, string> = {
  PENDING: '待审核', CONFIRMED: '已到账', REJECTED: '已驳回',
}

async function loadData() {
  loading.value = true
  try {
    const qs = filterStatus.value ? `?status=${filterStatus.value}` : ''
    const r = await api.get<{code: number; data: {items: any[]}}>(`/api/admin/deposits${qs}&limit=50`)
    deposits.value = r.data.items
  } finally { loading.value = false }
}

async function confirmDeposit() {
  if (!confirmDialog.value.deposit) return
  confirmLoading.value = true
  try {
    const did = confirmDialog.value.deposit.id
    const note = encodeURIComponent(confirmDialog.value.note)
    await api.post(`/api/admin/deposits/${did}/confirm?admin_note=${note}`, {})
    showToast('确认成功')
    confirmDialog.value.show = false
    confirmDialog.value.note = ''
    await loadData()
  } catch (e: any) { showToast(`错误: ${e.message || e}`) }
  finally { confirmLoading.value = false }
}

async function rejectDeposit() {
  if (!rejectDialog.value.deposit) return
  confirmLoading.value = true
  try {
    const did = rejectDialog.value.deposit.id
    const note = encodeURIComponent(rejectDialog.value.note)
    await api.post(`/api/admin/deposits/${did}/reject?admin_note=${note}`, {})
    showToast('已驳回')
    rejectDialog.value.show = false
    rejectDialog.value.note = ''
    await loadData()
  } catch (e: any) { showToast(`错误: ${e.message || e}`) }
  finally { confirmLoading.value = false }
}

// ══════════════════════════════════════════════════════
// TAB 2: Platform Addresses
// ══════════════════════════════════════════════════════
const platformAddresses = ref<any[]>([])
const showAddrForm = ref(false)
const addrForm = ref({ chain: 'TRC20', address: '', label: '' })
const addrEditId = ref<number | null>(null)

const chainLabels: Record<string, string> = {
  TRC20: 'TRC20 (波场)', ERC20: 'ERC20 (以太坊)', BSC: 'BSC (币安链)',
}

async function loadAddresses() {
  const r = await api.get<{code: number; data: any[]}>('/api/admin/deposit-addresses')
  platformAddresses.value = r.data
}

function openCreateAddr() {
  addrForm.value = { chain: 'TRC20', address: '', label: '' }
  addrEditId.value = null
  showAddrForm.value = true
}

function openEditAddr(a: any) {
  addrForm.value = { chain: a.chain, address: a.address, label: a.label || '' }
  addrEditId.value = a.id
  showAddrForm.value = true
}

async function saveAddress() {
  if (!addrForm.value.address) return
  try {
    if (addrEditId.value) {
      await api.put(`/api/admin/deposit-addresses/${addrEditId.value}?label=${encodeURIComponent(addrForm.value.label)}`, {})
    } else {
      await api.post(`/api/admin/deposit-addresses?owner_type=PLATFORM&owner_id=0&chain=${addrForm.value.chain}&address=${encodeURIComponent(addrForm.value.address)}&label=${encodeURIComponent(addrForm.value.label)}`, {})
    }
    showToast(addrEditId.value ? '已更新' : '已创建')
    showAddrForm.value = false
    await loadAddresses()
  } catch (e: any) { showToast(`失败: ${e.message || e}`) }
}

async function deleteAddress(id: number) {
  if (!confirm('确认删除此地址？')) return
  try {
    await api.delete(`/api/admin/deposit-addresses/${id}`)
    showToast('已删除')
    await loadAddresses()
  } catch (e: any) { showToast(`删除失败: ${e.message || e}`) }
}

// ══════════════════════════════════════════════════════
// TAB 3: Blockchain Monitor
// ══════════════════════════════════════════════════════
const blockchainAddrs = ref<any[]>([])
const blockchainTxns = ref<any[]>([])
const monitorLoading = ref(false)
const lastCheckTime = ref('')
const txnFilter = ref('')
// ── WebSocket ──────────────────────────────────────────────
const wsConnected = ref(false)
const newTxnAlert = ref<{count: number; matched: number; chain: string} | null>(null)
let ws: WebSocket | null = null
let wsReconnectTimer: ReturnType<typeof setTimeout> | null = null

function connectWS() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/api/admin/ws/blockchain`
  try {
    ws = new WebSocket(wsUrl)
    ws.onopen = () => { wsConnected.value = true }
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === 'new_transactions') {
          newTxnAlert.value = { count: msg.count, matched: msg.matched, chain: msg.chain }
          showToast(`🔔 检测到 ${msg.count} 笔新交易 (${msg.matched} 笔已匹配)`, 5000)
          // Auto-refresh data
          loadMonitorData()
          // Clear alert after 8s
          setTimeout(() => { newTxnAlert.value = null }, 8000)
        }
      } catch {}
    }
    ws.onclose = () => {
      wsConnected.value = false
      ws = null
      // Auto-reconnect after 5s
      wsReconnectTimer = setTimeout(connectWS, 5000)
    }
    ws.onerror = () => { ws?.close() }
  } catch { /* ignore */ }
}

function disconnectWS() {
  if (wsReconnectTimer) clearTimeout(wsReconnectTimer)
  if (ws) { ws.onclose = null; ws.close(); ws = null }
  wsConnected.value = false
}

const txnStatusLabels: Record<string, string> = {
  UNMATCHED: '未匹配', MATCHED: '已匹配', CLAIMED_MANUAL: '手动认领', IGNORED: '已忽略',
}
const txnStatusColors: Record<string, string> = {
  UNMATCHED: 'pending', MATCHED: 'success', CLAIMED_MANUAL: 'info', IGNORED: 'failed',
}

async function loadMonitorData() {
  monitorLoading.value = true
  try {
    // Load blockchain addresses with monitor state
    const aRes = await api.get<{code: number; data: any[]}>('/api/admin/blockchain/addresses')
    blockchainAddrs.value = aRes.data

    // Load blockchain transactions
    const qs = txnFilter.value ? `?status=${txnFilter.value}` : ''
    const tRes = await api.get<{code: number; data: {items: any[]; total: number}}>(`/api/admin/blockchain/transactions${qs}&limit=50`)
    blockchainTxns.value = tRes.data.items
  } finally {
    monitorLoading.value = false
    lastCheckTime.value = new Date().toLocaleString()
  }
}

async function refreshBalance(daId: number) {
  try {
    await api.post(`/api/admin/blockchain/refresh-balance?da_id=${daId}`, {})
    showToast('余额已刷新')
    await loadMonitorData()
  } catch (e: any) { showToast(`刷新失败: ${e.message || e}`) }
}

async function claimTxn(txnId: number) {
  const depositId = prompt('请输入要关联的充值记录ID:')
  if (!depositId || isNaN(Number(depositId))) return
  try {
    await api.post(`/api/admin/blockchain/claim?txn_id=${txnId}&deposit_id=${Number(depositId)}`, {})
    showToast('认领成功，积分已发放')
    await loadMonitorData()
  } catch (e: any) { showToast(`认领失败: ${e.message || e}`) }
}

async function ignoreTxn(txnId: number) {
  if (!confirm('确认忽略此交易？')) return
  try {
    await api.post(`/api/admin/blockchain/ignore?txn_id=${txnId}`, {})
    showToast('已忽略')
    await loadMonitorData()
  } catch (e: any) { showToast(`忽略失败: ${e.message || e}`) }
}

async function checkChainNow() {
  await loadMonitorData()
}

function copy(text: string) {
  navigator.clipboard.writeText(text)
  showToast('已复制', 2000)
}

// Format short address
function shortAddr(addr: string, len = 10): string {
  if (!addr) return '-'
  return addr.length > len * 2 ? `${addr.slice(0, len)}...${addr.slice(-len)}` : addr
}

function openExplorer(txHash: string) {
  window.open(`https://tronscan.org/#/transaction/${txHash}`, '_blank')
}

// Fix chain display
function parseChain(chain: string): string {
  return chain || '-'
}

onMounted(() => {
  loadData()
  loadAddresses()
  loadMonitorData()
  connectWS()
})

onUnmounted(() => {
  disconnectWS()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold text-[var(--color-text)]">USDT管理</h2>
      <div class="flex gap-1 bg-[var(--color-bg)] rounded-lg p-1 border border-[var(--color-border)]">
        <button v-for="t in [{k:'review',l:'充值审核'},{k:'addresses',l:'钱包地址'},{k:'monitor',l:'链上监控'}]" :key="t.k"
          class="px-3 py-1.5 text-xs rounded-md font-medium transition-colors"
          :class="activeTab === t.k ? 'bg-[var(--color-accent)] text-white' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'"
          @click="activeTab = t.k">
          {{ t.l }}
        </button>
      </div>
    </div>

    <!-- ════════════ TAB 1: Review ════════════ -->
    <template v-if="activeTab === 'review'">
      <div class="flex gap-2 items-center">
        <span class="text-sm text-[var(--color-text-muted)]">筛选:</span>
        <div class="flex gap-1 bg-[var(--color-bg)] rounded-lg p-1 border border-[var(--color-border)]">
          <button v-for="s in ['PENDING', 'CONFIRMED', 'REJECTED', '']" :key="s"
            class="px-3 py-1.5 text-xs rounded-md font-medium transition-colors"
            :class="filterStatus === s ? 'bg-[var(--color-accent)] text-white' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'"
            @click="filterStatus = s; loadData()">
            {{ s ? depositStatusLabels[s] : '全部' }}
          </button>
        </div>
      </div>
      <div class="card p-0 overflow-hidden">
        <div v-if="loading" class="p-6 text-sm text-[var(--color-text-muted)]">加载中...</div>
        <table v-else class="w-full text-sm">
          <thead><tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">ID</th>
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">申请人</th>
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">类型</th>
            <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">金额</th>
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">公链</th>
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">Tx Hash</th>
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">状态</th>
            <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">操作</th>
          </tr></thead>
          <tbody>
          <tr v-for="d in deposits" :key="d.id" class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
            <td class="p-3 font-mono text-xs text-[var(--color-text-muted)]">#{{ d.id }}</td>
            <td class="p-3 font-medium">{{ d.owner_name }}</td>
            <td class="p-3">
              <span class="text-xs px-1.5 py-0.5 rounded font-medium"
                :class="d.owner_type === 'SUPPLIER' ? 'bg-brand-info/10 text-brand-info' : 'bg-brand-warning/10 text-brand-warning'">
                {{ d.owner_type === 'SUPPLIER' ? '供应商' : '代理商' }}
              </span>
            </td>
            <td class="p-3 text-right font-mono font-semibold">{{ d.amount?.toLocaleString() }}</td>
            <td class="p-3 text-xs">{{ d.chain || '-' }}</td>
            <td class="p-3"><code class="text-xs bg-[var(--color-bg)] px-1.5 py-0.5 rounded font-mono max-w-[120px] inline-block truncate text-[var(--color-accent)]">{{ d.tx_hash }}</code></td>
            <td class="p-3"><Badge :status="d.status === 'PENDING' ? 'pending' : d.status === 'CONFIRMED' ? 'success' : 'failed'">{{ depositStatusLabels[d.status] || d.status }}</Badge></td>
            <td class="p-3 text-right">
              <template v-if="d.status === 'PENDING'">
                <button class="btn btn-sm mr-1 bg-green-500/10 text-green-500 hover:bg-green-500/20" @click="confirmDialog = { deposit: d, note: '', show: true }"><CheckCircle class="w-3 h-3" /> 确认</button>
                <button class="btn btn-sm bg-red-500/10 text-red-500 hover:bg-red-500/20" @click="rejectDialog = { deposit: d, note: '', show: true }"><XCircle class="w-3 h-3" /> 驳回</button>
              </template>
              <span v-else class="text-xs text-[var(--color-text-muted)]">-</span>
            </td>
          </tr>
          </tbody>
        </table>
        <div v-if="!loading && !deposits.length" class="p-6 text-center text-sm text-[var(--color-text-muted)]">暂无充值记录</div>
      </div>
    </template>

    <!-- ════════════ TAB 2: Addresses ════════════ -->
    <template v-if="activeTab === 'addresses'">
      <div class="flex justify-between items-center">
        <p class="text-sm text-[var(--color-text-muted)]">管理平台USDT收款地址，用户向这些地址转账后提交充值申请</p>
        <button class="btn btn-primary btn-sm" @click="openCreateAddr"><Plus class="w-4 h-4" /> 新增地址</button>
      </div>
      <div class="card p-0 overflow-hidden">
        <table class="w-full text-sm">
          <thead><tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">公链</th>
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">收款地址</th>
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">标签</th>
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">状态</th>
            <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">操作</th>
          </tr></thead>
          <tbody>
          <tr v-for="a in platformAddresses" :key="a.id" class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
            <td class="p-3 font-medium" :class="a.chain === 'TRC20' ? 'text-[#00B4F0]' : a.chain === 'ERC20' ? 'text-[#627EEA]' : 'text-[#F0B90B]'">{{ chainLabels[a.chain] || a.chain }}</td>
            <td class="p-3">
              <div class="flex items-center gap-1">
                <code class="text-xs font-mono bg-[var(--color-bg)] px-1.5 py-0.5 rounded max-w-[260px] truncate">{{ a.address }}</code>
                <button @click="copy(a.address)" class="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"><Copy class="w-3 h-3" /></button>
              </div>
            </td>
            <td class="p-3 text-[var(--color-text-muted)] text-xs">{{ a.label || '-' }}</td>
            <td class="p-3"><Badge :status="a.status === 'ACTIVE' ? 'success' : 'failed'">{{ a.status === 'ACTIVE' ? '启用' : '停用' }}</Badge></td>
            <td class="p-3 text-right">
              <button class="btn btn-outline btn-sm mr-1" @click="openEditAddr(a)">编辑</button>
              <button class="btn btn-outline btn-sm text-[var(--color-danger)]" @click="deleteAddress(a.id)"><Trash2 class="w-3 h-3" /> 删除</button>
            </td>
          </tr>
          </tbody>
        </table>
        <div v-if="!platformAddresses.length" class="p-6 text-center text-sm text-[var(--color-text-muted)]">暂无平台收款地址，请先添加</div>
      </div>
      <!-- Address form modal -->
      <div v-if="showAddrForm" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" @click.self="showAddrForm = false">
        <div class="card p-6 w-full max-w-md mx-4">
          <h3 class="text-base font-semibold mb-4">{{ addrEditId ? '编辑' : '新增' }}平台收款地址</h3>
          <div class="space-y-3">
            <div>
              <label class="block text-xs text-[var(--color-text-muted)] mb-1">公链</label>
              <select v-model="addrForm.chain" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm" :disabled="!!addrEditId">
                <option value="TRC20">TRC20 (波场)</option>
                <option value="ERC20">ERC20 (以太坊)</option>
                <option value="BSC">BSC (币安链)</option>
              </select>
            </div>
            <div>
              <label class="block text-xs text-[var(--color-text-muted)] mb-1">收款地址</label>
              <input v-model="addrForm.address" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm font-mono" placeholder="USDT 收款地址" />
            </div>
            <div>
              <label class="block text-xs text-[var(--color-text-muted)] mb-1">标签</label>
              <input v-model="addrForm.label" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm" placeholder="主钱包" />
            </div>
          </div>
          <div class="flex justify-end gap-2 mt-4">
            <button class="btn btn-outline" @click="showAddrForm = false">取消</button>
            <button class="btn btn-primary" :disabled="!addrForm.address" @click="saveAddress">保存</button>
          </div>
        </div>
      </div>
    </template>

    <!-- ════════════ TAB 3: Monitor ════════════ -->
    <template v-if="activeTab === 'monitor'">
      <!-- Address cards with balance -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div v-for="a in blockchainAddrs" :key="a.id" class="card p-4 relative overflow-hidden">
          <!-- Status indicator dot -->
          <div class="absolute top-0 right-0 w-16 h-16 -mr-6 -mt-6 rounded-full opacity-10"
            :class="a.status === 'ACTIVE' ? 'bg-green-500' : 'bg-red-500'"></div>

          <div class="flex items-start justify-between mb-3">
            <div>
              <span class="font-medium" :class="a.chain === 'TRC20' ? 'text-[#00B4F0]' : a.chain === 'ERC20' ? 'text-[#627EEA]' : 'text-[#F0B90B]'">
                {{ chainLabels[a.chain] || a.chain }}
              </span>
              <span v-if="a.label" class="ml-2 text-xs text-[var(--color-text-muted)]">({{ a.label }})</span>
            </div>
            <div class="flex gap-1">
              <Badge :status="a.status === 'ACTIVE' ? 'success' : 'failed'">{{ a.status === 'ACTIVE' ? '监听中' : '已停用' }}</Badge>
            </div>
          </div>

          <code class="text-xs font-mono break-all leading-relaxed block mb-3">{{ a.address }}</code>

          <!-- Balance + Stats -->
          <div class="grid grid-cols-3 gap-3 mb-3">
            <div class="bg-[var(--color-bg)] rounded-lg p-2 text-center">
              <div class="text-lg font-bold" :class="a.balance > 0 ? 'text-[var(--color-success)]' : 'text-[var(--color-text-muted)]'">
                {{ a.balance?.toFixed(2) || '0.00' }}
              </div>
              <div class="text-[10px] text-[var(--color-text-muted)]">USDT 余额</div>
            </div>
            <div class="bg-[var(--color-bg)] rounded-lg p-2 text-center">
              <div class="text-sm font-mono">{{ a.last_block?.toLocaleString() || '0' }}</div>
              <div class="text-[10px] text-[var(--color-text-muted)]">已扫描区块</div>
            </div>
            <div class="bg-[var(--color-bg)] rounded-lg p-2 text-center">
              <div class="text-sm font-mono">{{ a.poll_count || '0' }}</div>
              <div class="text-[10px] text-[var(--color-text-muted)]">轮询次数</div>
            </div>
          </div>

          <!-- Error display -->
          <div v-if="a.last_error" class="mb-2 p-2 rounded bg-red-500/5 border border-red-500/20 text-xs text-red-500">
            {{ a.last_error }}
          </div>

          <!-- Actions -->
          <div class="flex gap-2">
            <button class="btn btn-outline btn-sm flex-1 justify-center" @click="copy(a.address)">
              <Copy class="w-3 h-3" /> 复制
            </button>
            <button class="btn btn-outline btn-sm flex-1 justify-center" @click="refreshBalance(a.id)">
              <RefreshCw class="w-3 h-3" /> 查余额
            </button>
            <button v-if="a.chain === 'TRC20'" class="btn btn-outline btn-sm flex-1 justify-center"
              @click="window.open(`https://tronscan.org/#/address/${a.address}`, '_blank')">
              <ExternalLink class="w-3 h-3" /> 浏览器
            </button>
          </div>

          <div v-if="a.monitor_updated_at" class="mt-2 text-[10px] text-[var(--color-text-muted)]">
            上次监控: {{ a.monitor_updated_at?.slice(5, 19) || '-' }}
          </div>
        </div>
      </div>

      <!-- Blockchain Transactions -->
      <div class="card p-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold flex items-center gap-2">
            <Activity class="w-4 h-4" /> 检测到的链上交易
            <span v-if="blockchainTxns.length" class="text-xs text-[var(--color-text-muted)] font-normal">({{ blockchainTxns.length }} 条)</span>
          </h3>
          <div class="flex gap-2 items-center">
            <select v-model="txnFilter" @change="loadMonitorData" class="text-xs px-2 py-1 rounded border border-[var(--color-border)] bg-[var(--color-bg)]">
              <option value="">全部状态</option>
              <option value="UNMATCHED">未匹配</option>
              <option value="MATCHED">已匹配</option>
              <option value="CLAIMED_MANUAL">手动认领</option>
              <option value="IGNORED">已忽略</option>
            </select>
            <button class="btn btn-outline btn-sm" :disabled="monitorLoading" @click="checkChainNow">
              <RefreshCw class="w-3 h-3" :class="{ 'animate-spin': monitorLoading }" /> 刷新
            </button>
          </div>
        </div>

        <div v-if="lastCheckTime" class="text-xs text-[var(--color-text-muted)] mb-2">上次刷新: {{ lastCheckTime }}</div>

        <div v-if="monitorLoading" class="text-sm text-[var(--color-text-muted)] py-4">加载中...</div>
        <table v-else class="w-full text-xs">
          <thead><tr class="border-b border-[var(--color-border)]">
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">Tx Hash</th>
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">发送方</th>
            <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">金额</th>
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">状态</th>
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">关联充值</th>
            <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">时间</th>
            <th class="text-right p-2 font-semibold text-[var(--color-text-muted)]">操作</th>
          </tr></thead>
          <tbody>
          <tr v-for="tx in blockchainTxns" :key="tx.id" class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
            <td class="p-2">
              <div class="flex items-center gap-1">
                <code class="font-mono">{{ shortAddr(tx.tx_hash, 12) }}</code>
                <button @click="copy(tx.tx_hash)" class="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"><Copy class="w-3 h-3" /></button>
                <button @click="openExplorer(tx.tx_hash)" class="text-[var(--color-accent)] hover:underline"><ExternalLink class="w-3 h-3" /></button>
              </div>
            </td>
            <td class="p-2 font-mono">{{ shortAddr(tx.from_address, 8) }}</td>
            <td class="p-2 text-right font-mono font-semibold">{{ tx.amount?.toFixed(2) }} USDT</td>
            <td class="p-2"><Badge :status="txnStatusColors[tx.status] || 'default'">{{ txnStatusLabels[tx.status] || tx.status }}</Badge></td>
            <td class="p-2 text-[var(--color-text-muted)]">
              {{ tx.deposit_id ? `#${tx.deposit_id}` : '-' }}
            </td>
            <td class="p-2 text-[var(--color-text-muted)]">{{ tx.created_at?.slice(5, 19) || '-' }}</td>
            <td class="p-2 text-right">
              <template v-if="tx.status === 'UNMATCHED'">
                <button class="btn btn-outline btn-xs mr-1" @click="claimTxn(tx.id)">认领</button>
                <button class="btn btn-outline btn-xs text-[var(--color-danger)]" @click="ignoreTxn(tx.id)">忽略</button>
              </template>
              <span v-else class="text-[var(--color-text-muted)]">-</span>
            </td>
          </tr>
          </tbody>
        </table>
        <div v-if="!monitorLoading && !blockchainTxns.length" class="py-8 text-center text-sm text-[var(--color-text-muted)]">
          <div class="text-3xl mb-2 opacity-30">⛓️</div>
          <p>暂无链上交易记录</p>
          <p class="text-xs mt-1">监控正在运行，每45秒自动轮询一次。新的USDT转入交易会自动显示在这里。</p>
        </div>
      </div>

      <!-- Auto-monitor info -->
      <!-- Real-time alert banner -->
      <div v-if="newTxnAlert" class="card p-4 border-2 animate-pulse"
        :class="newTxnAlert.matched > 0 ? 'border-green-500/50 bg-green-500/5' : 'border-brand-warning/50 bg-brand-warning/5'">
        <div class="flex items-center gap-3">
          <BellRing class="w-5 h-5" :class="newTxnAlert.matched > 0 ? 'text-green-500' : 'text-brand-warning'" />
          <div>
            <p class="text-sm font-semibold">
              检测到 {{ newTxnAlert.count }} 笔新交易
              <span v-if="newTxnAlert.matched > 0" class="text-green-500">({{ newTxnAlert.matched }} 笔已自动匹配)</span>
              <span v-else class="text-brand-warning">(待手动处理)</span>
            </p>
            <p class="text-xs text-[var(--color-text-muted)]">{{ newTxnAlert.chain }} · {{ new Date().toLocaleTimeString() }}</p>
          </div>
          <button class="ml-auto btn btn-outline btn-sm" @click="loadMonitorData()">查看</button>
        </div>
      </div>

      <div class="card p-4 bg-[var(--color-bg)] border border-[var(--color-border)]">
        <div class="flex items-center gap-2 mb-2">
          <Activity class="w-4 h-4 text-[var(--color-success)]" />
          <h3 class="text-sm font-semibold">自动监测状态</h3>
          <Badge status="success">运行中</Badge>
          <Badge :status="wsConnected ? 'success' : 'failed'">{{ wsConnected ? 'WS 已连接' : 'WS 离线' }}</Badge>
        </div>
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
          <div>
            <span class="text-[var(--color-text-muted)]">轮询间隔</span>
            <div class="font-medium">45 秒</div>
          </div>
          <div>
            <span class="text-[var(--color-text-muted)]">监测公链</span>
            <div class="font-medium text-[#00B4F0]">TRC20 (波场)</div>
          </div>
          <div>
            <span class="text-[var(--color-text-muted)]">USDT合约</span>
            <div class="font-mono text-xs">TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t</div>
          </div>
          <div>
            <span class="text-[var(--color-text-muted)]">自动匹配</span>
            <div class="font-medium text-[var(--color-success)]">已启用</div>
          </div>
        </div>
        <div class="mt-3 text-xs text-[var(--color-text-muted)] border-t border-[var(--color-border)] pt-3 space-y-1">
          <p>• 系统每45秒自动轮询平台钱包地址的USDT转入交易</p>
          <p>• 检测到新交易后，自动匹配 <code class="bg-[var(--color-bg)] px-1 rounded">deposits</code> 表中的 <code class="bg-[var(--color-bg)] px-1 rounded">tx_hash</code></p>
          <p>• 匹配成功 → 自动确认到账 + 发放积分；未匹配 → 显示在列表中，管理员可手动认领</p>
          <p>• 测试钱包: <code class="bg-[var(--color-bg)] px-1 rounded font-mono">TEvK7pDTCkB3U6STFd65TWgbiYDa8kH5tf</code>（真实活跃地址，每45秒自动检测转入交易）</p>
        </div>
      </div>
    </template>

    <!-- ═══ Dialogs ═══ -->
    <div v-if="confirmDialog.show" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" @click.self="confirmDialog.show = false">
      <div class="card p-6 w-full max-w-sm mx-4">
        <h3 class="text-base font-semibold mb-2">确认充值到账</h3>
        <p class="text-sm text-[var(--color-text-muted)] mb-4">确认 <strong>{{ confirmDialog.deposit?.owner_name }}</strong> 的 <strong>{{ confirmDialog.deposit?.amount?.toLocaleString() }}</strong> 积分充值</p>
        <input v-model="confirmDialog.note" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm mb-4" placeholder="审核备注（选填）" />
        <div class="flex justify-end gap-2">
          <button class="btn btn-outline" @click="confirmDialog.show = false">取消</button>
          <button class="btn btn-primary" :disabled="confirmLoading" @click="confirmDeposit">{{ confirmLoading ? '确认中...' : '确认到账' }}</button>
        </div>
      </div>
    </div>

    <div v-if="rejectDialog.show" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" @click.self="rejectDialog.show = false">
      <div class="card p-6 w-full max-w-sm mx-4">
        <h3 class="text-base font-semibold mb-2">驳回充值申请</h3>
        <p class="text-sm text-[var(--color-text-muted)] mb-4">驳回 <strong>{{ rejectDialog.deposit?.owner_name }}</strong></p>
        <input v-model="rejectDialog.note" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm mb-4" placeholder="驳回原因" />
        <div class="flex justify-end gap-2">
          <button class="btn btn-outline" @click="rejectDialog.show = false">取消</button>
          <button class="btn btn-danger" :disabled="confirmLoading" @click="rejectDeposit">{{ confirmLoading ? '处理中...' : '确认驳回' }}</button>
        </div>
      </div>
    </div>

    <div v-if="toast" class="fixed bottom-6 right-6 card p-3 max-w-sm z-50 shadow-xl"
      :class="toast.includes('失败') ? 'border-red-500/50' : 'border-[var(--color-success)]/50'">
      <p class="text-sm">{{ toast }}</p>
    </div>
  </div>
</template>
