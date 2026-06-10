<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useTasksStore } from '@/stores/tasks'
import { api } from '@/utils/api'
import TaskProgress from '@/components/TaskProgress.vue'
import LogViewer from '@/components/LogViewer.vue'

const tasks = useTasksStore()

const availableProducts = ref<any[]>([])
const selectedProductId = ref<number>(0)
const quantity = ref(10)
const loadingProducts = ref(true)

// ── QQ 账号池 ──
const qqAccounts = ref<any[]>([])
const qqCollectionMode = ref<'add' | 'select' | 'batch'>('add')
const selectedAccountId = ref<number>(0)

// ── 执行状态 ──
const collecting = ref(false)
const collectionMethod = ref('')
const collectionPlatform = ref('')
const showManualInput = ref(false)
const manualInputText = ref('')
const manualPreviewItems = ref<{ value: string; type: string }[]>([])
const manualSubmitted = ref(false)
const manualTaskId = ref('')

// ── 任务历史 ──
interface TaskRecord {
  task_id: string
  platform: string
  product_id: string
  quantity: number
  method: string
  status: string
  progress: number
  error_message: string | null
  created_at: string
  completed_at: string | null
}
const taskHistory = ref<TaskRecord[]>([])
const showHistory = ref(false)
const selectedHistoryTask = ref<TaskRecord | null>(null)

const selectedProduct = computed(() => {
  return availableProducts.value.find(p => p.product_id === selectedProductId.value)
})

onMounted(async () => {
  loadingProducts.value = true
  try {
    const res = await api.get('/api/platform/products')
    if (res && res.products) {
      availableProducts.value = res.products
    }
  } catch (e) {
    console.error('Failed to load products:', e)
  }
  loadingProducts.value = false
  // 加载任务历史
  await loadTaskHistory()
})

async function loadTaskHistory() {
  try {
    const data = await api.get<{ tasks: TaskRecord[]; total: number }>('/api/tasks/list')
    taskHistory.value = (data?.tasks || []).slice(0, 20)
  } catch {
    // 静默处理
  }
}

function selectProduct(product: any) {
  selectedProductId.value = product.product_id
  // Reset state when switching products
  collecting.value = false
  showManualInput.value = false
  manualSubmitted.value = false
  // Load QQ accounts if QQ Coin product
  if (isQQCoin(product)) {
    loadQQAccounts()
  }
}

// ── QQ 账号加载 ──
async function loadQQAccounts() {
  try {
    const data = await api.get<{ accounts: any[] }>('/api/accounts/qq')
    qqAccounts.value = (data?.accounts || []).filter((a: any) => a.status === 'ACTIVE')
    if (qqAccounts.value.length > 0) {
      qqCollectionMode.value = 'select'
      selectedAccountId.value = qqAccounts.value[0].id
    } else {
      qqCollectionMode.value = 'add'
      selectedAccountId.value = 0
    }
  } catch {
    qqAccounts.value = []
    qqCollectionMode.value = 'add'
  }
}

// Detect if a product uses QQ Coin collector
function isQQCoin(product: any): boolean {
  return product?.collection_config?.collection_method === 'qq_coin'
}

function getProductBadge(product: any): string {
  if (isQQCoin(product)) return 'QQ扫码'
  return product?.collection_config?.platform || '—'
}

// ── 启动采集 ──────────────────────────────────────────────

async function startCollection() {
  if (!selectedProductId.value || !quantity.value) return

  const config = selectedProduct.value?.collection_config || {}
  const methods = config?.methods || ['manual']
  const method = methods[0] || 'manual'
  const platform = config?.collection_method || config?.platform || 'unknown'

  collectionMethod.value = method
  collectionPlatform.value = platform
  collecting.value = true

  if (isQQCoin(selectedProduct.value)) {
    // QQ Coin: pass mode and account_id to collector
    await startAutoTask(method, platform)
  } else if (method === 'manual') {
    // Manual: create task then show input
    await startManualTask()
  } else {
    // Auto / semi-auto: delegate to appropriate collector
    await startAutoTask(method, platform)
  }
}

