<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/utils/api'

interface AuthToken {
  id: number
  token: string
  name: string
  status: string
  last_used_at: string | null
  created_at: string
}

const tokens = ref<AuthToken[]>([])
const loading = ref(true)
const showCreateModal = ref(false)
const newName = ref('')
const createdToken = ref('')
const showCreated = ref(false)

onMounted(async () => {
  await loadData()
})

async function loadData() {
  loading.value = true
  try {
    const res = await api.get('/api/merchant/agent/auth-tokens')
    tokens.value = res?.data || []
  } catch (e) {
    console.error('Failed to load tokens:', e)
  }
  loading.value = false
}

async function createToken() {
  try {
    const res = await api.post('/api/merchant/agent/auth-tokens', { name: newName.value })
    if (res?.data) {
      createdToken.value = res.data.token
      showCreated.value = true
      showCreateModal.value = false
      newName.value = ''
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
  newName.value = ''
}

function copyToken() {
  navigator.clipboard.writeText(createdToken.value).catch(() => {
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
    await api.delete(`/api/merchant/agent/auth-tokens/${id}`)
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
        <p class="desc">管理你的 Agent Terminal 授权 API Key</p>
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
            <div class="field">
              <label>备注名称（可选）</label>
              <input v-model="newName" class="input" placeholder="如：办公室电脑、出差笔记本" />
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-primary" @click="createToken">生成</button>
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
              <span class="agent-name">{{ t.name || '未命名' }}</span>
              <span class="badge" :class="t.status === 'ACTIVE' ? 'badge-green' : 'badge-gray'">
                {{ t.status === 'ACTIVE' ? '正常' : '已失效' }}
              </span>
            </div>
            <code class="token-key">{{ t.token.substring(0, 20) }}...{{ t.token.slice(-8) }}</code>
            <div class="token-meta">创建于 {{ formatTime(t.created_at) }}</div>
          </div>
          <div class="token-actions">
            <button v-if="t.status === 'ACTIVE'" class="btn btn-sm btn-danger" @click="revokeToken(t.id)">失效</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 800px; }
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
.token-agent { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.agent-name { font-size: 14px; font-weight: 600; }
.token-key { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; font-family: monospace; }
.token-meta { font-size: 11px; color: var(--text-muted); }
.token-actions { display: flex; gap: 6px; flex-shrink: 0; }
.modal-overlay { position: fixed; top:0; left:0; right:0; bottom:0; background: rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; z-index:1000; }
.modal { width: 400px; padding:0; overflow:hidden; }
.modal-header { display:flex; justify-content:space-between; align-items:center; padding:16px 20px; border-bottom:1px solid var(--border-color); }
.modal-header h4 { font-size:15px; font-weight:600; }
.close-btn { background:none; border:none; color:var(--text-muted); cursor:pointer; padding:4px 8px; border-radius:4px; }
.modal-body { padding:20px; }
.modal-footer { display:flex; gap:8px; padding:16px 20px; border-top:1px solid var(--border-color); justify-content:flex-end; }
.field { display:flex; flex-direction:column; gap:6px; }
.field label { font-size:12px; font-weight:500; color:var(--text-muted); }
.input { padding:8px 12px; border:1px solid var(--border-color); border-radius:6px; background:var(--bg-secondary); color:var(--text-primary); font-size:13px; }
.badge { font-size:11px; padding:2px 8px; border-radius:4px; font-weight:500; }
.badge-green { background:rgba(34,197,94,0.15); color:#22c55e; }
.badge-gray { background:var(--bg-tertiary); color:var(--text-muted); }
</style>
