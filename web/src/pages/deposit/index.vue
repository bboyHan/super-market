<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '@/utils/api'
import { Copy, CheckCircle, ExternalLink, AlertTriangle, Clock, Wallet, TrendingUp, Send } from 'lucide-vue-next'

const wallet = ref({ balance: 0, frozen: 0, total_recharge: 0, available: 0 })
const deposits = ref<any[]>([])
const exchangeRate = ref(1.0)
const loading = ref(true)

// Form
const selectedChain = ref('TRC20')
const amount = ref(0)
const txHash = ref('')
const submitting = ref(false)
const submitResult = ref('')
const copied = ref(false)

// Platform addresses — fetched from API
const platformAddresses = ref<Record<string, string>>({})
const addressesError = ref(false)

const chainOptions = [
  { value: 'TRC20', label: 'TRC20 (波场)', color: 'text-[#00B4F0]', desc: '推荐 · 手续费低、到账快' },
  { value: 'ERC20', label: 'ERC20 (以太坊)', color: 'text-[#627EEA]', desc: '通用协议' },
  { value: 'BSC', label: 'BSC (币安链)', color: 'text-[#F0B90B]', desc: '币安智能链' },
]

const currentAddress = computed(() => platformAddresses.value[selectedChain.value] || '')
const noAddressConfigured = computed(() => {
  return Object.keys(platformAddresses.value).length === 0
})
const estimatedPoints = computed(() => {
  if (!amount.value || amount.value <= 0) return 0
  return Math.floor(amount.value * exchangeRate.value * 100) / 100
})

const statusLabels: Record<string, string> = {
  PENDING: '待审核', CONFIRMED: '已到账', REJECTED: '已驳回',
}

async function loadData() {
  loading.value = true
  try {
    const [wr, dr, er, ar] = await Promise.all([
      api.get<{code: number; data: any}>('/api/merchant/wallet'),
      api.get<{code: number; data: {items: any[]}}>('/api/merchant/deposits?limit=50'),
      api.get<{code: number; data: any}>('/api/merchant/exchange-rate'),
      api.get<{code: number; data: any[]}>('/api/merchant/deposit-addresses'),
    ])
    wallet.value = wr.data
    deposits.value = dr.data.items
    exchangeRate.value = er.data?.rate || 1.0
    // Build addresses lookup: array → Record<chain, address>
    const addrMap: Record<string, string> = {}
    if (ar.data && Array.isArray(ar.data)) {
      for (const a of ar.data) {
        if (a.chain && a.address) {
          addrMap[a.chain] = a.address
        }
      }
    }
    platformAddresses.value = addrMap
    addressesError.value = false
  } catch (e) {
    addressesError.value = true
    platformAddresses.value = {}
  } finally { loading.value = false }
}

async function submitDeposit() {
  if (!amount.value || amount.value <= 0 || !txHash.value.trim()) return
  submitting.value = true
  submitResult.value = ''
  try {
    const r = await api.post(
      `/api/merchant/deposits?amount=${amount.value}&tx_hash=${encodeURIComponent(txHash.value)}&remark=USDT充值&chain=${selectedChain.value}`,
      {})
    submitResult.value = r.message || '提交成功'
    amount.value = 0
    txHash.value = ''
    await loadData()
  } catch (e: any) {
    submitResult.value = `提交失败: ${e.message || e}`
  } finally {
    submitting.value = false
    setTimeout(() => submitResult.value = '', 5000)
  }
}

function copyAddress() {
  if (!currentAddress.value) return
  navigator.clipboard.writeText(currentAddress.value)
  copied.value = true
  setTimeout(() => copied.value = false, 2000)
}