async function startManualTask() {
  try {
    const res = await api.post('/api/tasks/create', {
      platform: collectionPlatform.value,
      product_id: String(selectedProductId.value),
      quantity: 1,
      method: 'manual',
      auto_mode: 'assisted',
      account_id: null,
    })
    manualTaskId.value = res.task_id
    showManualInput.value = true
    manualSubmitted.value = false
  } catch (e) {
    console.error('Failed to create task:', e)
    collecting.value = false
  }
}

async function startAutoTask(method: string, platform: string) {
  try {
    const actualPlatform = platform === 'qq_coin' ? 'qq_coin' : platform
    const actualMethod = platform === 'qq_coin' ? 'browser' : method

    // Build task config with QQ mode info
    const taskConfig: any = {
      platform: actualPlatform,
      product_id: String(selectedProductId.value),
      quantity: quantity.value,
      method: actualMethod,
      auto_mode: actualMethod === 'browser' ? 'full' : 'semi',
      account_id: null,
    }

    if (isQQCoin(selectedProduct.value)) {
      // Map front-end mode names to collector mode names
      const modeMap: Record<string, string> = {
        'add': 'add_account',
        'select': 'collect',
        'batch': 'batch_collect',
      }
      taskConfig.mode = modeMap[qqCollectionMode.value] || qqCollectionMode.value
      if (qqCollectionMode.value === 'select') {
        taskConfig.account_id = selectedAccountId.value
      }
    }

    const res = await api.post('/api/tasks/create', taskConfig)
    manualTaskId.value = res.task_id
    showManualInput.value = true
    manualSubmitted.value = false

    // Set up task tracking: create a local task object and start polling
    const taskId = res.task_id
    tasks.currentTask = {
      id: taskId,
      platform: actualPlatform,
      product: selectedProduct.value?.name || '',
      quantity: quantity.value,
      method: actualMethod,
      auto_mode: true,
      status: 'running',
      progress: 0,
      steps: [],
      logs: [],
      created_at: new Date().toISOString(),
    } as any

    // Poll task status every 2s until complete
    const poll = setInterval(async () => {
      try {
        const status = await api.get(`/api/tasks/${taskId}`)
        if (tasks.currentTask) {
          tasks.currentTask.progress = status.progress ?? tasks.currentTask.progress
          tasks.currentTask.status = status.status ?? tasks.currentTask.status
          tasks.currentTask.logs = status.logs ?? tasks.currentTask.logs
          if (status.qr_image) {
            (tasks.currentTask as any).qr_image = status.qr_image
          }
          tasks.currentTask.steps = status.steps ?? tasks.currentTask.steps
          if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
            clearInterval(poll)
          }
        }
      } catch {
        clearInterval(poll)
      }
    }, 2000)
  } catch (e) {
    console.error('Failed to start collection:', e)
    collecting.value = false
  }
}

// ── Manual Input ──────────────────────────────────────────

function previewManualInput() {
  const lines = manualInputText.value.split('\n').map(s => s.trim()).filter(s => s)
  manualPreviewItems.value = lines.map(v => ({
    value: v,
    type: v.startsWith('http') ? '支付链接' :
          v.startsWith('data:image') ? '二维码' :
          /^[A-Za-z0-9]{2,8}[-_][A-Za-z0-9]/.test(v) ? '卡密' : '未知'
  }))
}

async function submitManualInput() {
  if (!manualTaskId.value || manualPreviewItems.value.length === 0) return
  try {
    await api.post(`/api/tasks/${manualTaskId.value}/input`, {
      values: manualPreviewItems.value.map(i => i.value),
    })
    manualSubmitted.value = true
  } catch (e) {
    console.error('Failed to submit input:', e)
  }
}

function resetCollection() {
  collecting.value = false
  showManualInput.value = false
  manualInputText.value = ''
  manualPreviewItems.value = []
  manualSubmitted.value = false
  manualTaskId.value = ''
  selectedProductId.value = 0
  quantity.value = 10
}

function cancelManualInput() {
  showManualInput.value = false
  manualInputText.value = ''
  manualPreviewItems.value = []
  manualSubmitted.value = false
}

