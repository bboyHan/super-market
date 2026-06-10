<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/utils/api'

interface AuthToken {
  id: number
  agent_id: number | null
  owner_type: string
  token: string
  name: string
  status: string
  agent_name: string
  last_used_at: string | null
  expires_at: string | null
  created_at: string
}

interface AgentOption {
  id: number
  name: string
  supplier: string
}

const tokens = ref<AuthToken[]>([])
const agents = ref<AgentOption[]>([])
const loading = ref(true)
const showCreateModal = ref(false)
const createType = ref<'admin' | 'agent'>('admin')
const newToken = ref({ agent_id: 0, name: '' })
const createdToken = ref('')
const showCreated = ref(false)

onMounted(async () => {
  await loadData()
})

async function loadData() {
  loading.value = true
  try {
    const [tokensRes, agentsRes] = await Promise.all([
      api.get('/api/admin/auth-tokens'),
      api.get('/api/admin/agent-list'),
    ])
    tokens.value = tokensRes?.data || []
    agents.value = agentsRes?.data || []
  } catch (e) {
    console.error('Failed to load:', e)
  }
  loading.value = false
}

async function createToken() {
  try {
    const payload: any = { owner_type: createType.value, name: newToken.value.name }
    if (createType.value === 'agent') {
      if (!newToken.value.agent_id) return
      payload.agent_id = newToken.value.agent_id
    }
    const res = await api.post('/api/admin/auth-tokens', payload)
    if (res?.data) {
      createdToken.value = res.data.token
      showCreated.value = true
      showCreateModal.value = false
      newToken.value = { agent_id: 0, name: '' }
      await loadData()
    }
  } catch (e) {
    console.error('Failed to create token:', e)
  }
}

function openCreate() {
  showCreateModal.value = true
  showCreated.value = false
  createdToken.value = ''
  createType.value = 'admin'
  newToken.value = { agent_id: 0, name: '' }
}

function copyToken() {
  navigator.clipboard.writeText(createdToken.value).catch(() => {
    // Fallback for non-HTTPS dev
    const ta = document.createElement('textarea')
    ta.value = createdToken.value
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  })
}

async function revokeToken(id: number) {
  if (!confirm('确认将该授权码失效？')) return
  try {
    await api.delete(`/api/admin/auth-tokens/${id}`)
    await loadData()
  } catch (e) {
    console.error('Failed to revoke:', e)
  }
}

function formatTime(t: string | null) {
  if (!t) return '—'
  return t.substring(0, 19).replace('T', ' ')
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h3 class="title">工具授权</h3>
        <p class="desc">管理所有 Agent Terminal 的授权 API Key</p>
      </div>
      <button class="btn btn-primary" @click="openCreate">生成授权码</button>
    </div>

    <!-- Created Token Notification -->
    <div v-if="showCreated && createdToken" class="card created-card">
      <div class="created-header">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent-green)" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
        </svg>
        <span>授权码已生成，请立即复制并安全保存</span>
      </div>
      <div class="token-display">
        <code class="token-value">{{ createdToken }}</code>
        <button class="btn btn-sm btn-primary" @click="copyToken">复制</button>
      </div>
      <button class="btn btn-outline btn-sm" @click="showCreated = false" style="margin-top:8px">关闭</button>
    </div>

    <!-- Create Modal -->
    <Teleport to="body">
      <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
        <div class="modal card">
          <div class="modal-header">
            <h4>生成授权码</h4>
            <button class="close-btn" @click="showCreateModal = false">✕</button>
          </div>
          <div class="modal-body">
            <!-- Type Tabs -->
            <div class="type-tabs">
              <button
                :class="['tab-btn', { active: createType === 'admin' }]"
                @click="createType = 'admin'; newToken.agent_id = 0"
              >管理员</button>
              <button
                :class="['tab-btn', { active: createType === 'agent' }]"
                @click="createType = 'agent'"
              >代理商</button>
            </div>

            <!-- Agent select (only when type=agent) -->
            <div v-if="createType === 'agent'" class="field">
              <label>选择代理商</label>
              <select v-model.number="newToken.agent_id" class="input native-select">
                <option value="0" disabled>请选择代理商</option>
                <option v-for="a in agents" :key="a.id" :value="a.id">
                  {{ a.name }}（{{ a.supplier }}）
                </option>
              </select>
            </div>
            <div v-else class="field">
              <label>使用身份</label>
              <div class="admin-info">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                <span>管理员身份 — 拥有平台全部权限</span>
              </div>
            </div>

            <div class="field">
              <label>备注名称（可选）</label>
              <input v-model="newToken.name" class="input" placeholder="如：办公室电脑、出差笔记本" />
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-primary" @click="createToken"
              :disabled="createType === 'agent' && !newToken.agent_id">生成</button>
            <button class="btn btn-outline" @click="showCreateModal = false">取消</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Token List -->
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="tokens.length === 0" class="empty">
      <p>暂无授权码，点击上方「生成授权码」创建</p>
    </div>
    <div v-else class="token-list">
      <div v-for="t in tokens" :key="t.id" class="token-card card" :class="{ inactive: t.status !== 'ACTIVE' }">
        <div class="token-row">
          <div class="token-info">
            <div class="token-agent">
              <span v-if="t.owner_type === 'admin'" class="owner-badge admin-badge">管理员</span>
              <span v-else class="owner-badge agent-badge">代理商</span>
              <span class="agent-name">{{ t.agent_name }}</span>
              <span v-if="t.name" class="token-name">（{{ t.name }}）</span>
              <span class="badge" :class="t.status === 'ACTIVE' ? 'badge-green' : 'badge-gray'">
                {{ t.status === 'ACTIVE' ? '正常' : '已失效' }}
              </span>
            </div>
            <code class="token-key">{{ t.token.substring(0, 20) }}...{{ t.token.slice(-8) }}</code>
            <div class="token-meta">
              <span>创建于 {{ formatTime(t.created_at) }}</span>
              <span v-if="t.last_used_at">｜最后使用 {{ formatTime(t.last_used_at) }}</span>
            </div>
          </div>
          <div class="token-actions">
            <button
              v-if="t.status === 'ACTIVE'"
              class="btn btn-sm btn-danger"
              @click="revokeToken(t.id)"
            >失效</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 900px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.title { font-size: 18px; font-weight: 600; }
