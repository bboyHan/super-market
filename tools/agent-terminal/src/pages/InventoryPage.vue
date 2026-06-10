<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useInventoryStore, type InventoryItem } from '@/stores/inventory'

const inventory = useInventoryStore()

const filterTabs = [
  { id: 'all', label: '全部' },
  { id: 'collected', label: '已采集' },
  { id: 'uploaded', label: '已上传' },
  { id: 'consumed', label: '已消耗' },
]

// ── 详情弹窗 ──
const detailItem = ref<InventoryItem | null>(null)
const detailVisible = ref(false)

function showDetail(item: InventoryItem) {
  detailItem.value = item
  detailVisible.value = true
}

function closeDetail() {
  detailVisible.value = false
  detailItem.value = null
}

// ── 复制 ──
function copyText(text: string) {
  navigator.clipboard.writeText(text).catch(() => {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  })
}

// ── 批量上传 ──
const uploading = ref(false)
async function batchUpload() {
  if (uploading.value) return
  uploading.value = true
  try {
    const { success, errors } = await inventory.uploadToPlatform()
    // toast-style feedback — DOM-based
    showToast(`上传完成：成功 ${success} 条${errors > 0 ? `，失败 ${errors} 条` : ''}`)
  } catch (e: any) {
    showToast('上传失败: ' + (e?.message || '网络错误'))
  } finally {
    uploading.value = false
  }
}

// ── 批量删除 ──
async function batchDelete() {
  const count = inventory.selectedIds.size
  if (!confirm(`确认删除选中的 ${count} 条库存？此操作不可撤销。`)) return
  try {
    const deleted = await inventory.deleteSelected()
    showToast(`已删除 ${deleted} 条记录`)
  } catch (e: any) {
    showToast('删除失败: ' + (e?.message || '网络错误'))
  }
}

// ── 单条操作 ──
async function uploadSingle(item: InventoryItem) {
  inventory.selectedIds = new Set([item.resource_id])
  uploading.value = true
  try {
    const { success, errors } = await inventory.uploadToPlatform()
    if (success > 0) showToast('上传成功')
    else showToast('上传失败')
  } catch (e: any) {
    showToast('上传失败: ' + (e?.message || '网络错误'))
  } finally {
    uploading.value = false
  }
}

async function deleteSingle(item: InventoryItem) {
  if (!confirm('确认删除此条记录？')) return
  inventory.selectedIds = new Set([item.resource_id])
  try {
    await inventory.deleteSelected()
    showToast('已删除')
  } catch (e: any) {
    showToast('删除失败')
  }
}

// ── Toast 通知 ──
const toastMsg = ref('')
const toastVisible = ref(false)
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(msg: string) {
  toastMsg.value = msg
  toastVisible.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastVisible.value = false
  }, 3000)
}