// ── 任务历史辅助 ──
function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    running: 'badge-yellow',
    completed: 'badge-green',
    failed: 'badge-red',
    pending: 'badge-gray',
    cancelled: 'badge-gray',
  }
  return map[status] || 'badge-gray'
}

function statusBadgeLabel(status: string): string {
  const map: Record<string, string> = {
    running: '进行中',
    completed: '已完成',
    failed: '失败',
    pending: '等待中',
    cancelled: '已取消',
  }
  return map[status] || status
}

function fmtTime(t: string | null): string {
  if (!t) return '—'
  return t.replace('T', ' ').substring(0, 19)
}
</script>

<template>
  <div class="tasks-page">
    <!-- Step 1: Select Product -->
    <div class="card">
      <h3 class="section-title">选择商品</h3>
      <p class="section-desc">从以下已授权商品中选择要采集的货品</p>

      <div v-if="loadingProducts" class="loading-state">加载中...</div>

      <div v-else class="product-grid">
        <div
          v-for="p in availableProducts"
          :key="p.product_id"
          class="product-card"
          :class="{ selected: selectedProductId === p.product_id }"
          @click="selectProduct(p)"
        >
          <div class="product-name">{{ p.name }}</div>
          <div class="product-meta">
            <span class="meta-face">面值 {{ p.face_value }}</span>
            <span class="meta-price">结算 {{ p.settlement_price }}</span>
          </div>
          <div class="product-config">
            <span class="config-badge">{{ getProductBadge(p) }}</span>
          </div>
          <div class="check-mark" v-if="selectedProductId === p.product_id">✓</div>
        </div>
      </div>
    </div>

    <!-- 任务历史（折叠） -->
    <div class="card history-card">
      <div class="history-header" @click="showHistory = !showHistory">
        <h3 class="section-title" style="margin:0">采集记录</h3>
        <div class="history-count">{{ taskHistory.length }} 条</div>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          :style="{ transform: showHistory ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      <div v-if="showHistory && taskHistory.length === 0" class="history-empty">
        暂无采集记录，发起采集后会自动记录在此
      </div>

      <div v-if="showHistory && taskHistory.length > 0" class="history-list">
        <div
          v-for="t in taskHistory" :key="t.task_id"
          class="history-item"
          :class="{ 'item-selected': selectedHistoryTask?.task_id === t.task_id }"
          @click="selectedHistoryTask = t"
        >
          <div class="history-item-top">
            <span class="history-product">{{ t.platform === 'qq_coin' ? 'Q币' : t.platform }} × {{ t.quantity }}</span>
            <span class="badge" :class="statusBadgeClass(t.status)">{{ statusBadgeLabel(t.status) }}</span>
          </div>
          <div class="history-item-meta">
            <span class="meta-time">{{ fmtTime(t.created_at) }}</span>
            <span v-if="t.status === 'failed' && t.error_message" class="meta-error">{{ t.error_message.substring(0, 40) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 任务历史详情弹窗 -->
    <Transition name="modal">
      <div v-if="selectedHistoryTask" class="modal-overlay" @click.self="selectedHistoryTask = null">
        <div class="modal-card modal-sm">
          <div class="modal-header">
            <h3>任务详情</h3>
            <button class="modal-close" @click="selectedHistoryTask = null">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </button>
          </div>
          <div class="modal-body">
            <div class="detail-row"><span class="detail-label">任务ID</span><span class="detail-value mono">{{ selectedHistoryTask.task_id }}</span></div>
            <div class="detail-row"><span class="detail-label">货品</span><span class="detail-value">{{ selectedHistoryTask.platform === 'qq_coin' ? 'Q币' : selectedHistoryTask.platform }} #{{ selectedHistoryTask.product_id }}</span></div>
            <div class="detail-row"><span class="detail-label">数量</span><span class="detail-value">{{ selectedHistoryTask.quantity }}</span></div>
            <div class="detail-row"><span class="detail-label">方式</span><span class="detail-value">{{ selectedHistoryTask.method }}</span></div>
            <div class="detail-row"><span class="detail-label">状态</span><span class="badge" :class="statusBadgeClass(selectedHistoryTask.status)">{{ statusBadgeLabel(selectedHistoryTask.status) }}</span></div>
            <div class="detail-row"><span class="detail-label">创建时间</span><span class="detail-value">{{ fmtTime(selectedHistoryTask.created_at) }}</span></div>
            <div class="detail-row" v-if="selectedHistoryTask.completed_at"><span class="detail-label">完成时间</span><span class="detail-value">{{ fmtTime(selectedHistoryTask.completed_at) }}</span></div>
            <div class="detail-row" v-if="selectedHistoryTask.error_message">
              <span class="detail-label">错误信息</span>
              <span class="detail-value error-text">{{ selectedHistoryTask.error_message }}</span>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-outline" @click="selectedHistoryTask = null">关闭</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Step 2: Amount + Start -->
    <div v-if="selectedProductId > 0 && !collecting" class="card action-card">
      <div class="action-row">
        <div class="field">
          <label>采集数量</label>
          <input type="number" v-model.number="quantity" min="1" max="200" class="input" />
        </div>
        <div class="field-info">
          <div class="info-row">
            <span class="info-label">采集方式</span>
            <span class="info-value">
              {{ isQQCoin(selectedProduct) ? 'QQ扫码登录 + 浏览器自动化' : (selectedProduct?.collection_config?.methods || ['手动录入']).join(' / ') }}
            </span>
          </div>
          <div class="info-row">
            <span class="info-label">目标平台</span>
            <span class="info-value">{{ isQQCoin(selectedProduct) ? '腾讯充值中心' : (selectedProduct?.collection_config?.platform || '—') }}</span>
          </div>
        </div>
        <button class="btn btn-primary btn-start" @click="startCollection">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
          启动采集
        </button>
      </div>
    </div>

    <!-- Step 2b: QQ Account Mode Selector (when QQ Coin selected) -->
    <div v-if="selectedProductId > 0 && isQQCoin(selectedProduct) && !collecting" class="card qq-mode-card">
      <h3 class="section-title">QQ 账号配置</h3>
      <div class="qq-mode-options">
        <label v-if="qqAccounts.length > 0" class="mode-option" :class="{ active: qqCollectionMode === 'select' }">
          <input type="radio" v-model="qqCollectionMode" value="select" />
          <div class="mode-content">
            <span class="mode-label">使用已有账号</span>
            <span class="mode-desc">从已保存的 {{ qqAccounts.length }} 个有效账号中选择，跳过登录步骤</span>
            <select v-if="qqCollectionMode === 'select'" v-model.number="selectedAccountId" class="input account-select" @click.stop>
              <option v-for="a in qqAccounts" :key="a.id" :value="a.id">
                {{ a.nickname || 'QQ#' + a.id }} {{ a.uin ? '(' + a.uin + ')' : '' }}
              </option>
            </select>
          </div>
        </label>

        <label class="mode-option" :class="{ active: qqCollectionMode === 'add' }">
          <input type="radio" v-model="qqCollectionMode" value="add" />
          <div class="mode-content">
            <span class="mode-label">添加新账号</span>
            <span class="mode-desc">首次扫码登录，完成后自动保存账号凭据，下次可直接使用</span>
          </div>
        </label>

        <label v-if="qqAccounts.length >= 2" class="mode-option" :class="{ active: qqCollectionMode === 'batch' }">
          <input type="radio" v-model="qqCollectionMode" value="batch" />
          <div class="mode-content">
            <span class="mode-label">批量采集</span>
            <span class="mode-desc">轮换使用 {{ qqAccounts.length }} 个有效账号，每个账号生成 {{ Math.max(1, Math.ceil(quantity / qqAccounts.length)) }} 张支付码</span>
          </div>
        </label>
      </div>
    </div>

    <!-- Step 3: Manual Input Interface -->
    <div v-if="showManualInput && !manualSubmitted && collectionMethod === 'manual'" class="card">
      <h3 class="section-title">手动录入 — {{ selectedProduct?.name }}</h3>
      <p class="section-desc">粘贴支付链接、二维码或卡密，每行一个</p>

      <textarea
        v-model="manualInputText"
        class="manual-input"
        rows="6"
        placeholder="https://pay.jd.com/order/xxx&#10;https://pay.jd.com/order/yyy&#10;JD-CARD-XXXX-YYYY"
        @input="previewManualInput"
      ></textarea>

      <div v-if="manualPreviewItems.length > 0" class="preview-list">
        <div v-for="(item, i) in manualPreviewItems" :key="i" class="preview-item">
          <span class="preview-type">{{ item.type }}</span>
          <span class="preview-value">{{ item.value.substring(0, 50) }}{{ item.value.length > 50 ? '...' : '' }}</span>
        </div>
      </div>

      <div class="action-bar">
        <button class="btn btn-primary" @click="submitManualInput" :disabled="manualPreviewItems.length === 0">
          提交 {{ manualPreviewItems.length }} 条
        </button>
        <button class="btn btn-outline" @click="cancelManualInput">取消</button>
      </div>
    </div>

    <!-- Auto-collection in progress -->
    <div v-if="collecting && collectionMethod !== 'manual' && !manualSubmitted" class="card">
      <h3 class="section-title">正在采集 — {{ selectedProduct?.name }}</h3>
      <p class="section-desc">采集方式：{{ collectionMethod }} ｜ 目标平台：{{ collectionPlatform }}</p>
      <div v-if="tasks.currentTask" class="task-progress-inline">
        <!-- QR Code display -->
        <div v-if="(tasks.currentTask as any)?.qr_image" class="qr-display">
          <p class="qr-hint">请用手机 QQ 扫描下方二维码登录</p>
          <img :src="(tasks.currentTask as any).qr_image" class="qr-image" alt="QQ登录二维码" />
          <p class="qr-expiry">二维码有效期为3分钟</p>
        </div>
        <TaskProgress :steps="tasks.currentTask.steps || []" />
        <LogViewer :logs="(tasks.currentTask as any)?.logs || []" :max-height="'200px'" />
      </div>
      <div v-else class="loading-state">任务已提交，等待采集...</div>
    </div>

    <!-- Processing / Result -->
    <div v-if="manualSubmitted" class="card">
      <h3 class="section-title">处理中</h3>
      <div v-if="tasks.currentTask" class="task-progress-inline">
        <TaskProgress :steps="tasks.currentTask.steps || []" />
        <LogViewer :logs="(tasks.currentTask as any)?.logs || []" :max-height="'200px'" />
      </div>
      <div v-else class="success-state">
        <p>提交成功！正在上传到平台...</p>
      </div>
      <button class="btn btn-primary" @click="resetCollection" style="margin-top:12px">继续采集</button>
      <button class="btn btn-outline" @click="resetCollection" style="margin-top:12px;margin-left:8px">返回</button>
    </div>
  </div>
</template>

<style scoped>
.tasks-page{display:flex;flex-direction:column;gap:16px;padding:24px}
.section-title{font-size:14px;font-weight:600;margin-bottom:4px}
.section-desc{font-size:12px;color:var(--text-muted);margin-bottom:16px}
.loading-state,.success-state{padding:24px;text-align:center;color:var(--text-muted);font-size:13px}
.product-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
.product-card{background:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-md);padding:16px;cursor:pointer;transition:all .2s;position:relative}
.product-card:hover{border-color:var(--accent-primary);box-shadow:0 2px 8px rgba(0,0,0,.08)}
.product-card.selected{border-color:var(--accent-primary);background:var(--accent-primary-bg)}
.product-name{font-size:14px;font-weight:600;margin-bottom:6px}
.product-meta{display:flex;gap:10px;font-size:11px;color:var(--text-muted);margin-bottom:8px}
.product-config{display:flex;gap:6px;flex-wrap:wrap}
.config-badge{font-size:10px;padding:2px 8px;border-radius:4px;background:var(--bg-tertiary);color:var(--text-secondary)}
.check-mark{position:absolute;top:8px;right:8px;width:22px;height:22px;border-radius:50%;background:var(--accent-primary);color:#fff;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700}
.action-card{padding:20px}
.action-row{display:flex;align-items:flex-end;gap:20px;flex-wrap:wrap}
.field{display:flex;flex-direction:column;gap:4px;min-width:120px}
.field label{font-size:12px;color:var(--text-muted)}
.input{padding:8px 12px;border:1px solid var(--border-color);border-radius:var(--radius-sm);background:var(--bg-secondary);color:var(--text-primary);font-size:14px;width:100px}
.field-info{display:flex;flex-direction:column;gap:4px;font-size:12px;flex:1}
.info-row{display:flex;gap:8px}
.info-label{color:var(--text-muted);min-width:60px}
.info-value{color:var(--text-primary);font-weight:500}
.btn-start{display:flex;align-items:center;gap:6px;padding:10px 24px;font-size:14px;font-weight:600}
.manual-input{width:100%;padding:12px;border:1px solid var(--border-color);border-radius:var(--radius-sm);background:var(--bg-secondary);color:var(--text-primary);font-size:13px;font-family:var(--font-mono);resize:vertical}
.preview-list{display:flex;flex-direction:column;gap:4px;margin:12px 0}
.preview-item{display:flex;align-items:center;gap:10px;padding:6px 10px;border-radius:4px;background:var(--bg-tertiary);font-size:12px}
.preview-type{font-size:10px;padding:2px 6px;border-radius:3px;background:var(--accent-primary-bg);color:var(--accent-primary);white-space:nowrap}
.preview-value{color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis}
.action-bar{display:flex;gap:8px;margin-top:12px}

/* ── QQ 账号配置 ── */
.qq-mode-card{padding:20px}
.qq-mode-options{display:flex;flex-direction:column;gap:10px}
.mode-option{display:flex;align-items:flex-start;gap:12px;padding:14px 16px;border:1px solid var(--border-color);border-radius:var(--radius-md);cursor:pointer;transition:all .2s;background:var(--bg-secondary)}
.mode-option:hover{border-color:var(--accent-primary);background:var(--bg-hover)}
.mode-option.active{border-color:var(--accent-primary);background:var(--accent-primary-bg)}
.mode-option input[type="radio"]{margin-top:3px;accent-color:var(--accent-primary);flex-shrink:0}
.mode-content{display:flex;flex-direction:column;gap:4px;flex:1}
.mode-label{font-size:14px;font-weight:600;color:var(--text-primary)}
.mode-desc{font-size:12px;color:var(--text-muted);line-height:1.4}
.account-select{width:100%;margin-top:6px;padding:6px 10px;font-size:12px}

/* ── 任务历史 ── */
.history-card{padding:14px 16px;cursor:pointer}
.history-header{display:flex;align-items:center;gap:10px}
.history-count{font-size:11px;color:var(--text-muted);margin-left:auto}
.history-empty{padding:20px 0;text-align:center;font-size:12px;color:var(--text-muted)}
.history-list{display:flex;flex-direction:column;gap:4px;margin-top:12px;max-height:300px;overflow-y:auto}
.history-item{padding:10px 12px;border-radius:var(--radius-sm);cursor:pointer;transition:all .15s}
.history-item:hover{background:var(--bg-hover)}
.item-selected{background:var(--accent-primary-bg);border:1px solid var(--accent-primary)}
.history-item-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:3px}
.history-product{font-size:13px;font-weight:600;color:var(--text-primary)}
.history-item-meta{display:flex;align-items:center;gap:10px}
.meta-time{font-size:11px;color:var(--text-muted);font-family:monospace}
.meta-error{font-size:10px;color:var(--accent-red)}
/* 详情弹窗 */
.detail-row{display:flex;align-items:flex-start;gap:10px;margin-bottom:8px}
.detail-label{font-size:12px;color:var(--text-muted);width:70px;flex-shrink:0}
.detail-value{font-size:13px;color:var(--text-primary)}
.detail-value.mono{font-family:monospace;font-size:11px;word-break:break-all}
.detail-value.error-text{color:var(--accent-red);font-size:12px}
.modal-sm{width:420px}

.qr-display{text-align:center;padding:16px;background:var(--bg-tertiary);border-radius:var(--radius-md);margin-bottom:12px}
.qr-hint{font-size:14px;font-weight:600;color:var(--text-primary);margin-bottom:12px}
.qr-image{width:200px;height:200px;border-radius:8px;border:2px solid var(--border-color);display:inline-block}
.qr-expiry{font-size:11px;color:var(--text-muted);margin-top:8px}
</style>
