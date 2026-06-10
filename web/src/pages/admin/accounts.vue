<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '@/utils/api'
import Badge from '@/components/ui/Badge.vue'
import { Copy, Check, Eye, EyeOff, KeyRound, UserPlus, Plus, Edit3 } from 'lucide-vue-next'

const suppliers = ref<any[]>([])
const agents = ref<any[]>([])
const apiPayers = ref<any[]>([])
const loading = ref(true)
const activeTab = ref<'suppliers' | 'agents' | 'api-payers'>('suppliers')
const selectedSupplierId = ref<number>(0)

// Create supplier form
const showCreateSupplier = ref(false)
const supForm = ref({ nickname: '', username: '', password: '', auto_generate: true })

// Create agent form
const showCreateAgent = ref(false)
const agentForm = ref({ supplier_id: 0, nickname: '', username: '', password: '' })
const creatingAgent = ref(false)

// Create API payer form
const showCreatePayer = ref(false)
const payerForm = ref({ supplier_id: 0, nickname: '' })
const creatingPayer = ref(false)

// Edit dialog
const editItem = ref<any>(null)
const editType = ref<string>('')
const editNickname = ref('')
const showEdit = ref(false)

// Reset password in edit dialog
const showResetPwd = ref(false)
const resetPwdValue = ref('')
const resetPwdUserType = ref<string>('')
const resetPwdUserId = ref<number>(0)

// Copy feedback per row
const copiedId = ref<number | null>(null)

// Toast
const toastMsg = ref('')
const toastType = ref<'success' | 'error'>('success')
function showSuccess(msg: string) { toastMsg.value = msg; toastType.value = 'success'; clearToast() }
function showError(msg: string) { toastMsg.value = msg; toastType.value = 'error'; clearToast() }
function clearToast() { setTimeout(() => toastMsg.value = '', 3000) }

// ── One-time credential display (copy before close) ──
const credModal = ref({ show: false, title: '', fields: [] as {label:string, value:string}[], copied: false })
function showCreds(title: string, fields: {label:string, value:string}[]) {
  credModal.value = { show: true, title, fields, copied: false }
}
function credCopied() { credModal.value.copied = true }
function closeCreds() { credModal.value = { show: false, title: '', fields: [], copied: false } }

// ── Separate API payer credential modal ──
const payerCredModal = ref({ show: false, api_key: '', api_secret: '', copied: false })
function showPayerCreds(api_key: string, api_secret: string) {
  payerCredModal.value = { show: true, api_key, api_secret, copied: false }
}
function payerCredCopied() { payerCredModal.value.copied = true }
function closePayerCreds() { payerCredModal.value = { show: false, api_key: '', api_secret: '', copied: false } }

// Mask state for each user (keyed by row id)
const maskedMap = ref<Record<number, boolean>>({})

const tabViews = [
  { k: 'suppliers', l: '供应商' },
  { k: 'agents', l: '代理商' },
  { k: 'api-payers', l: 'API支付商' },
] as const

// Filter agents/payers by selected supplier
const filteredAgents = computed(() =>
  !selectedSupplierId.value ? agents.value : agents.value.filter(a => a.supplier_id === selectedSupplierId.value)
)
const filteredPayers = computed(() =>
  !selectedSupplierId.value ? apiPayers.value : apiPayers.value.filter(p => p.supplier_id === selectedSupplierId.value)
)

function genRandom() {
  supForm.value.username = 'sup_' + Math.random().toString(36).slice(2, 10)
  supForm.value.password = Math.random().toString(36).slice(2, 18)
}

function openAddAgent(supplier: any) {
  agentForm.value = { supplier_id: supplier.id, nickname: '', username: '', password: '' }
  showCreateAgent.value = true
}

function openAddPayer(supplier: any) {
  payerForm.value = { supplier_id: supplier.id, nickname: '' }
  showCreatePayer.value = true
}

function genAgentRandom() {
  agentForm.value.username = 'agent_' + Math.random().toString(36).slice(2, 10)
  agentForm.value.password = Math.random().toString(36).slice(2, 14)
}