// ── 智能排序：待上传的排前面 → 已消耗的排后面 ──
const sortedItems = computed(() => {
  const order: Record<string, number> = { collected: 0, uploaded: 1, consumed: 2 }
  return [...inventory.filteredItems].sort((a, b) => {
    const oa = order[a.status] ?? 99
    const ob = order[b.status] ?? 99
    if (oa !== ob) return oa - ob
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
})

onMounted(() => {
  inventory.fetchInventory()
})
</script>

<template>
  <div class="inventory-page">

    <!-- ── 顶部统计条 ── -->
    <div class="stat-bar">
      <div class="stat-item">
        <span class="stat-value">{{ inventory.totalCount }}</span>
        <span class="stat-label">库存总量</span>
      </div>
      <div class="stat-divider" />
      <div class="stat-item">
        <span class="stat-value yellow">{{ inventory.collectedCount }}</span>
        <span class="stat-label">待上传</span>
      </div>
      <div class="stat-divider" />
      <div class="stat-item">
        <span class="stat-value green">{{ inventory.uploadedCount }}</span>
        <span class="stat-label">已上传</span>
      </div>
      <div class="stat-divider" />
      <div class="stat-item">
        <span class="stat-value gray">{{ inventory.consumedCount }}</span>
        <span class="stat-label">已消耗</span>
      </div>
    </div>

    <!-- ── 筛选栏 ── -->
    <div class="card filter-card">
      <div class="filter-row">
        <div class="filter-tabs">
          <button
            v-for="tab in filterTabs"
            :key="tab.id"
            class="filter-tab"
            :class="{ active: inventory.filterStatus === tab.id }"
            @click="inventory.setFilter(tab.id)"
          >{{ tab.label }}</button>
        </div>
        <div class="search-box">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input v-model="inventory.searchQuery" class="input search-input" placeholder="搜索资源ID或内容…" />
        </div>
      </div>
    </div>

    <!-- ── 批量操作栏 ── -->
    <div v-if="inventory.selectedIds.size > 0" class="batch-bar">
      <span class="batch-count">已选 {{ inventory.selectedIds.size }} 项</span>
      <div class="batch-actions">
        <button
          class="btn btn-sm btn-primary"
          :disabled="uploading"
          @click="batchUpload"
        >
          {{ uploading ? '上传中…' : '上传到平台' }}
        </button>
        <button class="btn btn-sm btn-danger" @click="batchDelete">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
          删除
        </button>
        <button class="btn btn-sm btn-outline" @click="inventory.selectedIds = new Set()">
          取消选择
        </button>
      </div>
    </div>

    <!-- ── 加载中 ── -->
    <div v-if="inventory.loading" class="loading-state">
      <div class="spinner" />
      <span>加载中…</span>
    </div>

    <!-- ── 空状态 ── -->
    <div v-else-if="inventory.items.length === 0" class="empty-state">
      <svg class="empty-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)"
        stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      </svg>
      <p class="empty-title">暂无库存</p>
      <p class="empty-desc">去「采集任务」页面创建新的采集任务，凭证会自动存入库存</p>
      <button class="btn btn-primary" @click="$router.push('/tasks')">去创建采集任务</button>
    </div>

    <!-- ── 库存列表（卡片视图） ── -->
    <div v-else class="inventory-grid">
      <div
        v-for="item in sortedItems"
        :key="item.resource_id"
        class="card inventory-card"
        :class="{ 'card-selected': inventory.selectedIds.has(item.resource_id) }"
      >

        <!-- 选择和状态指示 -->
        <div class="card-select">
          <input
            type="checkbox"
            :checked="inventory.selectedIds.has(item.resource_id)"
            @change="
              inventory.selectedIds.has(item.resource_id)
                ? inventory.selectedIds.delete(item.resource_id)
                : inventory.selectedIds.add(item.resource_id)
            "
            class="checkbox"
          />
        </div>

        <!-- 二维码图片预览 -->
        <div
          v-if="inventory.isImage(item.value)"
          class="card-qr"
          @click="showDetail(item)"
        >
          <img :src="item.value" alt="二维码" class="qr-thumb" />
        </div>

        <!-- 链接/卡密图标 -->
        <div
          v-else
          class="card-icon"
          @click="showDetail(item)"
        >
          <svg v-if="item.value.startsWith('http')" width="28" height="28" viewBox="0 0 24 24" fill="none"
            stroke="var(--accent-primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
          <svg v-else width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--accent-yellow)" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <line x1="3" y1="9" x2="21" y2="9" />
            <line x1="9" y1="21" x2="9" y2="9" />
          </svg>
        </div>

        <!-- 信息区 -->
        <div class="card-info" @click="showDetail(item)">
          <div class="card-title-row">
            <span class="card-title">{{ inventory.productLabel(item.platform, item.product_id) }}</span>
            <span class="card-type-badge">{{ inventory.resourceTypeLabel(item.resource_type) }}</span>
            <span class="badge" :class="inventory.statusClass(item.status)">
              {{ inventory.statusLabel(item.status) }}
            </span>
          </div>
          <div class="card-meta">
            <span class="card-time">{{ inventory.formatTime(item.created_at) }}</span>
            <span v-if="item.uploaded_at" class="card-upload-info">上传: {{ inventory.formatTime(item.uploaded_at) }}</span>
          </div>
          <div class="card-preview">
            <span class="preview-text">{{ item.content_preview }}</span>
            <span v-if="item.value.length > 60 && !inventory.isImage(item.value)" class="preview-more">查看详情</span>
          </div>
        </div>

        <!-- 操作区 -->
        <div class="card-actions">
          <button
            v-if="item.status === 'collected'"
            class="btn btn-sm btn-primary"
            @click="uploadSingle(item)"
            title="上传到平台"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            上传
          </button>
          <button
            class="btn btn-sm btn-outline"
            @click="copyText(item.value)"
            title="复制内容"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          </button>
          <button
            v-if="item.status === 'collected'"
            class="btn btn-sm btn-danger"
            @click="deleteSingle(item)"
            title="删除"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- ── Toast ── -->
    <Transition name="toast">
      <div v-if="toastVisible" class="toast">{{ toastMsg }}</div>
    </Transition>

    <!-- ── 详情弹窗 ── -->
    <Transition name="modal">
      <div v-if="detailVisible && detailItem" class="modal-overlay" @click.self="closeDetail">
        <div class="modal-card">
          <div class="modal-header">
            <h3 class="modal-title">凭证详情</h3>
            <button class="modal-close" @click="closeDetail">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <!-- 二维码大图 -->
            <div v-if="inventory.isImage(detailItem.value)" class="modal-qr-large">
              <img :src="detailItem.value" alt="二维码" class="qr-large" />
              <p class="modal-hint">扫描此二维码完成支付</p>
            </div>

            <!-- 信息行 -->
            <div class="modal-info-grid">
              <div class="modal-info-row">
                <span class="info-label">货品</span>
                <span class="info-value">{{ inventory.productLabel(detailItem.platform, detailItem.product_id) }}</span>
              </div>
              <div class="modal-info-row">
                <span class="info-label">类型</span>
                <span class="info-value">{{ inventory.resourceTypeLabel(detailItem.resource_type) }}</span>
              </div>
              <div class="modal-info-row">
                <span class="info-label">状态</span>
                <span class="badge" :class="inventory.statusClass(detailItem.status)">{{ inventory.statusLabel(detailItem.status) }}</span>
              </div>
              <div class="modal-info-row">
                <span class="info-label">资源ID</span>
                <span class="info-value mono">{{ detailItem.resource_id }}</span>
              </div>
              <div class="modal-info-row">
                <span class="info-label">任务ID</span>
                <span class="info-value mono">{{ detailItem.task_id }}</span>
              </div>
              <div class="modal-info-row">
                <span class="info-label">采集时间</span>
                <span class="info-value">{{ inventory.formatTime(detailItem.created_at) }}</span>
              </div>
              <div class="modal-info-row" v-if="detailItem.uploaded_at">
                <span class="info-label">上传时间</span>
                <span class="info-value">{{ inventory.formatTime(detailItem.uploaded_at) }}</span>
              </div>
              <div class="modal-info-row" v-if="detailItem.expires_at">
                <span class="info-label">过期时间</span>
                <span class="info-value">{{ inventory.formatTime(detailItem.expires_at) }}</span>
              </div>
            </div>

            <!-- 完整内容 -->
            <div class="modal-content-block">
              <div class="content-block-header">
                <span class="content-block-label">完整内容</span>
                <button class="btn btn-xs btn-outline" @click="copyText(detailItem.value)">
                  复制
                </button>
              </div>
              <pre class="content-block-body">{{ detailItem.value }}</pre>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn btn-outline" @click="copyText(detailItem.value)">复制内容</button>
            <button
              v-if="detailItem.status === 'collected'"
              class="btn btn-primary"
              @click="uploadSingle(detailItem); closeDetail()"
            >
              上传到平台
            </button>
            <button class="btn btn-outline" @click="closeDetail">关闭</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* ── Layout ── */
.inventory-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 1200px;
  position: relative;
}

