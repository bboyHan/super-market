<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/utils/api'
import Badge from '@/components/ui/Badge.vue'
import { Package, Search } from 'lucide-vue-next'

const products = ref<any[]>([])
const loading = ref(true)
const searchKeyword = ref('')
const toast = ref('')

function showToast(msg: string, type: 'success' | 'error' = 'success') {
  toast.value = msg
  setTimeout(() => toast.value = '', 3000)
}

async function loadProducts() {
  loading.value = true
  try {
    const r = await api.get<{code: number; data: any[]}>('/api/merchant/products')
    products.value = r.data || []
  } catch (e: any) {
    showToast(`加载失败: ${e.message || e}`, 'error')
  } finally { loading.value = false }
}

async function toggleStatus(p: any) {
  const newStatus = p.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
  try {
    await api.put(`/api/merchant/products/${p.id}/status?status=${newStatus}`, {})
    p.status = newStatus
    showToast(newStatus === 'ACTIVE' ? '已上架' : '已下架')
  } catch (e: any) {
    showToast(`操作失败: ${e.message || e}`, 'error')
  }
}

const filteredProducts = ref<any[]>([])
function filterProducts() {
  if (!searchKeyword.value) {
    filteredProducts.value = products.value
    return
  }
  const kw = searchKeyword.value.toLowerCase()
  filteredProducts.value = products.value.filter(p =>
    (p.name || '').toLowerCase().includes(kw) ||
    (p.category || '').toLowerCase().includes(kw)
  )
}

onMounted(async () => {
  await loadProducts()
  filterProducts()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold text-[var(--color-text)]">货品管理</h2>
        <p class="text-sm text-[var(--color-text-muted)]">查看和管理已获授权的商品</p>
      </div>
    </div>

    <!-- Search -->
    <div class="relative max-w-sm">
      <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-muted)]" />
      <input v-model="searchKeyword" @input="filterProducts"
        class="w-full pl-9 pr-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm"
        placeholder="搜索商品名称或分类..." />
    </div>

    <!-- Product Table -->
    <div class="card p-0 overflow-hidden">
      <div v-if="loading" class="p-6 text-sm text-[var(--color-text-muted)]">加载中...</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">商品名称</th>
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">分类</th>
            <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">面值</th>
            <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">建议售价</th>
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">采集配置</th>
            <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">状态</th>
            <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in filteredProducts" :key="p.id"
            class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
            <td class="p-3 font-medium">
              <div class="flex items-center gap-2">
                <Package class="w-4 h-4 text-[var(--color-text-muted)] shrink-0" />
                {{ p.name }}
              </div>
            </td>
            <td class="p-3 text-[var(--color-text-muted)]">{{ p.category || '-' }}</td>
            <td class="p-3 text-right font-mono">{{ p.face_value }}</td>
            <td class="p-3 text-right font-mono">{{ p.suggested_price }}</td>
            <td class="p-3">
              <div v-if="p.collection_config" class="text-xs">
                <span class="chip chip-blue">{{ p.collection_config.platform || '未配置' }}</span>
                <span class="text-[var(--color-text-muted)] ml-1">{{ (p.collection_config.methods || []).join(', ') }}</span>
              </div>
              <span v-else class="text-xs text-[var(--color-text-muted)]">未配置</span>
            </td>
            <td class="p-3">
              <Badge :status="p.status === 'ACTIVE' ? 'success' : 'inactive'">
                {{ p.status === 'ACTIVE' ? '上架' : '下架' }}
              </Badge>
            </td>
            <td class="p-3 text-right">
              <button v-if="p.status === 'ACTIVE'" class="btn btn-sm btn-outline" @click="toggleStatus(p)">
                下架
              </button>
              <button v-else class="btn btn-sm btn-outline" @click="toggleStatus(p)">
                上架
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!loading && !filteredProducts.length" class="p-6 text-center text-sm text-[var(--color-text-muted)]">
        {{ searchKeyword ? '未搜索到匹配的货品' : '暂无已授权的商品' }}
      </div>
    </div>

    <!-- Toast -->
    <div v-if="toast"
      class="fixed bottom-6 left-1/2 -translate-x-1/2 card p-3 z-50 shadow-xl whitespace-nowrap"
      :class="toast.includes('失败') ? 'border-red-500/50' : 'border-[var(--color-success)]/50'">
      <p class="text-sm">{{ toast }}</p>
    </div>
  </div>
</template>

<style scoped>
.chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
}
.chip-blue {
  background: rgba(37, 99, 235, 0.08);
  color: #3b82f6;
}
</style>
