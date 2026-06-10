<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '@/utils/api'
import Badge from '@/components/ui/Badge.vue'
import { Plus, Edit, Settings, UserCheck, X, Search, ToggleLeft, ToggleRight, Gift, Gamepad2, Film, Smartphone, Package } from 'lucide-vue-next'

// ── Data ──
const products = ref<any[]>([])
const suppliers = ref<any[]>([])
const loading = ref(true)
const searchKeyword = ref('')
const activeTab = ref<'list' | 'config' | 'suppliers'>('list')

// Toast
const toast = ref('')
function showToast(msg: string, type: 'success' | 'error' = 'success') {
  toast.value = msg
  setTimeout(() => toast.value = '', 3000)
}

// ── Product CRUD ──
const showProductForm = ref(false)
const productForm = ref({ id: null as number | null, name: '', category: '', face_value: 0, platform: '' })
const savingProduct = ref(false)

async function loadProducts() {
  loading.value = true
  try {
    const r = await api.get<{code: number; data: any[]}>('/api/admin/products')
    products.value = r.data
  } catch (e: any) {
    showToast(`加载失败: ${e.message || e}`, 'error')
  } finally { loading.value = false }
}

async function loadSuppliers() {
  try {
    const r = await api.get<{code: number; data: any[]}>('/api/admin/suppliers')
    suppliers.value = r.data
  } catch { /* ignore */ }
}

function openCreate() {
  productForm.value = { id: null, name: '', category: '', face_value: 0, platform: '' }
  showProductForm.value = true
}

function openEdit(p: any) {
  productForm.value = {
    id: p.id,
    name: p.name || '',
    category: p.category || '',
    face_value: p.face_value || 0,
    platform: p.platform || '',
  }
  showProductForm.value = true
}