async function loadData() {
  loading.value = true
  try {
    const [sr, ar, pr] = await Promise.all([
      api.get<{code: number; data: any[]}>('/api/admin/suppliers'),
      api.get<{code: number; data: any[]}>('/api/admin/agents'),
      api.get<{code: number; data: any[]}>('/api/admin/api-payers'),
    ])
    suppliers.value = (sr.data || []).sort((a, b) => b.id - a.id)
    agents.value = (ar.data || []).sort((a, b) => b.id - a.id)
    apiPayers.value = (pr.data || []).sort((a, b) => b.id - a.id)
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

async function createSupplier() {
  if (!supForm.value.nickname) supForm.value.nickname = '供应商_' + Math.random().toString(36).slice(2, 8)
  const r = await api.post('/api/admin/suppliers', supForm.value)
  const d = r.data
  showCreateSupplier.value = false
  supForm.value = { nickname: '', username: '', password: '', auto_generate: true }
  await loadData()
  showCreds('供应商创建成功', [
    { label: '登录账号', value: d.username },
    { label: '登录密码', value: d.password },
  ])
}

async function createAgent() {
  creatingAgent.value = true
  try {
    if (!agentForm.value.nickname) agentForm.value.nickname = '代理商_' + Math.random().toString(36).slice(2, 8)
    const payload: any = {
      supplier_id: agentForm.value.supplier_id,
      nickname: agentForm.value.nickname,
      username: agentForm.value.username,
      password: agentForm.value.password,
    }
    const r = await api.post('/api/admin/agents', payload)
    const d = r.data || {}
    const savedUser = d.username || agentForm.value.username
    const savedPwd = d.password || agentForm.value.password
    showCreateAgent.value = false
    agentForm.value = { supplier_id: 0, nickname: '', username: '', password: '' }
    await loadData()
    showCreds('代理商创建成功', [
      { label: '登录账号', value: savedUser },
      { label: '登录密码', value: savedPwd },
    ])
  } catch (e: any) { console.error(e) }
  finally { creatingAgent.value = false }
}

async function createPayer() {
  try {
    creatingPayer.value = true
    if (!payerForm.value.nickname) payerForm.value.nickname = '支付商_' + Math.random().toString(36).slice(2, 8)
    const r = await api.post('/api/admin/api-payers', payerForm.value)
    const d = r.data || {}
    showCreatePayer.value = false
    payerForm.value = { supplier_id: 0, nickname: '' }
    await loadData()
    showPayerCreds(d.api_key || '', d.api_secret || '')
  } catch (e: any) { showError(`创建失败: ${e.message || e}`) }
  finally { creatingPayer.value = false }
}

function openEdit(item: any, type: string) {
  editItem.value = item
  editType.value = type
  editNickname.value = item.nickname || item.name
  showEdit.value = true
  showResetPwd.value = false
  resetPwdValue.value = ''
}

async function saveEdit() {
  const item = editItem.value
  const type = editType.value
  try {
    if (type === 'supplier') {
      await api.put(`/api/admin/suppliers/${item.id}`, { nickname: editNickname.value, status: item.status })
    } else if (type === 'agent') {
      await api.put(`/api/admin/agents/${item.id}`, { nickname: editNickname.value, status: item.status })
    } else {
      await api.put(`/api/admin/api-payers/${item.id}`, { nickname: editNickname.value, status: item.status })
    }
    // If password was entered, reset it
    let newPwd = ''
    if (resetPwdValue.value) {
      const pw = resetPwdValue.value
      const r = await api.put('/api/admin/users/reset-password', {
        user_id: item.id,
        new_password: pw,
      })
      newPwd = (r.data && r.data.new_password) || pw
    }
    showEdit.value = false
    resetPwdValue.value = ''
    await loadData()
    if (newPwd) {
      showCreds('密码已修改', [
        { label: '新密码', value: newPwd },
      ])
    } else {
      showSuccess('保存成功')
    }
  } catch (e: any) {
    showError(`保存失败: ${e.message || e}`)
  }
}

async function toggleStatus(item: any, type: string) {
  const newStatus = item.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
  try {
    if (type === 'supplier') {
      await api.put(`/api/admin/suppliers/${item.id}`, { nickname: item.nickname, status: newStatus })
    } else if (type === 'agent') {
      await api.put(`/api/admin/agents/${item.id}`, { nickname: item.nickname, status: newStatus })
    } else {
      await api.put(`/api/admin/api-payers/${item.id}`, { nickname: item.nickname, status: newStatus })
    }
    await loadData()
  } catch (e) { console.error(e) }
}

function openResetPwd(item: any, type: string) {
  showResetPwd.value = true
  resetPwdValue.value = ''
  // Map user_id based on entity type — assume the item has a user_id field
  // If not, we'll use item.id and the backend should map accordingly
  resetPwdUserType.value = type
  resetPwdUserId.value = item.id
}

async function doResetPassword() {
  if (!resetPwdValue.value) return
  try {
    await api.put('/api/admin/users/reset-password', {
      user_id: resetPwdUserId.value,
      new_password: resetPwdValue.value,
    })
    resetPwdValue.value = ''
    showResetPwd.value = false
    await loadData()
  } catch (e) { console.error(e) }
}

// ── Clipboard copy with fallback ──

async function copyText(text: string, id: number) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // Fallback for non-HTTPS (WSL dev server)
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    } catch (e2) {
      console.error('Copy failed:', e2)
      return
    }
  }
  copiedId.value = id
  setTimeout(() => { copiedId.value = null }, 2000)
}

