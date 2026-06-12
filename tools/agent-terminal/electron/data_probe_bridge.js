/**
 * DataProbe Bridge — 管理 DataProbe 作为 Electron 子进程。
 *
 * 职责：
 *   1. 查找 DataProbe 可执行文件（打包内嵌 / 全局 dotnet / 开发路径）
 *   2. 启动/停止 DataProbe 子进程
 *   3. 封装 REST API 调用（调查、证据、状态）
 *   4. 健康检查 + 自动重启
 */

const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const { app } = require('electron');

class DataProbeBridge {
  constructor(options = {}) {
    this.apiPort = options.apiPort || 18801;
    this.apiHost = options.apiHost || '127.0.0.1';
    this.process = null;
    this._isRunning = false;
    this._healthInterval = null;
    this._onStatusChange = null;
  }

  /** 设置状态变更回调 */
  onStatusChange(callback) {
    this._onStatusChange = callback;
  }

  /** 查找 DataProbe 可执行文件路径 */
  _findDataProbe() {
    const isDev = !app.isPackaged;

    // 开发模式：dotnet run
    if (isDev) {
      const probes = [
        { cmd: 'dotnet', args: ['run', '--project',
          path.join(__dirname, '..', '..', '..', 'data-probe', 'src', 'DataProbe.Api')] },
        { cmd: 'dotnet', args: ['run', '--project',
          path.join(__dirname, '..', '..', '..', 'server', 'oracle', 'src', 'Oracle.Api')] },
      ];
      return probes;
    }

    // 生产模式：打包内嵌的 DataProbe.exe
    return [
      { cmd: path.join(process.resourcesPath, 'data-probe', 'DataProbe.Api.exe'), args: [] },
    ];
  }

  /** 启动 DataProbe 子进程 */
  async start() {
    if (this._isRunning) return true;

    const probes = this._findDataProbe();
    for (const probe of probes) {
      try {
        console.log(`[DataProbe] 尝试启动: ${probe.cmd} ${probe.args.join(' ')}`);

        const args = [
          ...probe.args,
          '--api-port', String(this.apiPort),
        ];

        this.process = spawn(probe.cmd, args, {
          stdio: ['ignore', 'pipe', 'pipe'],
          env: { ...process.env },
        });

        this.process.stdout.on('data', (d) => {
          const msg = d.toString().trim();
          if (msg) console.log(`[DataProbe] ${msg}`);
        });

        this.process.stderr.on('data', (d) => {
          const msg = d.toString().trim();
          if (msg) console.log(`[DataProbe] ${msg}`);
        });

        this.process.on('error', (err) => {
          console.warn(`[DataProbe] 启动失败: ${err.message}`);
          this._isRunning = false;
          this.process = null;
        });

        this.process.on('exit', (code) => {
          console.log(`[DataProbe] 进程退出 (code=${code})`);
          this._isRunning = false;
          this.process = null;
          if (this._onStatusChange) this._onStatusChange(false);
        });

        // 等待服务就绪
        await this._waitForReady(15000);
        this._isRunning = true;
        console.log(`[DataProbe] 启动成功 (端口 ${this.apiPort})`);

        // 启动健康检查
        this._startHealthCheck();
        if (this._onStatusChange) this._onStatusChange(true);
        return true;
      } catch (e) {
        console.warn(`[DataProbe] 尝试失败: ${e.message}`);
        if (this.process) {
          this.process.kill();
          this.process = null;
        }
      }
    }

    console.error('[DataProbe] 所有启动方式均失败');
    return false;
  }

  /** 等待 DataProbe HTTP 服务就绪 */
  _waitForReady(timeoutMs) {
    return new Promise((resolve, reject) => {
      const start = Date.now();
      const check = () => {
        if (Date.now() - start > timeoutMs) {
          reject(new Error('服务启动超时'));
          return;
        }
        this._httpGet('/status')
          .then(() => resolve())
          .catch(() => setTimeout(check, 500));
      };
      check();
    });
  }

