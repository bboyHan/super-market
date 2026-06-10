<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import api from '@/utils/api'
import Badge from '@/components/ui/Badge.vue'
import { Plus, Copy, RotateCw, Eye, EyeOff, Pencil, RefreshCw } from 'lucide-vue-next'

// ── Suppliers ──
const suppliers = ref<any[]>([])
const loadingSuppliers = ref(true)
const selectedSupplier = ref<any>(null)

// ── Agents ──
const agents = ref<any[]>([])
const loadingAgents = ref(false)
const showCreateAgent = ref(false)
const showEditAgent = ref(false)
const editAgentTarget = ref<any>(null)
const newAgentNickname = ref('')
const revealedPw = ref<Record<number, boolean>>({})

// ── API Payers ──
const payers = ref<any[]>([])
const loadingPayers = ref(false)
const showCreatePayer = ref(false)
const showEditPayer = ref(false)
const editPayerTarget = ref<any>(null)
const newPayerNickname = ref('')
const showKey = ref<Record<number, boolean>>({})
const showSecret = ref<Record<number, boolean>>({})

// ── Tab ──
const activeTab = ref<'agents' | 'api-payers'>('agents')

// ── Toast ──
const toast = ref('')

function showToast(msg: string, isError = false) {
  toast.value = msg
  setTimeout(() => toast.value = '', 3000)
}

function copy(text: string) {
  navigator.clipboard.writeText(text)
  showToast('已复制')
}

function maskSecret(val: string | null | undefined): string {
  if (!val) return '••••••••'
  if (val.length <= 8) return '••••••••'
  return val.slice(0, 4) + '••••' + val.slice(-4)
}

function maskKey(val: string | null | undefined): string {
  if (!val) return '••••••••'
  if (val.length <= 8) return '••••••••'
  return val.slice(0, 8) + '••••'
}

function maskUsername(val: string | null | undefined): string {
  if (!val) return '—'
  if (val.length <= 4) return val.slice(0, 1) + '***'
  return val.slice(0, 2) + '***' + val.slice(-2)
}

// ── Load suppliers ──
async function loadSuppliers() {
  loadingSuppliers.value = true
  try {
    const r = await api.get<{ code: number; data: any[] }>('/api/admin/suppliers')
    suppliers.value = r.data
  } catch (e: any) {
    showToast('加载供应商列表失败: ' + (e.message || e), true)
  } finally {
    loadingSuppliers.value = false
  }
}

// ── Select supplier ──
async function selectSupplier(s: any) {
  selectedSupplier.value = s
  activeTab.value = 'agents'
  await loadAgents()
}

function toggleSupplierRow(s: any) {
  if (selectedSupplier.value?.id === s.id) {
    selectedSupplier.value = null
  } else {
    selectSupplier(s)
  }
}

// ── Load agents for selected supplier ──
async function loadAgents() {
  if (!selectedSupplier.value) return
  loadingAgents.value = true
  try {
    const r = await api.get<{ code: number; data: any[] }>(
      `/api/admin/suppliers/${selectedSupplier.value.id}/agents`
    )
    agents.value = r.data
  } catch (e: any) {
    showToast('加载代理商失败: ' + (e.message || e), true)
  } finally {
    loadingAgents.value = false
  }
}

// ── Load API payers for selected supplier ──
async function loadPayers() {
  if (!selectedSupplier.value) return
  loadingPayers.value = true
  try {
    const r = await api.get<{ code: number; data: any[] }>(
      `/api/admin/suppliers/${selectedSupplier.value.id}/api-payers`
    )
    payers.value = r.data
  } catch (e: any) {
    showToast('加载API支付商失败: ' + (e.message || e), true)
  } finally {
    loadingPayers.value = false
  }
}

// ── Tab switch ──
watch(activeTab, async (tab) => {
  if (tab === 'agents') {
    await loadAgents()
  } else {
    await loadPayers()
  }
})

// ── Create agent ──
async function createAgent() {
  if (!newAgentNickname.value || !selectedSupplier.value) return
  try {
    await api.post('/api/admin/agents', {
      supplier_id: selectedSupplier.value.id,
      nickname: newAgentNickname.value,
    })
    showCreateAgent.value = false
    newAgentNickname.value = ''
    showToast('代理商创建成功')
    await loadAgents()
  } catch (e: any) {
    showToast('创建失败: ' + (e.message || e), true)
  }
}

