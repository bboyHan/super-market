<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/utils/api'
import Badge from '@/components/ui/Badge.vue'
import { Plus, Copy, RotateCw, ArrowUpRight, Eye, EyeOff, Shuffle, Key } from 'lucide-vue-next'

const agents = ref<any[]>([])
const loading = ref(true)
const showCreate = ref(false)
const nickname = ref('')
const formUsername = ref('')
const formPassword = ref('')
const showPassword = ref(false)
const generated = ref<any>(null)

// Transfer
const transferTarget = ref<any>(null)
const transferAmount = ref(0)
const transferLoading = ref(false)
const showTransfer = ref(false)
const walletInfo = ref({ balance: 0, available: 0 })
const toast = ref('')

// Revealed passwords (masked by default)
const revealedPw = ref<Record<number, boolean>>({})

async function load() {
  loading.value = true
  try {
    const [ar, wr] = await Promise.all([
      api.get<{code: number; data: any[]}>('/api/merchant/agents'),
      api.get<{code: number; data: any}>('/api/merchant/wallet'),
    ])
    agents.value = ar.data
    walletInfo.value = wr.data
  } finally { loading.value = false }
}

function genRandom() {
  formUsername.value = 'agent_' + Math.random().toString(36).slice(2, 10)
  formPassword.value = Math.random().toString(36).slice(2, 18)
}

async function createAgent() {
  if (!nickname.value) return
  try {
    const body: any = { nickname: nickname.value }
    if (formUsername.value) body.username = formUsername.value
    if (formPassword.value) body.password = formPassword.value
    const r = await api.post('/api/merchant/agents', body)
    generated.value = r.data
    showCreate.value = false
    nickname.value = ''
    formUsername.value = ''
    formPassword.value = ''
    await load()
  } catch (e: any) {
    toast.value = `创建失败: ${e.message || e}`
    setTimeout(() => toast.value = '', 5000)
  }
}

async function resetPassword(aid: number) {
  try {
    const r = await api.post(`/api/merchant/agents/${aid}/reset-password`, {})
    revealedPw.value[aid] = true
    // Update the local agent data with new password
    const a = agents.value.find(x => x.id === aid)
    if (a) a._newPassword = r.data.new_password
    toast.value = `新密码已生成: ${r.data.new_password}`
    setTimeout(() => {
      toast.value = ''
      if (a) a._newPassword = undefined
    }, 15000)
  } catch { /* ignore */ }
}

function copy(text: string) {
  navigator.clipboard.writeText(text)
  toast.value = '已复制'
  setTimeout(() => toast.value = '', 2000)
}

function maskPassword(pw: string) {
  if (!pw) return '••••••••'
  return pw.slice(0, 2) + '••••' + pw.slice(-2)
}

async function toggleStatus(a: any) {
  const ns = a.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
  await api.put(`/api/merchant/agents/${a.id}?status=${ns}`, {})
  await load()
}

function openTransfer(a: any) {
  transferTarget.value = a
  transferAmount.value = 0
  showTransfer.value = true
}