async function saveProduct() {
  const f = productForm.value
  if (!f.name) { showToast('请输入商品名称', 'error'); return }
  savingProduct.value = true
  try {
    if (f.id) {
      await api.put(`/api/admin/products/${f.id}`, {
        name: f.name, category: f.category, face_value: f.face_value,
        platform: f.platform,
      })
      showToast('商品已更新')
    } else {
      await api.post('/api/admin/products', {
        name: f.name, category: f.category, face_value: f.face_value,
        platform: f.platform,
      })
      showToast('商品已创建')
    }
    showProductForm.value = false
    await loadProducts()
  } catch (e: any) {
    showToast(`保存失败: ${e.message || e}`, 'error')
  } finally { savingProduct.value = false }
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

// ── Collection Config ──
const configProduct = ref<any>(null)
const configForm = ref({
  platform: '',
  methods: [] as string[],
  default_method: '',
  login_url: '',
  capture: '',
})
const savingConfig = ref(false)

const platformOptions = ['京东', '淘宝', '抖音', '拼多多', '通用']
const methodOptions = ['browser', 'emulator', 'cdp', 'manual']
const methodLabels: Record<string, string> = {
  browser: '浏览器自动化', emulator: '模拟器抓包', cdp: 'CDP 辅助', manual: '手动录入',
}
const captureOptions = [
  { value: '', label: '自动检测' },
  { value: 'network', label: '网络请求捕获' },
  { value: 'mitmproxy', label: 'mitmproxy 代理' },
  { value: 'cdp', label: 'CDP 监听' },
  { value: 'ocr', label: '截图 OCR' },
]

function openConfig(p: any) {
  configProduct.value = p
  const cfg = p.collection_config || {}
  configForm.value = {
    platform: cfg.platform || '',
    methods: cfg.methods || [],
    default_method: cfg.default_method || '',
    login_url: cfg.implementation?.login_url || '',
    capture: cfg.implementation?.capture || '',
  }
  activeTab.value = 'config'
}

async function saveConfig() {
  if (!configProduct.value) return
  savingConfig.value = true
  const cfg = {
    platform: configForm.value.platform,
    methods: configForm.value.methods,
    default_method: configForm.value.default_method,
    implementation: {
      login_url: configForm.value.login_url,
      capture: configForm.value.capture,
    },
  }
  try {
    await api.put(`/api/admin/product-configs/${configProduct.value.id}?collection_config=${encodeURIComponent(JSON.stringify(cfg))}`, {})
    showToast('采集配置已保存')
    configProduct.value = null
    await loadProducts()
  } catch (e: any) {
    showToast(`保存失败: ${e.message || e}`, 'error')
  } finally { savingConfig.value = false }
}

// ── Supplier Authorization ──
const authProduct = ref<any>(null)
const authSuppliers = ref<any[]>([])
const loadingAuth = ref(false)
const showAddAuth = ref(false)
const addAuthForm = ref({ supplier_id: null as number | null })
const addingAuth = ref(false)

async function openAuth(p: any) {
  authProduct.value = p
  activeTab.value = 'suppliers'
  await loadAuthSuppliers()
}

async function loadAuthSuppliers() {
  if (!authProduct.value) return
  loadingAuth.value = true
  try {
    const r = await api.get<{code: number; data: any[]}>(`/api/admin/products/${authProduct.value.id}/suppliers`)
    authSuppliers.value = r.data || []
  } catch { authSuppliers.value = [] }
  finally { loadingAuth.value = false }
}

function openAddAuth() {
  addAuthForm.value = { supplier_id: null }
  showAddAuth.value = true
}

async function confirmAddAuth() {
  if (!addAuthForm.value.supplier_id) { showToast('请选择供应商', 'error'); return }
  addingAuth.value = true
  try {
    await api.post(`/api/admin/products/${authProduct.value!.id}/suppliers?supplier_id=${addAuthForm.value.supplier_id}`, {})
    showToast('授权成功')
    showAddAuth.value = false
    await loadAuthSuppliers()
  } catch (e: any) {
    showToast(`授权失败: ${e.message || e}`, 'error')
  } finally { addingAuth.value = false }
}

async function toggleSupplierAuth(sid: number, currentlyActive: boolean) {
  try {
    if (currentlyActive) {
      await api.delete(`/api/admin/products/${authProduct.value!.id}/suppliers/${sid}`, {})
      showToast('已取消授权')
    } else {
      await api.post(`/api/admin/products/${authProduct.value!.id}/suppliers?supplier_id=${sid}`, {})
      showToast('已重新授权')
    }
    await loadAuthSuppliers()
  } catch (e: any) {
    showToast(`操作失败: ${e.message || e}`, 'error')
  }
}

async function toggleStatus(pid: number, active: boolean) {
  await api.put(`/api/admin/product-configs/${pid}/status?status=${active}`, {})
  await loadProducts()
}

// Supplier dropdown (un-authorized only)
const availableSuppliers = computed(() => {
  const authedIds = new Set(authSuppliers.value.map((s: any) => s.supplier_id || s.id))
  return suppliers.value.filter((s: any) => !authedIds.has(s.id))
})

onMounted(async () => {
  await Promise.all([loadProducts(), loadSuppliers()])
  filterProducts()
})

// ── Category Icon/Color Mapping ──
const iconMap: Record<string, any> = {
  '电商卡券': Gift,
  '电商': Gift,
  '卡券': Gift,
  '游戏': Gamepad2,
  '点卡': Gamepad2,
  '视频': Film,
  '会员': Film,
  '话费': Smartphone,
  '充值': Smartphone,
}

const colorMap: Record<string, { bg: string; ring: string }> = {
  '电商卡券': { bg: '#3b82f6', ring: '#60a5fa' },  // blue
  '电商': { bg: '#3b82f6', ring: '#60a5fa' },
  '卡券': { bg: '#3b82f6', ring: '#60a5fa' },
  '游戏': { bg: '#22c55e', ring: '#4ade80' },     // green
  '点卡': { bg: '#22c55e', ring: '#4ade80' },
  '视频': { bg: '#a855f7', ring: '#c084fc' },     // purple
  '会员': { bg: '#a855f7', ring: '#c084fc' },
  '话费': { bg: '#f97316', ring: '#fb923c' },     // orange
  '充值': { bg: '#f97316', ring: '#fb923c' },
}

function categoryIcon(cat: string): any {
  if (!cat) return Package
  for (const [keyword, icon] of Object.entries(iconMap)) {
    if (cat.includes(keyword)) return icon
  }
  return Package
}

function categoryColor(cat: string): { bg: string; ring: string } {
  if (!cat) return { bg: '#6b7280', ring: '#9ca3af' }
  for (const [keyword, colors] of Object.entries(colorMap)) {
    if (cat.includes(keyword)) return colors
  }
  return { bg: '#6b7280', ring: '#9ca3af' } // gray fallback
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold text-[var(--color-text)]">商品管理</h2>
        <p class="text-sm text-[var(--color-text-muted)]">统一管理商品、采集配置与供应商授权</p>
      </div>
      <button class="btn btn-primary btn-sm" @click="openCreate">
        <Plus class="w-4 h-4" /> 新建商品
      </button>
    </div>

    <!-- Tab Navigation -->
    <div class="flex gap-1 border-b border-[var(--color-border)]">
      <button
        :class="['px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-[1px]',
          activeTab === 'list' ? 'border-[var(--color-accent)] text-[var(--color-accent)]' : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]']"
        @click="activeTab = 'list'">商品列表</button>
      <button
        :class="['px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-[1px]',
          activeTab === 'config' && configProduct ? 'border-[var(--color-accent)] text-[var(--color-accent)]' : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]']"
        @click="activeTab = 'config'">采集配置</button>
      <button
        :class="['px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-[1px]',
          activeTab === 'suppliers' && authProduct ? 'border-[var(--color-accent)] text-[var(--color-accent)]' : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]']"
        @click="activeTab = 'suppliers'">供应商授权</button>
    </div>

    <!-- ── Tab 1: Product List ── -->
    <div v-show="activeTab === 'list'" class="space-y-4">
      <div class="flex items-center gap-2">
        <div class="relative flex-1 max-w-sm">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-muted)]" />
          <input v-model="searchKeyword" @input="filterProducts"
            class="w-full pl-9 pr-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm"
            placeholder="搜索商品名称或分类..." />
        </div>
      </div>

      <div class="card p-0 overflow-hidden">
        <div v-if="loading" class="p-6 text-sm text-[var(--color-text-muted)]">加载中...</div>
        <table v-else class="w-full text-sm">
          <thead>
            <tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
              <th class="w-10 p-3 text-xs font-semibold text-[var(--color-text-muted)]"></th>
              <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">ID</th>
              <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">商品名称</th>
              <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">分类</th>
              <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">面值</th>
              <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">建议售价</th>
              <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">采集平台</th>
              <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">状态</th>
              <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in filteredProducts" :key="p.id"
              class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
              <td class="p-3">
                <div class="w-8 h-8 rounded-full flex items-center justify-center"
                  :style="{ background: categoryColor(p.category).bg }">
                  <component :is="categoryIcon(p.category)" class="w-4 h-4 text-white" />
                </div>
              </td>
              <td class="p-3 text-[var(--color-text-muted)] font-mono text-xs">{{ p.id }}</td>
              <td class="p-3 font-medium">{{ p.name }}</td>
              <td class="p-3 text-[var(--color-text-muted)]">{{ p.category || '-' }}</td>
              <td class="p-3 text-right font-mono">{{ p.face_value }}</td>
              <td class="p-3 text-right font-mono">{{ p.suggested_price }}</td>
              <td class="p-3">
                <span v-if="p.collection_config?.platform" class="chip chip-blue">{{ p.collection_config.platform }}</span>
                <span v-else class="text-[var(--color-text-muted)] text-xs">未配置</span>
              </td>
              <td class="p-3">
                <Badge :status="p.status === 'ACTIVE' ? 'success' : 'inactive'">
                  {{ p.status === 'ACTIVE' ? '启用' : '停用' }}
                </Badge>
              </td>
              <td class="p-3 text-right space-x-1">
                <button class="btn btn-outline btn-sm" @click="openEdit(p)" title="编辑">
                  <Edit class="w-3 h-3" />
                </button>
                <button class="btn btn-outline btn-sm" @click="openConfig(p)" title="采集配置">
                  <Settings class="w-3 h-3" />
                </button>
                <button class="btn btn-outline btn-sm" @click="openAuth(p)" title="授权供应商">
                  <UserCheck class="w-3 h-3" />
                </button>
                <button v-if="p.status === 'ACTIVE'" class="btn btn-outline btn-sm" @click="toggleStatus(p.id, false)">停用</button>
                <button v-else class="btn btn-outline btn-sm" @click="toggleStatus(p.id, true)">启用</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!loading && !filteredProducts.length" class="p-6 text-center text-sm text-[var(--color-text-muted)]">
          {{ searchKeyword ? '未搜索到匹配的商品' : '暂无商品，点击上方新建' }}
        </div>
      </div>
    </div>

    <!-- ── Tab 2: Collection Config ── -->
    <div v-show="activeTab === 'config'" class="space-y-4">
      <div v-if="!configProduct" class="card p-6 text-center text-sm text-[var(--color-text-muted)]">
        请先在「商品列表」中点击某商品的「采集配置」按钮
      </div>
      <div v-else class="card p-6 max-w-xl">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-base font-semibold">
            采集配置 — <span class="text-[var(--color-accent)]">{{ configProduct.name }}</span>
          </h3>
          <button class="btn btn-sm btn-outline" @click="configProduct = null; activeTab = 'list'">
            <X class="w-3 h-3" /> 关闭
          </button>
        </div>

        <div class="space-y-4">
          <!-- Target Platform -->
          <div>
            <label class="block text-xs font-semibold text-[var(--color-text-muted)] mb-1.5">目标平台</label>
            <select v-model="configForm.platform"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm">
              <option value="">请选择</option>
              <option v-for="p in platformOptions" :key="p" :value="p">{{ p }}</option>
            </select>
          </div>

          <!-- Collection Methods (checkboxes) -->
          <div>
            <label class="block text-xs font-semibold text-[var(--color-text-muted)] mb-1.5">采集方式（多选）</label>
            <div class="flex flex-wrap gap-3">
              <label v-for="m in methodOptions" :key="m"
                class="flex items-center gap-1.5 text-sm cursor-pointer select-none">
                <input type="checkbox" :value="m" v-model="configForm.methods"
                  class="rounded border-[var(--color-border)] text-[var(--color-accent)]" />
                {{ methodLabels[m] }}
              </label>
            </div>
          </div>

          <!-- Default Method -->
          <div>
            <label class="block text-xs font-semibold text-[var(--color-text-muted)] mb-1.5">默认方式</label>
            <select v-model="configForm.default_method"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm">
              <option value="">自动选择</option>
              <option v-for="m in methodOptions" :key="m" :value="m">{{ methodLabels[m] }}</option>
            </select>
          </div>

          <!-- Implementation Params -->
          <div class="border-t border-[var(--color-border)] pt-4">
            <p class="text-xs font-semibold text-[var(--color-text-muted)] mb-3">实现参数</p>
            <div class="space-y-3">
              <div>
                <label class="block text-xs text-[var(--color-text-muted)] mb-1">登录地址</label>
                <input v-model="configForm.login_url"
                  class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm font-mono"
                  placeholder="https://..." />
              </div>
              <div>
                <label class="block text-xs text-[var(--color-text-muted)] mb-1">捕获方式</label>
                <select v-model="configForm.capture"
                  class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm">
                  <option v-for="o in captureOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
                </select>
              </div>
            </div>
          </div>

          <div class="flex justify-end gap-2 pt-2">
            <button class="btn btn-outline" @click="configProduct = null; activeTab = 'list'">取消</button>
            <button class="btn btn-primary" :disabled="savingConfig" @click="saveConfig">
              {{ savingConfig ? '保存中...' : '保存配置' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Tab 3: Supplier Authorization ── -->
    <div v-show="activeTab === 'suppliers'" class="space-y-4">
      <div v-if="!authProduct" class="card p-6 text-center text-sm text-[var(--color-text-muted)]">
        请先在「商品列表」中点击某商品的「授权供应商」按钮
      </div>
      <div v-else>
        <div class="card p-4">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="text-base font-semibold">
                供应商授权 — <span class="text-[var(--color-accent)]">{{ authProduct.name }}</span>
              </h3>
              <p class="text-xs text-[var(--color-text-muted)] mt-0.5">管理可销售此商品的供应商</p>
            </div>
            <div class="flex gap-2">
              <button class="btn btn-sm btn-outline" @click="authProduct = null; activeTab = 'list'">
                <X class="w-3 h-3" /> 关闭
              </button>
              <button class="btn btn-primary btn-sm" @click="openAddAuth">
                <Plus class="w-4 h-4" /> 添加授权
              </button>
            </div>
          </div>

          <div v-if="loadingAuth" class="text-sm text-[var(--color-text-muted)] py-4">加载中...</div>
          <table v-else class="w-full text-sm">
            <thead>
              <tr class="border-b border-[var(--color-border)] bg-[var(--color-bg)]/50">
                <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">供应商</th>
                <th class="text-left p-3 text-xs font-semibold text-[var(--color-text-muted)]">状态</th>
                <th class="text-right p-3 text-xs font-semibold text-[var(--color-text-muted)]">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in authSuppliers" :key="s.id || s.supplier_id"
                class="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/30">
                <td class="p-3 font-medium">{{ s.supplier_name || s.name || '-' }}</td>
                <td class="p-3">
                  <Badge :status="s.status === 'ACTIVE' ? 'success' : 'inactive'">
                    {{ s.status === 'ACTIVE' ? '已授权' : '已取消' }}
                  </Badge>
                </td>
                <td class="p-3 text-right">
                  <button
                    class="btn btn-sm"
                    :class="s.status === 'ACTIVE' ? 'btn-outline' : 'btn-primary'"
                    @click="toggleSupplierAuth(s.id || s.supplier_id, s.status === 'ACTIVE')"
                    :title="s.status === 'ACTIVE' ? '取消授权' : '重新授权'">
                    <component :is="s.status === 'ACTIVE' ? ToggleLeft : ToggleRight" class="w-3 h-3" />
                    {{ s.status === 'ACTIVE' ? '停用' : '启用' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="!loadingAuth && !authSuppliers.length" class="py-6 text-center text-sm text-[var(--color-text-muted)]">
            暂无授权供应商，点击「添加授权」
          </div>
        </div>
      </div>
    </div>

    <!-- ── Create/Edit Product Modal ── -->
    <div v-if="showProductForm" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" @click.self="showProductForm = false">
      <div class="card p-6 w-full max-w-md mx-4">
        <h3 class="text-base font-semibold mb-4">{{ productForm.id ? '编辑商品' : '新建商品' }}</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">商品名称</label>
            <input v-model="productForm.name"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm"
              placeholder="例如：京东E卡 100元" />
          </div>
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">分类</label>
            <input v-model="productForm.category"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm"
              placeholder="例如：电子卡券" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs text-[var(--color-text-muted)] mb-1">面值</label>
              <input v-model.number="productForm.face_value" type="number" min="0"
                class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm font-mono" />
            </div>
            <div>
              <label class="block text-xs text-[var(--color-text-muted)] mb-1">采集平台</label>
              <input v-model="productForm.platform"
                class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm"
                placeholder="例如：京东" />
            </div>
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="btn btn-outline" @click="showProductForm = false">取消</button>
          <button class="btn btn-primary" :disabled="savingProduct || !productForm.name" @click="saveProduct">
            {{ savingProduct ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Add Supplier Auth Modal ── -->
    <div v-if="showAddAuth" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" @click.self="showAddAuth = false">
      <div class="card p-6 w-full max-w-sm mx-4">
        <h3 class="text-base font-semibold mb-4">添加供应商授权</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--color-text-muted)] mb-1">选择供应商</label>
            <select v-model.number="addAuthForm.supplier_id"
              class="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm">
              <option :value="null">请选择</option>
              <option v-for="s in availableSuppliers" :key="s.id" :value="s.id">{{ s.name || s.nickname || s.id }}</option>
            </select>
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button class="btn btn-outline" @click="showAddAuth = false">取消</button>
          <button class="btn btn-primary" :disabled="addingAuth || !addAuthForm.supplier_id"
            @click="confirmAddAuth">{{ addingAuth ? '添加中...' : '确认授权' }}</button>
        </div>
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