.desc { font-size: 13px; color: var(--text-muted); margin-top: 4px; }
.loading, .empty { text-align: center; padding: 40px; color: var(--text-muted); }

.created-card { padding: 16px; margin-bottom: 16px; border: 1px solid var(--accent-green); }
.created-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; font-size: 14px; font-weight: 500; }
.token-display { display: flex; align-items: center; gap: 8px; }
.token-value { font-family: monospace; font-size: 13px; padding: 8px 12px; background: var(--bg-tertiary); border-radius: 6px; word-break: break-all; flex: 1; }

.token-list { display: flex; flex-direction: column; gap: 10px; }
.token-card { padding: 14px 16px; }
.token-card.inactive { opacity: 0.6; }
.token-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.token-info { flex: 1; }
.token-agent { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.agent-name { font-size: 14px; font-weight: 600; }
.token-name { font-size: 12px; color: var(--text-muted); }
.token-key { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; font-family: monospace; }
.token-meta { font-size: 11px; color: var(--text-muted); }
.token-actions { display: flex; gap: 6px; flex-shrink: 0; }

/* Owner type badge */
.owner-badge { font-size: 10px; padding: 2px 7px; border-radius: 4px; font-weight: 600; }
.admin-badge { background: rgba(99,102,241,0.15); color: #818cf8; }
.agent-badge { background: rgba(251,191,36,0.15); color: #fbbf24; }

/* Modal */
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { width: 440px; padding: 0; overflow: hidden; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid var(--border-color); }
.modal-header h4 { font-size: 15px; font-weight: 600; }
.close-btn { background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 4px 8px; border-radius: 4px; }
.close-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.modal-body { padding: 20px; display: flex; flex-direction: column; gap: 16px; }
.modal-footer { display: flex; gap: 8px; padding: 16px 20px; border-top: 1px solid var(--border-color); justify-content: flex-end; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field label { font-size: 12px; font-weight: 500; color: var(--text-muted); }
.input { padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-secondary); color: var(--text-primary); font-size: 13px; }
.input:focus { outline: none; border-color: var(--accent-primary); }

/* Native select fix */
.native-select { min-height: 38px; cursor: pointer; }
.native-select option { padding: 8px; }

/* Type tabs */
.type-tabs { display: flex; gap: 8px; }
.tab-btn { flex: 1; padding: 10px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--bg-secondary); color: var(--text-muted); font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.2s; }
.tab-btn.active { border-color: var(--accent-primary); color: var(--accent-primary); background: var(--accent-primary-bg); }
.tab-btn:hover { border-color: var(--accent-primary); }

.admin-info { display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: var(--bg-tertiary); border-radius: 6px; font-size: 13px; color: var(--text-secondary); }

.badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.badge-green { background: rgba(34,197,94,0.15); color: #22c55e; }
.badge-gray { background: var(--bg-tertiary); color: var(--text-muted); }
</style>
