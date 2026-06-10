/**
 * Agent Terminal — Popup UI 逻辑
 */

document.addEventListener('DOMContentLoaded', () => {
  // ── 获取状态 ──
  function refreshState() {
    chrome.runtime.sendMessage({ type: 'GET_STATE' }, (state) => {
      if (!state) return;

      // 后端状态
      const dot = document.getElementById('statusDot');
      const statusText = document.getElementById('statusText');
      if (!state.backendReachable) {
        dot.className = 'status-dot offline';
        statusText.textContent = '后端离线';
      } else if (!state.enabled) {
        dot.className = 'status-dot paused';
        statusText.textContent = '已暂停';
      } else {
        dot.className = 'status-dot online';
        statusText.textContent = '采集中';
      }

      document.getElementById('backendStatus').textContent = 
        state.backendReachable ? '后端: 已连接 ✓' : '后端: 未连接 ✗';
      document.getElementById('tabCount').textContent = 
        `${state.activeTabs} 标签页`;
      document.getElementById('captureCount').textContent = 
        state.totalCaptured;
      document.getElementById('platformCount').textContent = 
        (state.recentCredentials.length > 0) ? 
          new Set(state.recentCredentials.map(c => c.platform)).size : 
          (state.activeTabs > 0 ? 1 : 0);
      document.getElementById('queueCount').textContent = 0;

      // 最近采集记录
      const list = document.getElementById('credentialList');
      if (state.recentCredentials.length === 0) {
        list.innerHTML = `
          <div class="empty">等待支付凭证采集...</div>
          <div class="empty" style="font-size:10px;padding-top:0;">
            提示：在 pay.qq.com 上选择 Q币 → 点击支付 → 自动采集
          </div>`;
      } else {
        list.innerHTML = state.recentCredentials.slice(0, 10).map(c => `
          <div class="credential-item">
            <span class="cred-product">${c.product || '未知'}</span>
            <span class="cred-type">${c.type}</span>
            <div class="cred-value">${(c.value || '').substring(0, 80)}${(c.value || '').length > 80 ? '...' : ''}</div>
            <div class="cred-time">${new Date(c.timestamp || c.captured_at).toLocaleTimeString()} · ${c.platform}</div>
          </div>
        `).join('');
      }
    });
  }

  refreshState();
  setInterval(refreshState, 2000);
});