async function confirmTransfer() {
  if (!transferTarget.value || !transferAmount.value || transferAmount.value <= 0) return
  if (transferAmount.value > walletInfo.value.available) {
    toast.value = '可用积分不足'
    setTimeout(() => toast.value = '', 3000)
    return
  }
  transferLoading.value = true
  try {
    await api.post(`/api/merchant/wallet/transfer?agent_id=${transferTarget.value.id}&amount=${transferAmount.value}`, {})
    toast.value = `已向 ${transferTarget.value.nickname} 划转 ${transferAmount.value} 积分`
    showTransfer.value = false
    transferTarget.value = null
    await load()
  } catch (e: any) {
    toast.value = `划转失败: ${e.message || e}`
  } finally {
    transferLoading.value = false
    setTimeout(() => toast.value = '', 5000)
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <div>
        <h2 class="text-2xl font-bold text-[var(--color-text)]">代理商管理</h2>
        <p class="text-sm text-[var(--color-text-muted)]">管理代理商，创建账号、划转积分、重置密码</p>
      </div>
      <button class="btn btn-primary btn-sm" @click="showCreate = true"><Plus class="w-4 h-4" /> 创建代理商</button>
    </div>

    <!-- Supplier balance bar -->
    <div class="card p-3 flex items-center justify-between">
      <div class="text-sm">
        <span class="text-[var(--color-text-muted)]">我的可用积分：</span>
        <span class="font-bold font-mono text-lg">{{ walletInfo.available?.toLocaleString() }}</span>
      </div>
    </div>

    <div class="card p-0 overflow-hidden">
      <div v-if="loading" class="p-6 text-sm text-[var(--color-text-muted)]">加载中...</div>
      <table v-else class="w-full text-sm">
        <thead><tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">昵称</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">登录账号</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">登录密码</th>
          <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">积分</th>
          <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">状态</th>
          <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">操作</th>
        </tr></thead>
        <tbody>
        <tr v-for="a in agents" :key="a.id" class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
          <td class="p-3 font-medium">{{ a.nickname }}</td>
          <td class="p-3">
            <div class="flex items-center gap-1">
              <code class="text-xs bg-[var(--color-bg)] px-1.5 py-0.5 rounded font-mono text-[var(--color-accent)]">
                {{ a.username || '-' }}
              </code>
              <button v-if="a.username" @click="copy(a.username)" class="text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="复制账号">
                <Copy class="w-3 h-3" />
              </button>
            </div>
          </td>
          <td class="p-3">
            <div class="flex items-center gap-1">
              <code class="text-xs bg-[var(--color-bg)] px-1.5 py-0.5 rounded font-mono">
                <span v-if="revealedPw[a.id]">
                  {{ a._newPassword || '••••••••' }}
                </span>
                <span v-else>••••••••</span>
              </code>
              <button v-if="revealedPw[a.id]" @click="copy(a._newPassword || '')" class="text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="复制密码">
                <Copy class="w-3 h-3" />
              </button>
            </div>
          </td>
          <td class="p-3 text-right font-mono text-sm font-semibold">{{ a.balance?.toLocaleString() }}</td>
          <td class="p-3"><Badge :type="a.status === 'ACTIVE' ? 'success' : 'danger'">{{ a.status === 'ACTIVE' ? '启用' : '停用' }}</Badge></td>
          <td class="p-3 text-right space-x-1">
            <button class="btn btn-primary btn-sm" @click="openTransfer(a)">
              <ArrowUpRight class="w-3 h-3" /> 划转
            </button>
            <button class="btn btn-outline btn-sm" @click="resetPassword(a.id)">
              <RotateCw class="w-3 h-3" /> 重置密码
            </button>
            <button class="btn btn-outline btn-sm" @click="toggleStatus(a)">
              {{ a.status === 'ACTIVE' ? '停用' : '启用' }}
            </button>
          </td>
        </tr>
        </tbody>
      </table>
      <div v-if="!loading && !agents.length" class="p-6 text-center text-sm text-[var(--color-text-muted)]">暂无代理商，点击上方创建</div>
    </div>

    <!-- Create Modal -->
    <div v-if="showCreate" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" @click.self="showCreate = false">
      <div class="card p-6 w-full max-w-sm mx-4">
        <h3 class="text-base font-semibold mb-4">创建代理商</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">昵称</label>
            <input v-model="nickname" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm" placeholder="代理商名称" />
          </div>
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">登录账号（留空自动生成）</label>
            <div class="flex gap-2">
              <input v-model="formUsername" class="flex-1 px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm font-mono" placeholder="agent_xxx" />
              <button class="btn btn-outline btn-sm" @click="genRandom" title="随机生成"><Shuffle class="w-3 h-3" /></button>
            </div>
          </div>
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">登录密码（留空自动生成）</label>
            <div class="flex gap-2">
              <div class="flex-1 relative">
                <input v-model="formPassword" :type="showPassword ? 'text' : 'password'"
                  class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm font-mono" placeholder="自动生成" />
                <button class="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" @click="showPassword = !showPassword">
                  <Eye v-if="!showPassword" class="w-4 h-4" />
                  <EyeOff v-else class="w-4 h-4" />
                </button>
              </div>
              <button class="btn btn-outline btn-sm" @click="formPassword = Math.random().toString(36).slice(2, 18); showPassword = true" title="随机生成"><Shuffle class="w-3 h-3" /></button>
            </div>
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="btn btn-outline" @click="showCreate = false">取消</button>
          <button class="btn btn-primary" :disabled="!nickname" @click="createAgent">创建</button>
        </div>
      </div>
    </div>

    <!-- Transfer Modal -->
    <div v-if="showTransfer" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" @click.self="showTransfer = false">
      <div class="card p-6 w-full max-w-sm mx-4">
        <h3 class="text-base font-semibold mb-2">划转积分</h3>
        <p class="text-sm text-[var(--color-text-muted)] mb-4">向 <strong>{{ transferTarget?.nickname }}</strong> 划转</p>
        <div class="space-y-3">
          <div class="flex justify-between text-sm">
            <span class="text-[var(--color-text-muted)]">我的可用</span>
            <span class="font-mono font-semibold">{{ walletInfo.available?.toLocaleString() }}</span>
          </div>
          <div class="flex justify-between text-sm">
            <span class="text-[var(--color-text-muted)]">代理商当前</span>
            <span class="font-mono">{{ transferTarget?.balance?.toLocaleString() }}</span>
          </div>
          <div>
            <input v-model.number="transferAmount" type="number" min="1"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm font-mono"
              placeholder="输入积分数量" />
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="btn btn-outline" @click="showTransfer = false">取消</button>
          <button class="btn btn-primary" :disabled="transferLoading || !transferAmount || transferAmount <= 0 || transferAmount > walletInfo.available"
            @click="confirmTransfer">{{ transferLoading ? '划转中...' : '确认划转' }}</button>
        </div>
      </div>
    </div>

    <!-- Created toast -->
    <div v-if="generated" class="fixed bottom-6 right-6 card p-4 max-w-sm z-50 shadow-xl border-[var(--color-accent)]">
      <h4 class="text-sm font-semibold mb-2">{{ generated.nickname }} 创建成功</h4>
      <div class="text-xs space-y-1">
        <div class="flex justify-between items-center">
          <span>账号:</span>
          <div class="flex items-center gap-1">
            <code class="text-[var(--color-accent)] font-mono">{{ generated.username }}</code>
            <button @click="copy(generated.username)"><Copy class="w-3 h-3" /></button>
          </div>
        </div>
        <div class="flex justify-between items-center">
          <span>密码:</span>
          <div class="flex items-center gap-1">
            <code class="text-[var(--color-success)] font-mono">{{ generated.password }}</code>
            <button @click="copy(generated.password)"><Copy class="w-3 h-3" /></button>
          </div>
        </div>
      </div>
      <button class="btn btn-outline btn-sm mt-3 w-full" @click="generated=null">关闭</button>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="fixed bottom-6 left-1/2 -translate-x-1/2 card p-3 z-50 shadow-xl"
      :class="toast.includes('失败') ? 'border-red-500/50' : 'border-[var(--color-success)]/50'">
      <p class="text-sm whitespace-nowrap">{{ toast }}</p>
    </div>
  </div>
</template>