// ── Edit agent ──
async function saveEditAgent() {
  if (!editAgentTarget.value) return
  try {
    await api.put(`/api/admin/agents/${editAgentTarget.value.id}`, {
      nickname: editAgentTarget.value.nickname,
    })
    showEditAgent.value = false
    editAgentTarget.value = null
    showToast('代理商已更新')
    await loadAgents()
  } catch (e: any) {
    showToast('更新失败: ' + (e.message || e), true)
  }
}

function openEditAgent(a: any) {
  editAgentTarget.value = { ...a }
  showEditAgent.value = true
}

// ── Reset agent password ──
async function resetAgentPassword(a: any) {
  try {
    const r = await api.post<{ code: number; data: { new_password: string } }>(
      `/api/admin/agents/${a.id}/reset-password`, {}
    )
    revealedPw.value[a.id] = true
    a._newPassword = r.data.new_password
    showToast('新密码: ' + r.data.new_password)
    setTimeout(() => {
      a._newPassword = undefined
      revealedPw.value[a.id] = false
    }, 30000)
  } catch (e: any) {
    showToast('重置失败: ' + (e.message || e), true)
  }
}

// ── Toggle agent status ──
async function toggleAgentStatus(a: any) {
  const ns = a.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
  try {
    await api.put(`/api/admin/agents/${a.id}?status=${ns}`, {})
    await loadAgents()
  } catch (e: any) {
    showToast('操作失败: ' + (e.message || e), true)
  }
}

// ── Create API payer ──
async function createPayer() {
  if (!newPayerNickname.value || !selectedSupplier.value) return
  try {
    await api.post('/api/admin/api-payers', {
      supplier_id: selectedSupplier.value.id,
      nickname: newPayerNickname.value,
    })
    showCreatePayer.value = false
    newPayerNickname.value = ''
    showToast('API支付商创建成功')
    await loadPayers()
  } catch (e: any) {
    showToast('创建失败: ' + (e.message || e), true)
  }
}

// ── Edit API payer ──
async function saveEditPayer() {
  if (!editPayerTarget.value) return
  try {
    await api.put(`/api/admin/api-payers/${editPayerTarget.value.id}`, {
      nickname: editPayerTarget.value.nickname,
      callback_url: editPayerTarget.value.callback_url,
    })
    showEditPayer.value = false
    editPayerTarget.value = null
    showToast('API支付商已更新')
    await loadPayers()
  } catch (e: any) {
    showToast('更新失败: ' + (e.message || e), true)
  }
}

function openEditPayer(p: any) {
  editPayerTarget.value = { ...p }
  showEditPayer.value = true
}

// ── Reset API payer secret ──
async function resetPayerSecret(p: any) {
  try {
    const r = await api.post<{ code: number; data: { api_secret: string } }>(
      `/api/admin/api-payers/${p.id}/reset-secret`, {}
    )
    showSecret.value[p.id] = true
    p._newSecret = r.data.api_secret
    showToast('新Secret: ' + r.data.api_secret)
    setTimeout(() => {
      p._newSecret = undefined
      showSecret.value[p.id] = false
    }, 30000)
  } catch (e: any) {
    showToast('重置失败: ' + (e.message || e), true)
  }
}

// ── Toggle API payer status ──
async function togglePayerStatus(p: any) {
  const ns = p.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
  try {
    await api.put(`/api/admin/api-payers/${p.id}?status=${ns}`, {})
    await loadPayers()
  } catch (e: any) {
    showToast('操作失败: ' + (e.message || e), true)
  }
}