function getPwd(item: any): string {
  return item.raw_password || item.password || ''
}

function getPasswordDisplay(item: any): string {
  return item.username ? '******' : '—'
}

function getMasked(id: number): boolean {
  return maskedMap.value[id] !== false // default masked
}

function toggleMask(id: number) {
  maskedMap.value[id] = !getMasked(id)
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold text-[var(--color-text)]">账号管理</h2>
        <p class="mt-1 text-sm text-[var(--color-text-muted)]">管理供应商 → 代理商 → API支付商</p>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 border-b border-[var(--color-border)]">
      <button
        v-for="t in tabViews"
        :key="t.k"
        @click="activeTab = t.k"
        :class="[
          'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors',
          activeTab === t.k
            ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
            : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
        ]"
      >
        {{ t.l }}
      </button>
    </div>

    <!-- ==================== SUPPLIERS ==================== -->
    <div v-if="activeTab === 'suppliers'">
      <div class="flex justify-between mb-3">
        <span class="text-xs text-[var(--color-text-muted)] self-center">共 {{ suppliers.length }} 个供应商</span>
        <button class="btn btn-primary btn-sm" @click="showCreateSupplier = true">+ 创建供应商</button>
      </div>
      <div class="card p-0 overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
              <th class="text-left p-3 font-semibold text-[var(--color-text-muted)] text-xs">ID</th>
              <th class="text-left p-3 font-semibold text-[var(--color-text-muted)] text-xs">昵称</th>
              <th class="text-left p-3 font-semibold text-[var(--color-text-muted)] text-xs">用户名</th>
              <th class="text-center p-3 font-semibold text-[var(--color-text-muted)] text-xs">代理商数</th>
              <th class="text-center p-3 font-semibold text-[var(--color-text-muted)] text-xs">API支付商数</th>
              <th class="text-left p-3 font-semibold text-[var(--color-text-muted)] text-xs">状态</th>
              <th class="text-left p-3 font-semibold text-[var(--color-text-muted)] text-xs">创建时间</th>
              <th class="text-right p-3 font-semibold text-[var(--color-text-muted)] text-xs">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in suppliers"
              :key="s.id"
              class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30 transition-colors"
            >
              <td class="p-3 font-mono text-xs">{{ s.id }}</td>
              <td class="p-3 font-medium">{{ s.nickname }}</td>
              <td class="p-3">
                <div class="flex items-center gap-1.5">
                  <span class="font-mono text-xs">{{ s.username || '—' }}</span>
                  <button v-if="s.username" class="p-0.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors" title="复制用户名" @click="copyText(s.username, s.id)">
                    <Copy v-if="copiedId !== s.id" class="w-3.5 h-3.5" />
                    <Check v-else class="w-3.5 h-3.5 text-brand-success" />
                  </button>
                </div>
              </td>
              <td class="p-3 text-center">{{ s.agent_count }}</td>
              <td class="p-3 text-center">{{ s.api_payer_count }}</td>
              <td class="p-3">
                <button
                  @click="toggleStatus(s, 'supplier')"
                  :class="[
                    'relative inline-flex h-5 w-9 items-center rounded-full transition-colors duration-200',
                    s.status === 'ACTIVE' ? 'bg-brand-success' : 'bg-[var(--color-border)]',
                  ]"
                >
                  <span
                    :class="[
                      'inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform duration-200 shadow-sm',
                      s.status === 'ACTIVE' ? 'translate-x-[18px]' : 'translate-x-[2px]',
                    ]"
                  />
                </button>
              </td>
              <td class="p-3 text-xs text-[var(--color-text-muted)]">{{ s.created_at?.slice(0, 10) }}</td>
              <td class="p-3 text-right space-x-0.5 whitespace-nowrap">
                <button class="p-1.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-bg)] transition-colors" title="添加代理商" @click.stop="openAddAgent(s)">
                  <UserPlus class="w-4 h-4" />
                </button>
                <button class="p-1.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-bg)] transition-colors" title="添加支付商" @click.stop="openAddPayer(s)">
                  <Plus class="w-4 h-4" />
                </button>
                <button class="p-1.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-bg)] transition-colors" title="编辑" @click="openEdit(s, 'supplier')">
                  <Edit3 class="w-4 h-4" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ==================== AGENTS ==================== -->
    <div v-if="activeTab === 'agents'">
      <div class="flex justify-between mb-3 flex-wrap gap-2">
        <div class="flex items-center gap-2">
          <span class="text-xs text-[var(--color-text-muted)]">所属供应商:</span>
          <select
            v-model="selectedSupplierId"
            class="px-2 py-1 rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-xs"
          >
            <option :value="0">全部</option>
            <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.nickname }}</option>
          </select>
          <span class="text-xs text-[var(--color-text-muted)]">共 {{ filteredAgents.length }} 个代理商</span>
        </div>
        <button
          class="btn btn-primary btn-sm"
          @click="agentForm.supplier_id = 0; agentForm.nickname = ''; agentForm.username = ''; agentForm.password = ''; showCreateAgent = true"
        >
          + 创建代理商
        </button>
      </div>
      <div class="card p-0 overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
              <th class="text-left p-3 font-semibold text-xs text-[var(--color-text-muted)]">ID</th>
              <th class="text-left p-3 font-semibold text-xs text-[var(--color-text-muted)]">昵称</th>
              <th class="text-left p-3 font-semibold text-xs text-[var(--color-text-muted)]">用户名</th>
              <th class="text-left p-3 font-semibold text-xs text-[var(--color-text-muted)]">所属供应商</th>
              <th class="text-right p-3 font-semibold text-xs text-[var(--color-text-muted)]">积分余额</th>
              <th class="text-left p-3 font-semibold text-xs text-[var(--color-text-muted)]">状态</th>
              <th class="text-right p-3 font-semibold text-xs text-[var(--color-text-muted)]">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="a in filteredAgents"
              :key="a.id"
              class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30 transition-colors"
            >
              <td class="p-3 font-mono text-xs">{{ a.id }}</td>
              <td class="p-3 font-medium">{{ a.nickname }}</td>
              <td class="p-3">
                <div class="flex items-center gap-1.5">
                  <span class="font-mono text-xs">{{ a.username || '—' }}</span>
                  <button v-if="a.username" class="p-0.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors" title="复制用户名" @click="copyText(a.username, a.id)">
                    <Copy v-if="copiedId !== a.id" class="w-3.5 h-3.5" />
                    <Check v-else class="w-3.5 h-3.5 text-brand-success" />
                  </button>
                </div>
              </td>
              <td class="p-3 text-xs text-[var(--color-text-muted)]">{{ a.supplier_name }}</td>
              <td class="p-3 text-right font-mono text-xs">{{ a.balance?.toLocaleString() }}</td>
              <td class="p-3">
                <button
                  @click="toggleStatus(a, 'agent')"
                  :class="[
                    'relative inline-flex h-5 w-9 items-center rounded-full transition-colors duration-200',
                    a.status === 'ACTIVE' ? 'bg-brand-success' : 'bg-[var(--color-border)]',
                  ]"
                >
                  <span
                    :class="[
                      'inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform duration-200 shadow-sm',
                      a.status === 'ACTIVE' ? 'translate-x-[18px]' : 'translate-x-[2px]',
                    ]"
                  />
                </button>
              </td>
              <td class="p-3 text-right space-x-0.5">
                <button class="p-1.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-bg)] transition-colors" title="编辑" @click="openEdit(a, 'agent')">
                  <Edit3 class="w-4 h-4" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ==================== API PAYERS ==================== -->
    <div v-if="activeTab === 'api-payers'">
      <div class="flex justify-between mb-3 flex-wrap gap-2">
        <div class="flex items-center gap-2">
          <span class="text-xs text-[var(--color-text-muted)]">所属供应商:</span>
          <select
            v-model="selectedSupplierId"
            class="px-2 py-1 rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-xs"
          >
            <option :value="0">全部</option>
            <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.nickname }}</option>
          </select>
          <span class="text-xs text-[var(--color-text-muted)]">共 {{ filteredPayers.length }} 个API支付商</span>
        </div>
        <button
          class="btn btn-primary btn-sm"
          @click="payerForm.supplier_id = 0; payerForm.nickname = ''; showCreatePayer = true"
        >
          + 创建API支付商
        </button>
      </div>
      <div class="card p-0 overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
              <th class="text-left p-3 font-semibold text-xs text-[var(--color-text-muted)]">ID</th>
              <th class="text-left p-3 font-semibold text-xs text-[var(--color-text-muted)]">昵称</th>
              <th class="text-left p-3 font-semibold text-xs text-[var(--color-text-muted)]">供应商</th>
              <th class="text-left p-3 font-semibold text-xs text-[var(--color-text-muted)]">API Key</th>
              <th class="text-left p-3 font-semibold text-xs text-[var(--color-text-muted)]">API Secret</th>
              <th class="text-left p-3 font-semibold text-xs text-[var(--color-text-muted)]">回调地址</th>
              <th class="text-left p-3 font-semibold text-xs text-[var(--color-text-muted)]">状态</th>
              <th class="text-right p-3 font-semibold text-xs text-[var(--color-text-muted)]">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="p in filteredPayers"
              :key="p.id"
              class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30 transition-colors"
            >
              <td class="p-3 font-mono text-xs">{{ p.id }}</td>
              <td class="p-3 font-medium">{{ p.nickname }}</td>
              <td class="p-3 text-xs text-[var(--color-text-muted)]">{{ p.supplier_name }}</td>
              <td class="p-3">
                <div class="flex items-center gap-1.5">
                  <code class="text-xs font-mono bg-[var(--color-bg)] px-1.5 py-0.5 rounded break-all max-w-[160px] truncate">{{ p.api_key }}</code>
                  <button class="p-0.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors" title="复制 API Key" @click="copyText(p.api_key, p.id)">
                    <Copy v-if="copiedId !== p.id" class="w-3.5 h-3.5" />
                    <Check v-else class="w-3.5 h-3.5 text-brand-success" />
                  </button>
                </div>
              </td>
              <td class="p-3">
                <code class="text-xs font-mono text-[var(--color-text-muted)] break-all max-w-[160px] truncate block">{{ p.api_secret }}</code>
              </td>
              <td class="p-3 text-xs text-[var(--color-text-muted)] truncate max-w-[160px]">{{ p.callback_url || '—' }}</td>
              <td class="p-3">
                <button
                  @click="toggleStatus(p, 'payer')"
                  :class="[
                    'relative inline-flex h-5 w-9 items-center rounded-full transition-colors duration-200',
                    p.status === 'ACTIVE' ? 'bg-brand-success' : 'bg-[var(--color-border)]',
                  ]"
                >
                  <span
                    :class="[
                      'inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform duration-200 shadow-sm',
                      p.status === 'ACTIVE' ? 'translate-x-[18px]' : 'translate-x-[2px]',
                    ]"
                  />
                </button>
              </td>
              <td class="p-3 text-right space-x-0.5">
                <button class="p-1.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-bg)] transition-colors" title="编辑" @click="openEdit(p, 'payer')">
                  <Edit3 class="w-4 h-4" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ══════ One-time credential modal ══════ -->
    <div
      v-if="credModal.show"
      class="fixed inset-0 bg-black/60 z-[999] flex items-center justify-center"
      @click.self="closeCreds"
    >
      <div class="card p-6 w-full max-w-sm mx-4 animate-slide-up shadow-2xl border border-[var(--color-accent)]/20">
        <div class="text-center mb-5">
          <div class="w-12 h-12 rounded-full bg-brand-success/10 flex items-center justify-center mx-auto mb-3">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent-success, #22c55e)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
          <h3 class="text-base font-semibold text-[var(--color-text)]">{{ credModal.title }}</h3>
          <p class="text-xs text-[var(--color-text-muted)] mt-1">请立即复制并妥善保存，关闭后将无法再次查看</p>
        </div>

        <div class="space-y-3 mb-5">
          <div v-for="(f, i) in credModal.fields" :key="i">
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">{{ f.label }}</label>
            <div class="flex items-center gap-2 p-2.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
              <code class="flex-1 font-mono text-sm break-all select-all">{{ f.value }}</code>
              <button
                class="p-1.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-bg-secondary)] transition-colors shrink-0"
                title="复制"
                @click="copyText(f.value, -i-1); credCopied()"
              >
                <svg v-if="copiedId !== -i-1" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-success, #22c55e)" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <button
          class="btn w-full justify-center"
          :class="credModal.copied ? 'btn-primary' : 'btn-outline text-[var(--color-text-muted)]'"
          @click="closeCreds"
        >
          {{ credModal.copied ? '已复制，关闭' : '我已知晓，关闭' }}
        </button>
        <p v-if="!credModal.copied" class="text-[10px] text-[var(--color-text-muted)] text-center mt-2">关闭后将无法再次查看，请确认已保存</p>
      </div>
    </div>

    <!-- ══════ One-time credential modal (API payer) ══════ -->
    <div
      v-if="payerCredModal.show"
      class="fixed inset-0 bg-black/60 z-[999] flex items-center justify-center"
      @click.self="closePayerCreds"
    >
      <div class="card p-6 w-full max-w-sm mx-4 animate-slide-up shadow-2xl">
        <div class="text-center mb-5">
          <div class="w-12 h-12 rounded-full bg-brand-success/10 flex items-center justify-center mx-auto mb-3">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent-success, #22c55e)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
          </div>
          <h3 class="text-base font-semibold text-[var(--color-text)]">API支付商创建成功</h3>
          <p class="text-xs text-[var(--color-text-muted)] mt-1">请立即复制并妥善保存，关闭后将无法再次查看</p>
        </div>
        <div class="space-y-3 mb-5">
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">API Key</label>
            <div class="flex items-center gap-2 p-2.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
              <code class="flex-1 font-mono text-sm break-all select-all">{{ payerCredModal.api_key }}</code>
              <button class="p-1.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)] shrink-0" title="复制" @click="copyText(payerCredModal.api_key, -99); payerCredCopied()">
                <svg v-if="copiedId !== -99" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
              </button>
            </div>
          </div>
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">API Secret</label>
            <div class="flex items-center gap-2 p-2.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
              <code class="flex-1 font-mono text-sm break-all select-all">{{ payerCredModal.api_secret }}</code>
              <button class="p-1.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)] shrink-0" title="复制" @click="copyText(payerCredModal.api_secret, -98); payerCredCopied()">
                <svg v-if="copiedId !== -98" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
              </button>
            </div>
          </div>
        </div>
        <button class="btn w-full justify-center" :class="payerCredModal.copied ? 'btn-primary' : 'btn-outline text-[var(--color-text-muted)]'" @click="closePayerCreds">
          {{ payerCredModal.copied ? '已复制，关闭' : '我已知晓，关闭' }}
        </button>
        <p v-if="!payerCredModal.copied" class="text-[10px] text-[var(--color-text-muted)] text-center mt-2">关闭后将无法再次查看，请确认已保存</p>
      </div>
    </div>
    <div
      v-if="toastMsg"
      :class="['fixed bottom-6 right-6 card p-3 max-w-sm z-50 shadow-xl animate-slide-up border',
        toastType === 'success' ? 'border-green-500/50' : 'border-red-500/50']"
    >
      <p class="text-sm" :class="toastType === 'success' ? 'text-green-600' : 'text-red-600'">{{ toastMsg }}</p>
    </div>

    <!-- ==================== CREATE SUPPLIER MODAL ==================== -->
    <div
      v-if="showCreateSupplier"
      class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center"
      @click.self="showCreateSupplier = false"
    >
      <div class="card p-6 w-full max-w-sm mx-4 animate-slide-up">
        <h3 class="text-base font-semibold text-[var(--color-text)] mb-4">创建供应商</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">昵称</label>
            <input
              v-model="supForm.nickname"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm"
              placeholder="供应商昵称"
            />
          </div>
          <div class="flex gap-2">
            <div class="flex-1">
              <label class="block text-xs text-[var(--color-text-muted)] mb-1">登录用户名</label>
              <input
                v-model="supForm.username"
                class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm font-mono"
                placeholder="用户名"
              />
            </div>
            <div class="flex-1">
              <label class="block text-xs text-[var(--color-text-muted)] mb-1">登录密码</label>
              <input
                v-model="supForm.password"
                class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm font-mono"
                placeholder="密码"
              />
            </div>
          </div>
          <button class="btn btn-outline btn-sm w-full justify-center" @click="genRandom">🎲 随机生成账号密码</button>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="btn btn-outline" @click="showCreateSupplier = false">取消</button>
          <button class="btn btn-primary" @click="createSupplier">创建</button>
        </div>
      </div>
    </div>

    <!-- ==================== CREATE AGENT MODAL ==================== -->
    <div
      v-if="showCreateAgent"
      class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center"
      @click.self="showCreateAgent = false"
    >
      <div class="card p-6 w-full max-w-sm mx-4 animate-slide-up">
        <h3 class="text-base font-semibold text-[var(--color-text)] mb-4">创建代理商</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">所属供应商</label>
            <select
              v-model="agentForm.supplier_id"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm"
              :disabled="agentForm.supplier_id > 0"
            >
              <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.nickname }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">昵称</label>
            <input v-model="agentForm.nickname" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm" placeholder="代理商昵称" />
          </div>
          <div class="flex gap-2">
            <div class="flex-1">
              <label class="block text-xs text-[var(--color-text-muted)] mb-1">登录用户名</label>
              <input v-model="agentForm.username" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm font-mono" placeholder="输入或点击随机生成" />
            </div>
            <div class="flex-1">
              <label class="block text-xs text-[var(--color-text-muted)] mb-1">登录密码</label>
              <input v-model="agentForm.password" class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm font-mono" placeholder="输入或点击随机生成" />
            </div>
          </div>
          <button class="btn btn-outline btn-sm w-full justify-center" @click="genAgentRandom">🎲 随机生成账号密码</button>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="btn btn-outline" @click="showCreateAgent = false">取消</button>
          <button class="btn btn-primary" :disabled="creatingAgent || !agentForm.nickname" @click="createAgent">
            {{ creatingAgent ? '创建中...' : '创建' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ==================== CREATE API PAYER MODAL ==================== -->
    <div
      v-if="showCreatePayer"
      class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center"
      @click.self="showCreatePayer = false"
    >
      <div class="card p-6 w-full max-w-sm mx-4 animate-slide-up">
        <h3 class="text-base font-semibold text-[var(--color-text)] mb-4">创建API支付商</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">所属供应商</label>
            <select
              v-model="payerForm.supplier_id"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm"
              :disabled="payerForm.supplier_id > 0"
            >
              <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.nickname }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">昵称</label>
            <input
              v-model="payerForm.nickname"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm"
              placeholder="API支付商昵称"
            />
          </div>
          <div class="bg-[var(--color-bg)] p-2 rounded text-xs text-[var(--color-text-muted)]">
            API Key 和 Secret 将在创建后自动生成
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="btn btn-outline" @click="showCreatePayer = false">取消</button>
          <button class="btn btn-primary" @click="createPayer">创建</button>
        </div>
      </div>
    </div>

    <!-- ==================== EDIT MODAL ==================== -->
    <div
      v-if="showEdit"
      class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center"
      @click.self="showEdit = false"
    >
      <div class="card p-6 w-full max-w-sm mx-4 animate-slide-up">
        <h3 class="text-base font-semibold text-[var(--color-text)] mb-4">
          编辑 {{ { supplier: '供应商', agent: '代理商', payer: 'API支付商' }[editType] || '' }}
        </h3>

        <!-- Edit nickname -->
        <div class="mb-4">
          <label class="block text-xs text-[var(--color-text-muted)] mb-1">昵称</label>
          <input
            v-model="editNickname"
            class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm"
            placeholder="昵称"
          />
        </div>

        <!-- Reset password section -->
        <div v-if="editType !== 'payer'" class="border-t border-[var(--color-border)] pt-4">
          <label class="block text-xs text-[var(--color-text-muted)] mb-1.5">修改密码（留空不修改）</label>
          <div class="flex gap-2">
            <input
              v-model="resetPwdValue"
              type="text"
              class="flex-1 px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm font-mono"
              placeholder="输入新密码或点击生成"
            />
            <button class="btn btn-outline btn-sm whitespace-nowrap" @click="resetPwdValue = Math.random().toString(36).slice(2, 14)">🎲 生成</button>
          </div>
        </div>

        <div class="flex justify-end gap-2 mt-4 pt-3 border-t border-[var(--color-border)]">
          <button class="btn btn-outline" @click="showEdit = false">取消</button>
          <button class="btn btn-primary" @click="saveEdit">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Additional toggle styling is handled inline via Tailwind classes */
</style>