/* ── 统计条 ── */
.stat-bar {
  display: flex;
  align-items: center;
  gap: 0;
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

.stat-value.yellow { color: var(--accent-yellow); }
.stat-value.green { color: var(--accent-green); }
.stat-value.gray { color: var(--text-secondary); }

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

/* ── 筛选 ── */
.filter-card {
  padding: 10px 16px;
}

.filter-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.filter-tabs {
  display: flex;
  gap: 4px;
}

.filter-tab {
  padding: 5px 12px;
  border-radius: var(--radius-md);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.filter-tab:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.filter-tab.active {
  background: var(--accent-primary);
  color: #fff;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 6px;
}

.search-input {
  width: 200px;
  padding: 5px 10px;
  font-size: 12px;
}

/* ── 批量操作栏 ── */
.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: var(--bg-card);
  border: 1px solid var(--accent-primary);
  border-radius: var(--radius-md);
}

.batch-count {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

.batch-actions {
  display: flex;
  gap: 6px;
}

/* ── 加载状态 ── */
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

.empty-icon {
  opacity: 0.4;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-secondary);
}

.empty-desc {
  font-size: 13px;
  color: var(--text-muted);
  max-width: 300px;
  line-height: 1.5;
}

/* ── 库存卡片网格 ── */
.inventory-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.inventory-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  transition: all 0.2s ease;
  cursor: default;
}

