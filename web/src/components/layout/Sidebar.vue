<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'
import {
  LayoutDashboard, ShoppingCart, Users, Wallet, Cpu,
  BarChart3, Package, Warehouse,
  ChevronLeft, ChevronRight, Store, Shield, Terminal, DollarSign, Settings, Key,
} from 'lucide-vue-next'

const props = defineProps<{ collapsed: boolean; mobileOpen: boolean }>()
const emit = defineEmits<{ toggle: []; closeMobile: [] }>()
const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const supplierItems = [
  { label: '仪表盘', icon: LayoutDashboard, path: '/dashboard' },
  { label: '订单管理', icon: ShoppingCart, path: '/orders' },
  { label: '代理商管理', icon: Users, path: '/agents' },
  { label: '货品管理', icon: Package, path: '/products' },
  { label: '财务管理', icon: Wallet, path: '/finance' },
  { label: 'API渠道', icon: Cpu, path: '/apichannel' },
]
const agentItems = [
  { label: '代理商仪表盘', icon: BarChart3, path: '/agent/dashboard' },
  { label: '交付管理', icon: Package, path: '/agent/delivery' },
  { label: '库存管理', icon: Warehouse, path: '/agent/inventory' },
  { label: '工具授权', icon: Key, path: '/agent/auth-tokens' },
]
const adminItems = [
  { label: '供应商管理', icon: Store, path: '/suppliers' },
  { label: '账号管理', icon: Shield, path: '/admin/accounts' },
{ label: '充值审核', icon: DollarSign, path: '/admin/deposits' },
  { label: '模拟终端', icon: Terminal, path: '/admin/simulate' },
  { label: '商品配置', icon: Settings, path: '/admin/product-configs' },
]

const isActive = (path: string) => route.path === path || route.path.startsWith(path + '/')
const navigate = (to: string) => { router.push(to); emit('closeMobile') }
const sidebarWidth = computed(() => props.collapsed ? 'w-16' : 'w-64')

const role = computed(() => userStore.user?.role)
const showSupplier = computed(() => role.value === 'SUPPLIER' || role.value === 'ADMIN')
const showAgent = computed(() => role.value === 'AGENT' || role.value === 'ADMIN')
const showAdmin = computed(() => role.value === 'ADMIN')
const showDeposit = computed(() => showSupplier.value || showAgent.value)
</script>

<template>
  <aside :class="[
    sidebarWidth,
    mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
    'fixed lg:static inset-y-0 left-0 z-50 flex flex-col',
    'bg-[var(--color-card)] border-r border-[var(--color-border)]',
    'transition-all duration-300 ease-in-out',
  ]">
    <div class="flex h-16 items-center justify-between px-4 border-b border-[var(--color-border)]">
      <div v-if="!collapsed" class="flex items-center gap-2.5">
        <Store class="w-6 h-6 text-[var(--color-accent)]" />
        <span class="font-semibold text-base text-[var(--color-text)]">Super Market</span>
      </div>
      <Store v-else class="w-6 h-6 text-[var(--color-accent)] mx-auto" />
    </div>

    <nav class="flex-1 overflow-y-auto p-3 space-y-1">
      <!-- Supplier section -->
      <template v-if="showSupplier">
        <p v-if="!collapsed" class="px-3 pt-4 pb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">供应商</p>
        <div class="space-y-0.5">
          <div v-for="item in supplierItems" :key="item.path"
            :class="[isActive(item.path) ? 'sidebar-link-active' : 'sidebar-link', collapsed && 'justify-center px-0']"
            @click="navigate(item.path)" :title="collapsed ? item.label : undefined">
            <component :is="item.icon" class="w-5 h-5 shrink-0" />
            <span v-if="!collapsed" class="truncate">{{ item.label }}</span>
          </div>
        </div>
      </template>

      <!-- Agent section -->
      <template v-if="showAgent">
        <p v-if="!collapsed" class="px-3 pt-6 pb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">代理商</p>
        <div class="space-y-0.5">
          <div v-for="item in agentItems" :key="item.path"
            :class="[isActive(item.path) ? 'sidebar-link-active' : 'sidebar-link', collapsed && 'justify-center px-0']"
            @click="navigate(item.path)" :title="collapsed ? item.label : undefined">
            <component :is="item.icon" class="w-5 h-5 shrink-0" />
            <span v-if="!collapsed" class="truncate">{{ item.label }}</span>
          </div>
        </div>
      </template>

      <!-- Admin section -->
      <template v-if="showAdmin">
        <p v-if="!collapsed" class="px-3 pt-6 pb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">管理</p>
        <div class="space-y-0.5">
          <div v-for="item in adminItems" :key="item.path"
            :class="[isActive(item.path) ? 'sidebar-link-active' : 'sidebar-link', collapsed && 'justify-center px-0']"
            @click="navigate(item.path)" :title="collapsed ? item.label : undefined">
            <component :is="item.icon" class="w-5 h-5 shrink-0" />
            <span v-if="!collapsed" class="truncate">{{ item.label }}</span>
          </div>
        </div>
      </template>
    </nav>

    <!-- Bottom: Deposit for supplier/agent -->
    <div v-if="showDeposit" class="border-t border-[var(--color-border)] p-3">
      <div :class="['flex items-center gap-3 rounded-lg py-2 px-3 cursor-pointer transition-colors',
        isActive('/deposit') ? 'sidebar-link-active' : 'sidebar-link',
        collapsed && 'justify-center px-0']"
        @click="navigate('/deposit')" :title="collapsed ? '积分充值' : undefined">
        <DollarSign class="w-5 h-5 shrink-0" />
        <span v-if="!collapsed" class="truncate text-sm font-medium">积分充值</span>
      </div>
    </div>

    <!-- Bottom: Admin tools -->
    <div v-if="showAdmin" class="border-t border-[var(--color-border)] p-3">
      <div :class="['flex items-center gap-3 rounded-lg py-2 px-3 cursor-pointer transition-colors',
        isActive('/admin/auth-tokens') ? 'sidebar-link-active' : 'sidebar-link',
        collapsed && 'justify-center px-0']"
        @click="navigate('/admin/auth-tokens')" :title="collapsed ? '工具授权' : undefined">
        <Key class="w-5 h-5 shrink-0" />
        <span v-if="!collapsed" class="truncate text-sm font-medium">工具授权</span>
      </div>
    </div>

    <div class="hidden lg:block border-t border-[var(--color-border)] p-3">
      <button class="flex items-center justify-center w-full py-2 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-all duration-200"
        @click="emit('toggle')" :title="collapsed ? '展开侧边栏' : '折叠侧边栏'">
        <ChevronLeft v-if="!collapsed" class="w-4 h-4" />
        <ChevronRight v-else class="w-4 h-4" />
      </button>
    </div>
  </aside>
</template>