  /** 启动定期健康检查（每15秒） */
  _startHealthCheck() {
    this._stopHealthCheck();
    this._healthInterval = setInterval(async () => {
      const ok = await this.healthCheck();
      if (!ok && this._onStatusChange) {
        this._onStatusChange(false);
      }
    }, 15000);
  }

  _stopHealthCheck() {
    if (this._healthInterval) {
      clearInterval(this._healthInterval);
      this._healthInterval = null;
    }
  }

  /** 停止 DataProbe 子进程 */
  async stop() {
    this._stopHealthCheck();
    if (this.process) {
      this.process.kill();
      this.process = null;
    }
    this._isRunning = false;
    if (this._onStatusChange) this._onStatusChange(false);
  }

  // ═════════════════════════════════════════════
  // HTTP API 调用
  // ═════════════════════════════════════════════

  _httpGet(path) {
    return new Promise((resolve, reject) => {
      const req = http.get(`http://${this.apiHost}:${this.apiPort}${path}`, (res) => {
        let data = '';
        res.on('data', (chunk) => data += chunk);
        res.on('end', () => {
          try { resolve(JSON.parse(data)); }
          catch { resolve(data); }
        });
      });
      req.on('error', reject);
      req.setTimeout(5000, () => { req.destroy(); reject(new Error('timeout')); });
    });
  }

  _httpPost(path, body) {
    return new Promise((resolve, reject) => {
      const data = JSON.stringify(body || {});
      const req = http.request({
        hostname: this.apiHost, port: this.apiPort, path, method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) },
      }, (res) => {
        let resp = '';
        res.on('data', (chunk) => resp += chunk);
        res.on('end', () => {
          try { resolve(JSON.parse(resp)); }
          catch { resolve(resp); }
        });
      });
      req.on('error', reject);
      req.setTimeout(10000, () => { req.destroy(); reject(new Error('timeout')); });
      req.write(data);
      req.end();
    });
  }

  /** 健康检查：GET /status */
  async healthCheck() {
    try {
      const status = await this._httpGet('/status');
      return status && (status.status === 'running' || status.status === 'stopped');
    } catch {
      return false;
    }
  }

  /** 获取引擎状态 */
  async getStatus() {
    return await this._httpGet('/status');
  }

  /** 启动调查 */
  async startInvestigation(target, rulePacks = []) {
    return await this._httpPost('/api/investigate/start', {
      target: target,
      rule_packs: rulePacks,
      depth: 'standard',
    });
  }

  /** 停止调查 */
  async stopInvestigation() {
    return await this._httpPost('/api/investigate/stop', {});
  }

  /** 获取调查会话 */
  async getSession() {
    return await this._httpGet('/api/session');
  }

  /** 获取提取的证据 */
  async getEvidence() {
    return await this._httpGet('/api/evidence');
  }

  /** 获取捕获的凭证数据 */
  async getCapturedData() {
    return await this._httpGet('/data');
  }

  /** 注入外部数据（来自 Chrome 扩展等） */
  async ingestData(credential) {
    return await this._httpPost('/api/capture/ingest', credential);
  }

  /** 获取规则列表 */
  async getRules() {
    return await this._httpGet('/rules');
  }

  /** 创建规则 */
  async createRule(rule) {
    return await this._httpPost('/rules', rule);
  }

  /** 删除规则 */
  async deleteRule(id) {
    return new Promise((resolve, reject) => {
      const req = http.request({
        hostname: this.apiHost, port: this.apiPort,
        path: `/rules/${encodeURIComponent(id)}`, method: 'DELETE',
      }, (res) => {
        let data = '';
        res.on('data', (chunk) => data += chunk);
        res.on('end', () => { try { resolve(JSON.parse(data)); } catch { resolve(data); } });
      });
      req.on('error', reject);
      req.end();
    });
  }
}

module.exports = DataProbeBridge;