.inventory-card:hover {
  border-color: var(--accent-primary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.card-selected {
  border-color: var(--accent-primary) !important;
  background: var(--accent-primary-bg);
}

/* 选择框 */
.card-select {
  flex-shrink: 0;
}

.checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--accent-primary);
  cursor: pointer;
}

/* 二维码缩略图 */
.card-qr {
  flex-shrink: 0;
  cursor: pointer;
}

.qr-thumb {
  width: 44px;
  height: 44px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  object-fit: cover;
}

/* 链接/卡密图标 */
.card-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 6px;
  background: var(--bg-tertiary);
  cursor: pointer;
}

/* 信息区 */
.card-info {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.card-type-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-tertiary);
  color: var(--text-muted);
  font-weight: 500;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 3px;
}

.card-time {
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.card-upload-info {
  font-size: 11px;
  color: var(--accent-green);
}

.card-preview {
  display: flex;
  align-items: center;
  gap: 6px;
}

.preview-text {
  font-size: 11px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
}

.preview-more {
  font-size: 10px;
  color: var(--accent-primary);
  flex-shrink: 0;
}

/* 操作区 */
.card-actions {
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

/* ── 详情弹窗 ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.modal-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  width: 520px;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  border: 1px solid var(--border-color);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}

.modal-title {
  font-size: 16px;
  font-weight: 600;
}

.modal-close {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}

.modal-close:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.modal-body {
  padding: 20px;
}

/* 大图二维码 */
.modal-qr-large {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  padding: 20px;
  background: #fff;
  border-radius: var(--radius-md);
}

.qr-large {
  width: 200px;
  height: 200px;
  image-rendering: pixelated;
}

.modal-hint {
  font-size: 12px;
  color: var(--text-muted);
}

/* 信息网格 */
.modal-info-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.modal-info-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.info-label {
  font-size: 12px;
  color: var(--text-muted);
  width: 70px;
  flex-shrink: 0;
}

.info-value {
  font-size: 13px;
  color: var(--text-primary);
}

.info-value.mono {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 11px;
  color: var(--text-secondary);
  word-break: break-all;
}

/* 完整内容块 */
.modal-content-block {
  margin-bottom: 12px;
}

.content-block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.content-block-label {
  font-size: 12px;
  color: var(--text-muted);
}

.content-block-body {
  font-size: 11px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 12px;
  max-height: 160px;
  overflow-y: auto;
  word-break: break-all;
  white-space: pre-wrap;
  line-height: 1.4;
  color: var(--text-secondary);
}

.modal-footer {
  display: flex;
  gap: 8px;
  padding: 14px 20px;
  border-top: 1px solid var(--border-color);
  justify-content: flex-end;
}

/* ── Modal 动画 ── */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.25s ease;
}

.modal-enter-active .modal-card,
.modal-leave-active .modal-card {
  transition: transform 0.25s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-card,
.modal-leave-to .modal-card {
  transform: scale(0.95) translateY(10px);
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .card-preview {
    display: none;
  }
  .card-actions {
    flex-direction: column;
    gap: 4px;
  }
}
</style>