function openExplorer() {
  const urls: Record<string, string> = {
    TRC20: `https://tronscan.org/#/address/${currentAddress.value}`,
    ERC20: `https://etherscan.io/address/${currentAddress.value}`,
    BSC: `https://bscscan.com/address/${currentAddress.value}`,
  }
  window.open(urls[selectedChain.value] || urls.TRC20, '_blank')
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <!-- Asset Overview -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div class="card p-4">
        <div class="flex items-center gap-2 text-[var(--color-text-muted)] text-xs mb-2"><Wallet class="w-4 h-4" /> 可用积分</div>
        <div class="text-2xl font-bold">{{ wallet.available?.toLocaleString() }}</div>
      </div>
      <div class="card p-4">
        <div class="flex items-center gap-2 text-[var(--color-text-muted)] text-xs mb-2"><TrendingUp class="w-4 h-4" /> 当前汇率</div>
        <div class="text-2xl font-bold text-[var(--color-accent)]">1 USDT = {{ exchangeRate }} 积分</div>
      </div>
      <div class="card p-4">
        <div class="flex items-center gap-2 text-[var(--color-text-muted)] text-xs mb-2"><Clock class="w-4 h-4" /> 总充值</div>
        <div class="text-2xl font-bold text-[var(--color-success)]">{{ wallet.total_recharge?.toLocaleString() }}</div>
      </div>
    </div>

    <!-- Risk Warning -->
    <div class="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
      <div class="flex items-start gap-3">
        <AlertTriangle class="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
        <div class="text-xs text-red-500 space-y-1">
          <p class="font-semibold text-sm">重要提醒</p>
          <p>请务必选择对应公链转账。<strong>转错链、转错币种、转错地址资金将无法找回</strong>。</p>
          <p>仅支持转账 <strong>USDT</strong>，请勿转入其他代币。最小充值金额 <strong>1.00 USDT</strong>。</p>
        </div>
      </div>
    </div>

    <!-- Main: Address + Form -->
    <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <!-- Left: Platform Address + QR -->
      <div class="lg:col-span-2 card p-5 flex flex-col items-center">
        <template v-if="noAddressConfigured">
          <AlertTriangle class="w-10 h-10 text-amber-500 mb-3" />
          <h3 class="text-base font-semibold mb-1">暂无充值地址</h3>
          <p class="text-xs text-amber-500 text-center leading-relaxed">
            暂无配置充值地址，请联系管理员
          </p>
        </template>
        <template v-else>
        <h3 class="text-base font-semibold mb-1">平台USDT收款地址</h3>
        <p class="text-xs text-[var(--color-text-muted)] mb-4">向下方地址转账后提交交易哈希</p>

        <!-- Chain selector -->
        <div class="flex gap-1 mb-4 bg-[var(--color-bg)] rounded-lg p-1 border border-[var(--color-border)]">
          <button v-for="c in chainOptions" :key="c.value"
            @click="selectedChain = c.value"
            :class="[
              'px-3 py-1.5 text-xs rounded-md font-medium transition-colors',
              selectedChain === c.value
                ? 'bg-[var(--color-accent)] text-white'
                : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
            ]">
            <span :class="c.color">{{ c.label }}</span>
          </button>
        </div>

        <!-- QR -->
        <div class="w-full max-w-[180px] aspect-square mb-3 bg-white rounded-lg p-2 border border-[var(--color-border)]">
          <img :src="`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(currentAddress)}`"
            alt="QR" class="w-full h-full" />
        </div>

        <!-- Address -->
        <div class="w-full bg-[var(--color-bg)] rounded-lg p-2.5 border border-[var(--color-border)] mb-2">
          <code class="text-xs font-mono break-all leading-relaxed">{{ currentAddress }}</code>
        </div>
        <div class="flex gap-2 w-full">
          <button class="btn btn-primary btn-sm flex-1 justify-center" @click="copyAddress">
            <Copy class="w-3.5 h-3.5" /> {{ copied ? '已复制' : '复制地址' }}
          </button>
          <button class="btn btn-outline btn-sm flex-1 justify-center" @click="openExplorer">
            <ExternalLink class="w-3.5 h-3.5" /> 浏览器
          </button>
        </div>
        </template>
      </div>

      <!-- Right: Submit form -->
      <div class="lg:col-span-3 card p-5">
        <h3 class="text-base font-semibold mb-4">提交充值申请</h3>
        <div class="space-y-4">
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">充值金额 (USDT)</label>
            <input v-model.number="amount" type="number" min="1" step="0.01"
              class="w-full px-3 py-2.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm font-mono"
              placeholder="请输入金额" />
          </div>

          <div class="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
            <div class="flex justify-between">
              <span class="text-xs text-[var(--color-text-muted)]">预计到账积分</span>
              <span class="text-lg font-bold font-mono text-[var(--color-accent)]">
                {{ amount > 0 ? estimatedPoints.toLocaleString() : '-' }}
              </span>
            </div>
            <div v-if="amount > 0" class="text-xs text-[var(--color-text-muted)] mt-1">
              {{ amount }} USDT × {{ exchangeRate }} = {{ estimatedPoints }} 积分
            </div>
          </div>

          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">交易哈希 (Tx Hash)</label>
            <input v-model="txHash" type="text"
              class="w-full px-3 py-2.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm font-mono"
              placeholder="0x..." />
          </div>

          <div v-if="submitResult" class="text-xs p-2 rounded"
            :class="submitResult.includes('失败') ? 'bg-red-500/10 text-red-500' : 'bg-green-500/10 text-green-500'">
            {{ submitResult }}
          </div>

          <button class="btn btn-primary w-full justify-center" :disabled="submitting || !amount || !txHash.trim()"
            @click="submitDeposit">
            <Send class="w-4 h-4" /> {{ submitting ? '提交中...' : '提交审核' }}
          </button>

          <p class="text-xs text-[var(--color-text-muted)] leading-relaxed">
            提交后等待管理员审核确认，通常1-2小时内完成。
          </p>
        </div>
      </div>
    </div>

    <!-- Deposit History -->
    <div class="card p-4">
      <h3 class="text-sm font-semibold mb-3 flex items-center gap-2">
        <Clock class="w-4 h-4" /> 充值记录
      </h3>
      <table class="w-full text-xs">
        <thead><tr class="border-b border-[var(--color-border)]">
          <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">金额</th>
          <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">公链</th>
          <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">Tx Hash</th>
          <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">状态</th>
          <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">备注</th>
          <th class="text-left p-2 font-semibold text-[var(--color-text-muted)]">时间</th>
        </tr></thead>
        <tbody>
        <tr v-for="d in deposits" :key="d.id" class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
          <td class="p-2 font-mono font-semibold">{{ d.amount?.toLocaleString() }}</td>
          <td class="p-2">
            <span :class="d.chain === 'TRC20' ? 'text-[#00B4F0]' : d.chain === 'ERC20' ? 'text-[#627EEA]' : ''">
              {{ d.chain || '-' }}
            </span>
          </td>
          <td class="p-2"><code class="font-mono max-w-[100px] truncate inline-block">{{ d.tx_hash?.slice(0, 16) }}...</code></td>
          <td class="p-2">
            <span :class="d.status === 'CONFIRMED' ? 'text-green-500' : d.status === 'REJECTED' ? 'text-red-500' : 'text-amber-500'"
              class="font-medium">{{ statusLabels[d.status] || d.status }}</span>
          </td>
          <td class="p-2 text-[var(--color-text-muted)] max-w-[80px] truncate">{{ d.remark || '-' }}</td>
          <td class="p-2 text-[var(--color-text-muted)]">{{ d.created_at?.slice(5, 19) }}</td>
        </tr>
        </tbody>
      </table>
      <div v-if="!deposits.length" class="py-4 text-center text-sm text-[var(--color-text-muted)]">暂无充值记录</div>
    </div>
  </div>
</template>
