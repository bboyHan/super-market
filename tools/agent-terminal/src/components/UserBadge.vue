<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

interface UserInfo {
  token: string
  user_id?: number
  username?: string
  role?: string
  agent_id?: number
  supplier_id?: number
  agent_name?: string
}

const userInfo = ref<UserInfo | null>(null)
const showMenu = ref(false)

function loadUserInfo() {
  try {
    const raw = localStorage.getItem('agent-info')
    if (raw) {
      userInfo.value = JSON.parse(raw)
    }
  } catch {
    userInfo.value = null
  }
}

onMounted(loadUserInfo)

// 监听 storage 变化（其他标签页登录/退出）
window.addEventListener('storage', loadUserInfo)

const displayName = computed(() => {
  if (!userInfo.value) return ''
  return userInfo.value.agent_name || userInfo.value.username || '未知用户'
})

const roleLabel = computed(() => {
  const role = userInfo.value?.role || ''
  return role === 'ADMIN' ? '管理员' : role === 'AGENT' ? '代理商' : role
})

const isAdmin = computed(() => userInfo.value?.role === 'ADMIN')

function handleLogout() {
  localStorage.removeItem('agent-token')
  localStorage.removeItem('agent-info')
  userInfo.value = null
  showMenu.value = false
  router.push('/login')
}

// 点击外部关闭菜单
function onClickOutside(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.user-badge')) {
    showMenu.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
})
</script>

<template>
  <div v-if="userInfo" class="user-badge" @click.stop>
    <button class="badge-btn" @click="showMenu = !showMenu" :title="displayName">
      <span class="role-dot" :class="{ admin: isAdmin }"></span>
      <span class="user-name">{{ displayName }}</span>
      <svg
        class="chevron"
        :class="{ open: showMenu }"
        width="12" height="12" viewBox="0 0 24 24"
        fill="none" stroke="currentColor" stroke-width="2.5"
        stroke-linecap="round" stroke-linejoin="round"
      >
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </button>

    <Transition name="fade">
      <div v-if="showMenu" class="dropdown">
        <div class="dropdown-header">
          <div class="dropdown-role-badge" :class="{ admin: isAdmin }">
            {{ roleLabel }}
          </div>
          <div class="dropdown-name">{{ displayName }}</div>
          <div v-if="userInfo.agent_id" class="dropdown-id">
            ID: {{ userInfo.agent_id }}
          </div>
        </div>
        <div class="dropdown-divider"></div>
        <button class="dropdown-item logout" @click="handleLogout">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          退出登录
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.user-badge {
  position: relative;
  user-select: none;
}

.badge-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md, 8px);
  background: var(--bg-primary);
  color: var(--text-primary);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s ease;
}

.badge-btn:hover {
  border-color: var(--accent-primary);
  background: var(--bg-hover);
}

.role-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b82f6;  /* 代理商蓝色 */
  flex-shrink: 0;
}

.role-dot.admin {
  background: #f59e0b;  /* 管理员金色 */
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
}

.user-name {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chevron {
  transition: transform 0.2s ease;
  color: var(--text-muted);
}

.chevron.open {
  transform: rotate(180deg);
}

/* ── 下拉菜单 ── */

.dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 200px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md, 10px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  z-index: 1000;
  overflow: hidden;
}

.dropdown-header {
  padding: 14px 16px 12px;
  text-align: center;
}

.dropdown-role-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
  margin-bottom: 8px;
}

.dropdown-role-badge.admin {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.dropdown-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.dropdown-id {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.dropdown-divider {
  height: 1px;
  background: var(--border-color);
  margin: 0;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 16px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}

.dropdown-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.dropdown-item.logout:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.08);
}

/* ── 动画 ── */

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(-4px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-2px);
}
</style>
