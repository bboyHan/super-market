/**
 * 超级市场平台 API 客户端
 *
 * 封装与 Super Market 平台后端的 HTTP 通信。
 * 通过 API Key (auth token) 认证，操作库存和订单。
 */

const DEFAULTS = {
  baseUrl: 'http://localhost:8000',
  timeout: 15000,
}

// ── Types ──

export interface PlatformProduct {
  id: number
  name: string
  category: string
  face_value: number
  settlement_price: number
  collection_config?: Record<string, any>
}

export interface UploadResult {
  accepted: number
  rejected: number
  items: Array<{ id: number; product_id: number; content_preview: string }>
}

export interface InventoryItem {
  id: number
  product_id: number
  product_name: string
  content: string
  status: string
  created_at: string | null
}

export interface PlatformProfile {
  agent_id: number
  supplier_id: number
  agent_name: string
}

// ── API Client ──

export class PlatformApi {
  private baseUrl: string
  private apiKey: string = ''
  private token: string = ''
  private agentId: number = 0

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || DEFAULTS.baseUrl
  }

  setApiKey(key: string) {
    this.apiKey = key
  }

  get isAuthenticated(): boolean {
    return !!this.token
  }

  get currentAgentId(): number {
    return this.agentId
  }

  private async _fetch<T>(path: string, options?: RequestInit): Promise<T> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), DEFAULTS.timeout)
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (this.token) headers['Authorization'] = `Bearer ${this.token}`

      const resp = await fetch(`${this.baseUrl}${path}`, {
        ...options,
        signal: controller.signal,
        headers: { ...headers, ...(options?.headers as Record<string, string>) },
      })
      clearTimeout(timer)

      const body = await resp.json()
      if (body.code !== 0) throw new Error(body.message || `API error: ${body.code}`)
      return body.data
    } catch (e) {
      clearTimeout(timer)
      throw e
    }
  }

  /** 通过 API Key 登录 */
  async login(apiKey: string): Promise<PlatformProfile> {
    this.apiKey = apiKey
    const data = await this._fetch<{ token: string; agent_id: number; supplier_id: number; agent_name: string }>(
      '/api/terminal/auth-token-login',
      { method: 'POST', body: JSON.stringify({ api_key: apiKey }) }
    )
    this.token = data.token
    this.agentId = data.agent_id
    return data
  }

  /** 获取代理商可用的货品列表 */
  async getProducts(): Promise<PlatformProduct[]> {
    return this._fetch('/api/terminal/products')
  }

  /** 上传库存 */
  async uploadInventory(productId: number, items: string[]): Promise<UploadResult> {
    return this._fetch('/api/terminal/inventory/upload', {
      method: 'POST',
      body: JSON.stringify({
        items: items.map(content => ({ product_id: productId, content })),
      }),
    })
  }

  /** 获取库存列表 */
  async getInventory(productId?: number, status?: string): Promise<{ items: InventoryItem[]; total: number }> {
    let path = '/api/terminal/inventory?limit=100'
    if (productId) path += `&product_id=${productId}`
    if (status) path += `&status=${status}`
    return this._fetch(path)
  }

  /** 获取库存汇总 */
  async getInventorySummary(): Promise<Array<{ product_id: number; product_name: string; total: number; available: number; used: number }>> {
    return this._fetch('/api/terminal/inventory/summary')
  }

  /** 删除库存 */
  async deleteInventory(itemId: number): Promise<void> {
    await this._fetch(`/api/terminal/inventory/${itemId}`, { method: 'DELETE' })
  }

  /** 检查连接 */
  async healthCheck(): Promise<boolean> {
    try {
      await this._fetch('/api/terminal/products')
      return true
    } catch {
      return false
    }
  }
}

export const platformApi = new PlatformApi()
