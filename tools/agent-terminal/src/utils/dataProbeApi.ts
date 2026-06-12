/**
 * DataProbe REST API 客户端
 *
 * 封装对 DataProbe 引擎 HTTP API 的调用。
 * 在 Electron 环境中通过 preload bridge 调用；在浏览器中直接 HTTP 调用。
 */

const DEFAULTS = {
  baseUrl: 'http://127.0.0.1:18801',
  timeout: 10000,
}

// ── Types ──

export interface DataProbeStatus {
  status: string
  version: string
  uptime_seconds: number
  credentials_queued: number
  credentials_sent: number
  credentials_failed: number
  active_tls_sessions: number
  total_connections: number
  dns_spoofed: number
  active_connections: number
}

export interface InvestigationResult {
  status: string
  sessionId?: string
  channels?: string[]
  target?: string
  limits?: string[]
}

export interface Evidence {
  ruleName: string
  value: string
  type: string
  locationId: string
  stepIndex: number
  requestUrl: string
  rawSnippet: string
  matchType: string
  confidence: number
  capturedAt: string
  metadata: Record<string, string>
}

export interface SessionSnapshot {
  sessionId: string
  target: string
  startedAt: string
  steps: any[]
}

export interface RuleItem {
  id: string
  name: string
  enabled: boolean
  priority: number
  matcher_count: number
  extractor_count: number
  total_captured: number
  last_matched: string | null
}

// ── API Client ──

export class DataProbeApi {
  private baseUrl: string
  private useElectron: boolean

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || DEFAULTS.baseUrl
    this.useElectron = typeof window !== 'undefined' && !!(window as any).electronAPI
  }

  private async _fetch<T>(path: string, options?: RequestInit): Promise<T> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), DEFAULTS.timeout)

    try {
      const resp = await fetch(`${this.baseUrl}${path}`, {
        ...options,
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json', ...options?.headers },
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      return await resp.json()
    } finally {
      clearTimeout(timer)
    }
  }

  async getStatus(): Promise<DataProbeStatus> {
    if (this.useElectron) {
      return (window as any).electronAPI.getStatus()
    }
    return this._fetch('/status')
  }

  async startInvestigation(target: string): Promise<InvestigationResult> {
    if (this.useElectron) {
      return (window as any).electronAPI.startInvestigation(target)
    }
    return this._fetch('/api/investigate/start', {
      method: 'POST',
      body: JSON.stringify({ target }),
    })
  }

  async stopInvestigation(): Promise<{ status: string }> {
    if (this.useElectron) {
      return (window as any).electronAPI.stopInvestigation()
    }
    return this._fetch('/api/investigate/stop', { method: 'POST' })
  }

  async getEvidence(): Promise<{ items: Evidence[] }> {
    if (this.useElectron) {
      return (window as any).electronAPI.getEvidence()
    }
    return this._fetch('/api/evidence')
  }

  async getSession(): Promise<SessionSnapshot | null> {
    if (this.useElectron) {
      return (window as any).electronAPI.getSession()
    }
    return this._fetch('/api/session')
  }

  async getData(): Promise<{ items: any[]; total: number }> {
    if (this.useElectron) {
      return (window as any).electronAPI.getData()
    }
    return this._fetch('/data')
  }

  async getRules(): Promise<{ count: number; rules: RuleItem[] }> {
    if (this.useElectron) {
      return (window as any).electronAPI.getRules()
    }
    return this._fetch('/rules')
  }

  async createRule(rule: any): Promise<{ status: string; id: string }> {
    return this._fetch('/rules', {
      method: 'POST',
      body: JSON.stringify(rule),
    })
  }

  async deleteRule(id: string): Promise<void> {
    await this._fetch(`/rules/${encodeURIComponent(id)}`, { method: 'DELETE' })
  }

  async ingestData(credential: any): Promise<{ status: string; id: string }> {
    return this._fetch('/api/capture/ingest', {
      method: 'POST',
      body: JSON.stringify(credential),
    })
  }
}

export const dataProbeApi = new DataProbeApi()