onMounted(loadSuppliers)
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div>
      <h2 class="text-2xl font-bold text-[var(--color-text)]">供应商管理</h2>
      <p class="text-sm text-[var(--color-text-muted)]">管理供应商及其关联的代理商和API支付商</p>
    </div>

    <!-- Suppliers Table -->
    <div class="card p-0 overflow-hidden">
      <div v-if="loadingSuppliers" class="p-6 text-sm text-[var(--color-text-muted)]">加载中...</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)] w-16">ID</th>
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">名称</th>
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)] w-24">状态</th>
            <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)] w-24">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in suppliers"
            :key="s.id"
            class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30 cursor-pointer transition-colors"
            :class="{ 'bg-[var(--color-accent)]/5 border-[var(--color-accent)]/30': selectedSupplier?.id === s.id }"
            @click="toggleSupplierRow(s)"
          >
            <td class="p-3 font-mono text-xs text-[var(--color-text-muted)]">#{{ s.id }}</td>
            <td class="p-3 font-medium">{{ s.name }}</td>
            <td class="p-3">
              <Badge :type="s.status === 'ACTIVE' ? 'success' : 'danger'">
                {{ s.status === 'ACTIVE' ? '启用' : '停用' }}
              </Badge>
            </td>
            <td class="p-3 text-right">
              <button
                class="btn btn-outline btn-sm"
                @click.stop="selectSupplier(s)"
              >
                查看详情
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!loadingSuppliers && !suppliers.length" class="p-6 text-center text-sm text-[var(--color-text-muted)]">
        暂无供应商
      </div>
    </div>

    <!-- Detail Area -->
    <template v-if="selectedSupplier">
      <div class="card p-4">
        <div class="flex items-center justify-between mb-3">
          <div>
            <h3 class="text-base font-semibold text-[var(--color-text)]">
              {{ selectedSupplier.name }}
              <span class="text-xs text-[var(--color-text-muted)] font-normal ml-2">#{{ selectedSupplier.id }}</span>
            </h3>
            <p class="text-xs text-[var(--color-text-muted)] mt-0.5">该供应商下的代理商和API支付商管理</p>
          </div>
        </div>

        <!-- Tabs -->
        <div class="flex gap-0 border-b border-[var(--color-border)] mb-4">
          <button
            class="px-4 py-2.5 text-sm font-medium transition-colors relative"
            :class="activeTab === 'agents'
              ? 'text-[var(--color-accent)]'
              : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'"
            @click="activeTab = 'agents'"
          >
            代理商
            <span v-if="activeTab === 'agents'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--color-accent)] rounded-full"></span>
          </button>
          <button
            class="px-4 py-2.5 text-sm font-medium transition-colors relative"
            :class="activeTab === 'api-payers'
              ? 'text-[var(--color-accent)]'
              : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'"
            @click="activeTab = 'api-payers'"
          >
            API支付商
            <span v-if="activeTab === 'api-payers'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--color-accent)] rounded-full"></span>
          </button>
        </div>

        <!-- ===== Agents Tab ===== -->
        <div v-if="activeTab === 'agents'">
          <div class="flex justify-end mb-3">
            <button class="btn btn-primary btn-sm" @click="showCreateAgent = true">
              <Plus class="w-4 h-4" /> 新建代理商
            </button>
          </div>

          <div class="card p-0 overflow-hidden -mx-4 -mb-4 rounded-none border-x-0 border-b-0">
            <div v-if="loadingAgents" class="p-6 text-sm text-[var(--color-text-muted)]">加载中...</div>
            <table v-else class="w-full text-sm">
              <thead>
                <tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
                  <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">名称</th>
                  <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">用户名</th>
                  <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">积分余额</th>
                  <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)] w-24">状态</th>
                  <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)] w-44">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="a in agents" :key="a.id" class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
                  <td class="p-3 font-medium">{{ a.nickname }}</td>
                  <td class="p-3">
                    <div class="flex items-center gap-1.5">
                      <code class="text-xs bg-[var(--color-bg)] px-1.5 py-0.5 rounded font-mono text-[var(--color-accent)]">
                        {{ maskUsername(a.username) }}
                      </code>
                      <button
                        v-if="a.username"
                        @click="copy(a.username)"
                        class="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                        title="复制完整账号"
                      >
                        <Copy class="w-3 h-3" />
                      </button>
                    </div>
                  </td>
                  <td class="p-3 text-right font-mono text-sm font-semibold">{{ (a.balance ?? 0).toLocaleString() }}</td>
                  <td class="p-3">
                    <button
                      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors cursor-pointer"
                      :class="a.status === 'ACTIVE'
                        ? 'bg-brand-success/10 text-brand-success border-brand-success/20 hover:bg-brand-success/20'
                        : 'bg-[var(--color-border)]/30 text-[var(--color-text-muted)] border-[var(--color-border)] hover:bg-[var(--color-border)]/50'"
                      @click="toggleAgentStatus(a)"
                    >
                      <span class="w-1.5 h-1.5 rounded-full" :class="a.status === 'ACTIVE' ? 'bg-brand-success' : 'bg-[var(--color-text-muted)]'"></span>
                      {{ a.status === 'ACTIVE' ? '启用' : '停用' }}
                    </button>
                  </td>
                  <td class="p-3 text-right space-x-1.5">
                    <button class="btn btn-outline btn-sm" @click="openEditAgent(a)" title="编辑">
                      <Pencil class="w-3 h-3" /> 编辑
                    </button>
                    <button class="btn btn-outline btn-sm" @click="resetAgentPassword(a)" title="重置密码">
                      <RotateCw class="w-3 h-3" /> 重置密码
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!loadingAgents && !agents.length" class="p-6 text-center text-sm text-[var(--color-text-muted)]">
              暂无代理商，点击上方「新建代理商」创建
            </div>
          </div>
        </div>

        <!-- ===== API Payers Tab ===== -->
        <div v-if="activeTab === 'api-payers'">
          <div class="flex justify-end mb-3">
            <button class="btn btn-primary btn-sm" @click="showCreatePayer = true">
              <Plus class="w-4 h-4" /> 新建API支付商
            </button>
          </div>

          <div class="card p-0 overflow-hidden -mx-4 -mb-4 rounded-none border-x-0 border-b-0">
            <div v-if="loadingPayers" class="p-6 text-sm text-[var(--color-text-muted)]">加载中...</div>
            <table v-else class="w-full text-sm">
              <thead>
                <tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
                  <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">商户名</th>
                  <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">API Key</th>
                  <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">API Secret</th>
                  <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">回调地址</th>
                  <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)] w-24">状态</th>
                  <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)] w-48">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in payers" :key="p.id" class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
                  <td class="p-3 font-medium">{{ p.nickname }}</td>
                  <td class="p-3">
                    <div class="flex items-center gap-1.5">
                      <code class="text-xs bg-[var(--color-bg)] px-1.5 py-0.5 rounded font-mono">
                        {{ showKey[p.id] ? p.api_key : maskKey(p.api_key) }}
                      </code>
                      <button
                        @click="showKey[p.id] = !showKey[p.id]"
                        class="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                        :title="showKey[p.id] ? '隐藏' : '显示'"
                      >
                        <Eye v-if="!showKey[p.id]" class="w-3 h-3" />
                        <EyeOff v-else class="w-3 h-3" />
                      </button>
                      <button
                        @click="copy(p.api_key)"
                        class="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                        title="复制API Key"
                      >
                        <Copy class="w-3 h-3" />
                      </button>
                    </div>
                  </td>
                  <td class="p-3">
                    <div class="flex items-center gap-1.5">
                      <code class="text-xs bg-[var(--color-bg)] px-1.5 py-0.5 rounded font-mono">
                        <template v-if="showSecret[p.id]">
                          {{ p._newSecret || p.api_secret }}
                        </template>
                        <template v-else>
                          {{ maskSecret(p.api_secret) }}
                        </template>
                      </code>
                      <button
                        @click="showSecret[p.id] = !showSecret[p.id]"
                        class="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                        :title="showSecret[p.id] ? '隐藏' : '显示'"
                      >
                        <Eye v-if="!showSecret[p.id]" class="w-3 h-3" />
                        <EyeOff v-else class="w-3 h-3" />
                      </button>
                      <button
                        @click="copy(p._newSecret || p.api_secret)"
                        class="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                        title="复制API Secret"
                      >
                        <Copy class="w-3 h-3" />
                      </button>
                    </div>
                  </td>
                  <td class="p-3">
                    <code class="text-xs text-[var(--color-text-muted)] font-mono max-w-[160px] truncate inline-block align-middle">
                      {{ p.callback_url || '—' }}
                    </code>
                  </td>
                  <td class="p-3">
                    <button
                      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors cursor-pointer"
                      :class="p.status === 'ACTIVE'
                        ? 'bg-brand-success/10 text-brand-success border-brand-success/20 hover:bg-brand-success/20'
                        : 'bg-[var(--color-border)]/30 text-[var(--color-text-muted)] border-[var(--color-border)] hover:bg-[var(--color-border)]/50'"
                      @click="togglePayerStatus(p)"
                    >
                      <span class="w-1.5 h-1.5 rounded-full" :class="p.status === 'ACTIVE' ? 'bg-brand-success' : 'bg-[var(--color-text-muted)]'"></span>
                      {{ p.status === 'ACTIVE' ? '启用' : '停用' }}
                    </button>
                  </td>
                  <td class="p-3 text-right space-x-1.5">
                    <button class="btn btn-outline btn-sm" @click="openEditPayer(p)" title="编辑">
                      <Pencil class="w-3 h-3" /> 编辑
                    </button>
                    <button class="btn btn-outline btn-sm" @click="resetPayerSecret(p)" title="重置密钥">
                      <RefreshCw class="w-3 h-3" /> 重置密钥
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!loadingPayers && !payers.length" class="p-6 text-center text-sm text-[var(--color-text-muted)]">
              暂无API支付商，点击上方「新建API支付商」创建
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ===== Create Agent Modal ===== -->
    <div v-if="showCreateAgent" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" @click.self="showCreateAgent = false">
      <div class="card p-6 w-full max-w-sm mx-4">
        <h3 class="text-base font-semibold mb-4">新建代理商</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">所属供应商</label>
            <input
              disabled
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]/50 text-sm text-[var(--color-text-muted)] cursor-not-allowed"
              :value="selectedSupplier?.name"
            />
          </div>
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">代理商名称</label>
            <input
              v-model="newAgentNickname"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm"
              placeholder="输入名称"
              @keyup.enter="createAgent"
            />
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="btn btn-outline" @click="showCreateAgent = false">取消</button>
          <button class="btn btn-primary" :disabled="!newAgentNickname" @click="createAgent">创建</button>
        </div>
      </div>
    </div>

    <!-- ===== Edit Agent Modal ===== -->
    <div v-if="showEditAgent && editAgentTarget" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" @click.self="showEditAgent = false">
      <div class="card p-6 w-full max-w-sm mx-4">
        <h3 class="text-base font-semibold mb-4">编辑代理商</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">代理商名称</label>
            <input
              v-model="editAgentTarget.nickname"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm"
              placeholder="输入名称"
              @keyup.enter="saveEditAgent"
            />
          </div>
          <div v-if="editAgentTarget._newPassword" class="p-3 rounded-lg bg-brand-warning/5 border border-brand-warning/20">
            <p class="text-xs text-brand-warning font-medium mb-1">新密码（仅本次显示）</p>
            <code class="text-sm font-mono break-all">{{ editAgentTarget._newPassword }}</code>
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="btn btn-outline" @click="showEditAgent = false">取消</button>
          <button class="btn btn-primary" :disabled="!editAgentTarget.nickname" @click="saveEditAgent">保存</button>
        </div>
      </div>
    </div>

    <!-- ===== Create API Payer Modal ===== -->
    <div v-if="showCreatePayer" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" @click.self="showCreatePayer = false">
      <div class="card p-6 w-full max-w-sm mx-4">
        <h3 class="text-base font-semibold mb-4">新建API支付商</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">所属供应商</label>
            <input
              disabled
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]/50 text-sm text-[var(--color-text-muted)] cursor-not-allowed"
              :value="selectedSupplier?.name"
            />
          </div>
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">商户昵称</label>
            <input
              v-model="newPayerNickname"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm"
              placeholder="输入商户名"
              @keyup.enter="createPayer"
            />
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="btn btn-outline" @click="showCreatePayer = false">取消</button>
          <button class="btn btn-primary" :disabled="!newPayerNickname" @click="createPayer">创建</button>
        </div>
      </div>
    </div>

    <!-- ===== Edit API Payer Modal ===== -->
    <div v-if="showEditPayer && editPayerTarget" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" @click.self="showEditPayer = false">
      <div class="card p-6 w-full max-w-sm mx-4">
        <h3 class="text-base font-semibold mb-4">编辑API支付商</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">商户昵称</label>
            <input
              v-model="editPayerTarget.nickname"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm"
              placeholder="输入商户名"
            />
          </div>
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">回调地址</label>
            <input
              v-model="editPayerTarget.callback_url"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm font-mono"
              placeholder="https://example.com/callback"
            />
          </div>
          <div v-if="editPayerTarget._newSecret" class="p-3 rounded-lg bg-brand-warning/5 border border-brand-warning/20">
            <p class="text-xs text-brand-warning font-medium mb-1">新Secret（仅本次显示）</p>
            <code class="text-sm font-mono break-all">{{ editPayerTarget._newSecret }}</code>
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="btn btn-outline" @click="showEditPayer = false">取消</button>
          <button class="btn btn-primary" :disabled="!editPayerTarget.nickname" @click="saveEditPayer">保存</button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div
      v-if="toast"
      class="fixed bottom-6 left-1/2 -translate-x-1/2 card p-3 z-50 shadow-xl transition-all duration-300"
      :class="toast.includes('失败') ? 'border-red-500/50' : 'border-[var(--color-success)]/50'"
    >
      <p class="text-sm whitespace-nowrap">{{ toast }}</p>
    </div>
  </div>
</template>
