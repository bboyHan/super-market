<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/utils/api'

interface QQAccount {
  id: number
  nickname: string
  uin: string
  midas_openid: string
  midas_openkey: string
  status: 'ACTIVE' | 'EXPIRED' | 'ERROR'
  last_verified_at: string | null
  error_message: string
  created_at: string
  updated_at: string
}

interface AccountList {
  accounts: QQAccount[]
  total: number
  active_count: number
}

const router = useRouter()

// ── 数据 ──
const accounts = ref<QQAccount[]>([])
const total = ref(0)
const activeCount = ref(0)
const loading = ref(true)

// ── 统计 ──
const stats = ref({ total: 0, active: 0, expired: 0 })

// ── 选中批量操作 ──
const selectedIds = ref<Set<number>>(new Set())

// ── Toast ──
const toastMsg = ref('')
const toastVisible = ref(false)
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(msg: string) {
  toastMsg.value = msg
  toastVisible.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastVisible.value = false }, 3000)
}

// ── 加载 ──
async function loadAccounts() {
  loading.value = true
  try {
    const data = await api.get<AccountList>('/api/accounts/qq')
    accounts.value = data?.accounts || []
    total.value = data?.total || 0
    activeCount.value = data?.active_count || 0

    // 统计
    const s = { total: total.value, active: 0, expired: 0 }
    for (const a of accounts.value) {
      if (a.status === 'ACTIVE') s.active++
      else s.expired++
    }
    stats.value = s
  } catch {
    accounts.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadAccounts)

// ── 删除 ──
async function deleteAccount(id: number) {
  if (!confirm('确认删除此QQ账号？')) return
  try {
    await api.delete(`/api/accounts/qq/${id}`)
    showToast('已删除')
    await loadAccounts()
  } catch {
    showToast('删除失败')
  }
}

// ── 状态标签 ──
function statusBadge(s: string): string {
  const map: Record<string, string> = {
    ACTIVE: 'badge-green',
    EXPIRED: 'badge-red',
    ERROR: 'badge-red',
  }
  return map[s] || 'badge-gray'
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    ACTIVE: '有效',
    EXPIRED: '已失效',
    ERROR: '异常',
  }
  return map[s] || s
}

// ── 格式化时间 ──
function fmt(t: string | null): string {
  if (!t) return '—'
  return t.replace('T', ' ').substring(0, 19)
}

// ── 创建采集任务（跳转到任务页） ──
function createTaskForAccount(acct: QQAccount) {
  // 跳转到 tasks 页并携带 account_id 参数
  router.push(`/tasks?account_id=${acct.id}&product_id=27`)
}

function createBatchTask() {
  router.push('/tasks?batch_qq=1&product_id=27')
}
</script>

