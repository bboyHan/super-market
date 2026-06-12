const { contextBridge, ipcRenderer } = require('electron');

/**
 * DataProbe Agent Terminal — Preload Script
 *
 * Exposes DataProbe and platform APIs to the Vue renderer.
 * Also injected into collector BrowserView for postMessage interception.
 */

contextBridge.exposeInMainWorld('electronAPI', {
  // ── DataProbe Engine Status ──
  getStatus: () => ipcRenderer.invoke('get-status'),

  // ── Investigation (Easy Mode) ──
  startInvestigation: (target) => ipcRenderer.invoke('start-investigation', target),
  stopInvestigation: () => ipcRenderer.invoke('stop-investigation'),
  getEvidence: () => ipcRenderer.invoke('get-evidence'),
  getSession: () => ipcRenderer.invoke('get-session'),
  getData: () => ipcRenderer.invoke('get-data'),

  // ── Rules ──
  getRules: () => ipcRenderer.invoke('get-rules'),

  // ── Built-in Browser ──
  openBrowser: (url) => ipcRenderer.invoke('open-browser', url),
  closeBrowser: () => ipcRenderer.invoke('close-browser'),

  // ── Status Events ──
  onDataProbeStatus: (callback) => {
    ipcRenderer.on('dataprobe-status', (event, data) => callback(data));
  },
  onUrlChanged: (callback) => {
    ipcRenderer.on('url-changed', (event, url) => callback(url));
  },

  // ── Capture Events ──
  captureCredential: (credential) => {
    ipcRenderer.send('capture-credential', credential);
  },
  onCapture: (callback) => {
    ipcRenderer.on('capture', (event, credential) => callback(credential));
  },
});

// ═══════════════════════════════════════════
// postMessage 拦截（BrowserView 内）
// ═══════════════════════════════════════════

if (window.location.origin !== 'http://localhost:5173' &&
    window.location.origin !== 'file://') {

  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (!msg || !msg.action) return;

    const handlers = [
      { action: 'wechat_wapbuy', extract: (m) => m.data?.url },
      { action: 'wechat_buy', extract: (m) => m.data?.info },
      { action: 'mqq_buy', extract: (m) => m.data?.info },
      { action: 'launch_schema', extract: (m) => m.data?.url },
      { action: 'jump_face_url', extract: (m) => m.data?.schemaUrl || m.data?.h5Url },
      { action: 'MidasJSBridge_call', match: (m) => m.data?.cmd === 'launchPaySign',
        extract: (m) => m.data?.params },
    ];

    for (const h of handlers) {
      if (h.action === msg.action && (!h.match || h.match(msg))) {
        const value = h.extract(msg);
        if (value) {
          window.electronAPI?.captureCredential({
            type: 'url',
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
  }, true);
}
