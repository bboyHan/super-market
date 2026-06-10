import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/utils/api'

/**
 * 本地库存项（对应后端 /api/inventory/list 的 resources 字段）
 */
export interface InventoryItem {
  id: number
  resource_id: string
  task_id: string
  platform: string           // 货品类型，如 qq_coin
  product_id: string         // 平台侧货品 ID
  resource_type: string      // qrcode / link / code
  value: string              // 原始内容
  content_preview: string    // 预览截断
  status: 'collected' | 'uploaded' | 'consumed'
  expires_at: string | null
  metadata: string | null    // JSON
  created_at: string
  uploaded_at: string | null
}

export const useInventoryStore = defineStore('inventory', () => {
  // ── 状态 ──
  const items = ref<InventoryItem[]>([])
  const loading = ref(false)
  const selectedIds = ref<Set<string>>(new Set())
  const filterStatus = ref<string>('all')
  const searchQuery = ref('')

  // ── 计算属性 ──
  const totalCount = computed(() => items.value.length)
  const collectedCount = computed(() => items.value.filter(i => i.status === 'collected').length)
  const uploadedCount = computed(() => items.value.filter(i => i.status === 'uploaded').length)
  const consumedCount = computed(() => items.value.filter(i => i.status === 'consumed').length)

  const filteredItems = computed(() => {
    let result = items.value
    if (filterStatus.value !== 'all') {
      result = result.filter(i => i.status === filterStatus.value)
    }
    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase()
      result = result.filter(i =>
        i.resource_id.toLowerCase().includes(q) ||
        i.platform.toLowerCase().includes(q) ||
        i.value.toLowerCase().includes(q)
      )
    }
    return result
  })

  const selectAll = computed({
    get: () => selectedIds.value.size > 0 && selectedIds.value.size === filteredItems.value.length,
    set: (val: boolean) => {
      if (val) {
        selectedIds.value = new Set(filteredItems.value.map(i => i.resource_id))
      } else {
        selectedIds.value = new Set()
      }
    },
  })

  // ── 状态文本映射 ──
  function statusLabel(status: string): string {
    const map: Record<string, string> = {
      collected: '已采集',
      uploaded: '已上传',
      consumed: '已消耗',
    }
    return map[status] || status
  }

  function statusClass(status: string): string {
    const map: Record<string, string> = {
      collected: 'badge-yellow',
      uploaded: 'badge-green',
      consumed: 'badge-gray',
    }
    return map[status] || 'badge-gray'
  }

  // ── 货品名称映射 ──
  function productLabel(platform: string, product_id: string): string {
    const names: Record<string, string> = {
      qq_coin: 'Q币',
      jd_card: '京东E卡',
      game_card: '游戏点卡',
      video_vip: '视频会员',
    }
    return names[platform] || `${platform} #${product_id}`
  }

  // ── 凭证类型标签 ──
  function resourceTypeLabel(type: string): string {
    const map: Record<string, string> = {
      qrcode: '二维码',
      link: '链接',
      code: '卡密',
      credential: '凭证',
    }
    return map[type] || type
  }

  // ── 是否是图片内容 ──
  function isImage(value: string): boolean {
    return value.startsWith('data:image')
  }

  // ── 格式化时间 ──
  function formatTime(t: string | null): string {
    if (!t) return '—'
    return t.replace('T', ' ').substring(0, 19)
  }

  // ── 操作 ──
  async function fetchInventory() {
    loading.value = true
    try {
      const data = await api.get<{ resources?: InventoryItem[] }>('/api/inventory/list')
      items.value = data?.resources || []
    } catch {
      items.value = []
    } finally {
      loading.value = false
    }
  }

  async function uploadToPlatform(): Promise<{ success: number; errors: number }> {
    const ids = Array.from(selectedIds.value)
    if (ids.length === 0) return { success: 0, errors: 0 }

    const result = await api.post<{ uploaded: string[]; errors: any[]; success_count: number; error_count: number }>(
      '/api/inventory/upload-to-platform',
      ids
    )

    // 刷新本地列表
    await fetchInventory()

    selectedIds.value = new Set()
    return {
      success: result?.success_count || 0,
      errors: result?.error_count || 0,
    }
  }

  async function deleteSelected(): Promise<number> {
    const ids = Array.from(selectedIds.value)
    if (ids.length === 0) return 0

    const result = await api.post<{ deleted: number }>('/api/inventory/delete', { resource_ids: ids })
    await fetchInventory()
    selectedIds.value = new Set()
    return result?.deleted || 0
  }

  function setFilter(status: string) {
    filterStatus.value = status
  }

  function setSearch(query: string) {
    searchQuery.value = query
  }

  return {
    // 状态
    items,
    loading,
    selectedIds,
    filterStatus,
    searchQuery,
    // 计算
    totalCount,
    collectedCount,
    uploadedCount,
    consumedCount,
    filteredItems,
    selectAll,
    // 工具函数
    statusLabel,
    statusClass,
    productLabel,
    resourceTypeLabel,
    isImage,
    formatTime,
    // 操作
    fetchInventory,
    uploadToPlatform,
    deleteSelected,
    setFilter,
    setSearch,
  }
})
