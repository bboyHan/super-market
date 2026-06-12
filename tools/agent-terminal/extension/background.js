/**
 * Agent Terminal — Background Service Worker
 * 
 * 职责：
 *   1. 管理内容脚本的注入状态
 *   2. 维护采集计数和状态
 *   3. 可选：桌面通知
 */

let state = {
  enabled: true,
  totalCaptured: 0,
  activeTabs: 0,
  backendReachable: false,
  recentCredentials: [],
};

// ── 采集事件 ──
chrome.runtime.onMessage.addListener((msg, sender) => {
  switch (msg.type) {
    case 'CAPTURED':
      state.totalCaptured = msg.count || state.totalCaptured + 1;
      state.recentCredentials.unshift({
        ...msg.credential,
        timestamp: new Date().toISOString(),
      });
      // 只保留最近100条
      if (state.recentCredentials.length > 100) {
        state.recentCredentials.length = 100;
      }
      break;

    case 'BACKEND_OFFLINE':
      state.backendReachable = false;
      break;

    case 'CONTENT_LOADED':
      state.activeTabs++;
      break;

    case 'NOTIFY':
      // 可选：显示桌面通知
      break;

    case 'GET_STATE':
      return true; // 保持通道打开
  }
});

// ── 标签页关闭时减少计数 ──
chrome.tabs.onRemoved.addListener((tabId) => {
  state.activeTabs = Math.max(0, state.activeTabs - 1);
});

// ── 定期检查后端健康 ──
async function checkBackend() {
  try {
    const resp = await fetch('http://127.0.0.1:18801/status');
    state.backendReachable = resp.ok;
  } catch {
    state.backendReachable = false;
  }
}
setInterval(checkBackend, 15000);
checkBackend();

// ── 供 popup 获取状态 ──
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'GET_STATE') {
    sendResponse(state);
  }
});
