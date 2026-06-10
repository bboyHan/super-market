const { contextBridge, ipcRenderer } = require('electron');

/**
 * Agent Terminal — Preload Script
 * 
 * Exposes collector API to renderer (Vue app).
 * Also injected into collector BrowserView to intercept postMessage.
 */

contextBridge.exposeInMainWorld('electronAPI', {
  // ── Collector status ──
  getStatus: () => ipcRenderer.invoke('get-collector-status'),
  
  // ── Pipeline control ──
  openBrowser: (url) => ipcRenderer.invoke('open-collector-browser', url),
  startMitm: () => ipcRenderer.invoke('start-mitm'),
  stopMitm: () => ipcRenderer.invoke('stop-mitm'),

  // ── Capture event ──
  onCapture: (callback) => {
    ipcRenderer.on('capture', (event, credential) => callback(credential));
  },
  captureCredential: (credential) => {
    ipcRenderer.send('capture-credential', credential);
  },

  // ── URL change events ──
  onUrlChanged: (callback) => {
    ipcRenderer.on('url-changed', (event, url) => callback(url));
  },
});

// ═══════════════════════════════════════════
// postMessage Interception（用于 BrowserView）
// ═══════════════════════════════════════════

// 仅在 BrowserView 中执行，不在主窗口执行
if (window.location.origin !== 'http://localhost:5173' && 
    window.location.origin !== 'file://') {
  
  // postMessage 捕获阶段拦截
  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (!msg || !msg.action) return;

    // 腾讯 Midas 支付拦截
    const handlers = [
      { action: 'wechat_wapbuy', extract: (m) => m.data?.url },
      { action: 'wechat_buy', extract: (m) => m.data?.info },
      { action: 'mqq_buy', extract: (m) => m.data?.info },
      { action: 'launch_schema', extract: (m) => m.data?.url },
      { action: 'MidasJSBridge_call', match: (m) => m.data?.cmd === 'launchPaySign',
        extract: (m) => m.data?.params },
    ];

    for (const h of handlers) {
      if (h.action === msg.action && (!h.match || h.match(msg))) {
        const value = h.extract(msg);
        if (value) {
          window.electronAPI?.captureCredential({
            type: 'payment_url',
            value: typeof value === 'string' ? value : JSON.stringify(value),
            platform: 'qq_midas',
            product: 'Q币',
            source: 'postmessage',
            origin: event.origin,
            url: window.location.href,
            captured_at: new Date().toISOString(),
          });
        }
        break;
      }
    }
  }, true); // 捕获阶段
}