<template>
  <div class="accounts-page">

    <!-- 顶部统计条 -->
    <div class="stat-bar">
      <div class="stat-item">
        <span class="stat-value">{{ stats.total }}</span>
        <span class="stat-label">账号总数</span>
      </div>
      <div class="stat-divider" />
      <div class="stat-item">
        <span class="stat-value green">{{ stats.active }}</span>
        <span class="stat-label">有效</span>
      </div>
      <div class="stat-divider" />
      <div class="stat-item">
        <span class="stat-value red">{{ stats.expired }}</span>
        <span class="stat-label">失效/异常</span>
      </div>
    </div>

    <!-- 操作栏 -->
    <div class="action-bar">
      <div class="action-hint">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
        <span>每个QQ账号首次使用需要扫码登录，登录成功后自动保存 Token，后续可直接使用无需再次扫码</span>
      </div>
      <div class="action-buttons">
        <button class="btn btn-primary" @click="createBatchTask">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
          </svg>
          批量采集 Q币
        </button>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-state">
      <div class="spinner" />
      <span>加载中…</span>
    </div>

    <!-- 空状态 -->
    <div v-else-if="accounts.length === 0" class="empty-state">
      <svg class="empty-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)"
        stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
      <p class="empty-title">暂无QQ账号</p>
      <p class="empty-desc">前往「采集任务」页，选择 Q币 货品发起采集，首次扫码登录后账号会自动保存到这里</p>
      <button class="btn btn-primary" @click="router.push('/tasks')">去创建采集任务</button>
    </div>

    <!-- 账号列表 -->
    <div v-else class="account-grid">
      <div
        v-for="acct in accounts"
        :key="acct.id"
        class="card account-card"
        :class="{ 'card-expired': acct.status !== 'ACTIVE' }"
      >

        <!-- 头像区 -->
        <div class="account-avatar">
          <div class="avatar-circle" :class="{ 'avatar-green': acct.status === 'ACTIVE', 'avatar-red': acct.status !== 'ACTIVE' }">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
            </svg>
          </div>
        </div>

        <!-- 信息区 -->
        <div class="account-info">
          <div class="info-top">
            <span class="account-name">{{ acct.nickname || '未命名账号' }}</span>
            <span class="badge" :class="statusBadge(acct.status)">{{ statusLabel(acct.status) }}</span>
            <span v-if="acct.uin" class="account-uin">QQ: {{ acct.uin }}</span>
          </div>
          <div class="info-meta">
            <span class="meta-item">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
              添加于 {{ fmt(acct.created_at) }}
            </span>
            <span v-if="acct.last_verified_at" class="meta-item">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
              最后验证 {{ fmt(acct.last_verified_at) }}
            </span>
          </div>
          <div v-if="acct.error_message" class="info-error">
            {{ acct.error_message }}
          </div>
        </div>

        <!-- 操作区 -->
        <div class="account-actions">
          <button
            class="btn btn-sm btn-primary"
            :disabled="acct.status !== 'ACTIVE'"
            @click="createTaskForAccount(acct)"
            title="使用此账号采集"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
            采集
          </button>
          <button class="btn btn-sm btn-danger" @click="deleteAccount(acct.id)" title="删除">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <Transition name="toast">
      <div v-if="toastVisible" class="toast">{{ toastMsg }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.accounts-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 900px;
  position: relative;
}

/* ── 统计条 ── */
.stat-bar {
  display: flex;
  align-items: center;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 14px 0;
  border: 1px solid var(--border-color);
}

.stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--text-primary);
}

.stat-value.green { color: var(--accent-green); }
.stat-value.red { color: var(--accent-red); }

.stat-label {
  font-size: 11px;
  color: var(--text-muted);
  letter-spacing: 0.03em;
}

.stat-divider {
  width: 1px;
  height: 32px;
  background: var(--border-color);
}

/* ── 操作栏 ── */
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.action-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.4;
}

.action-buttons {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

/* ── 加载 ── */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--text-muted);
  font-size: 13px;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-color);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── 空状态 ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 20px;
  text-align: center;
}

.empty-icon { opacity: 0.4; }
.empty-title { font-size: 16px; font-weight: 600; color: var(--text-secondary); }
.empty-desc { font-size: 13px; color: var(--text-muted); max-width: 360px; line-height: 1.5; }

/* ── 账号卡片 ── */
.account-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.account-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  transition: all 0.2s ease;
}

.account-card:hover {
  border-color: var(--accent-primary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.card-expired {
  opacity: 0.6;
}

/* 头像 */
.account-avatar {
  flex-shrink: 0;
}

.avatar-circle {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-green {
  background: var(--accent-green-bg, rgba(34,197,94,0.1));
  color: var(--accent-green);
}

.avatar-red {
  background: var(--accent-red-bg, rgba(239,68,68,0.1));
  color: var(--accent-red);
}

/* 信息 */
.account-info {
  flex: 1;
  min-width: 0;
}

.info-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.account-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.account-uin {
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'SF Mono', monospace;
  background: var(--bg-tertiary);
  padding: 1px 6px;
  border-radius: 4px;
}

.info-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.info-error {
  font-size: 11px;
  color: var(--accent-red);
  margin-top: 3px;
  background: var(--accent-red-bg, rgba(239,68,68,0.06));
  padding: 4px 8px;
  border-radius: 4px;
}

/* 操作 */
.account-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

/* ── Toast ── */
.toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg-card);
  border: 1px solid var(--accent-primary);
  color: var(--text-primary);
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
  z-index: 9999;
  white-space: nowrap;
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(16px);
}
</style>
