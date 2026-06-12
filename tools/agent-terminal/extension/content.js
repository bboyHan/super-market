/**
 * Agent Terminal — 支付凭证采集器
 * 
 * content.js — 核心拦截脚本
 * 
 * 在捕获阶段 (capture phase) 拦截 postMessage，
 * 在页面自身的 handler 执行之前提取支付凭证。
 * 
 * 三层采集策略：
 *   1. postMessage 拦截（最高优先级）
 *   2. 网络请求拦截（备选）
 *   3. DOM 监控（兜底）
 */

(function() {
  'use strict';

  // Oracle 本地引擎 (默认端口 18801)
  const BACKEND_URL = 'http://127.0.0.1:18801';
  const CAPTURE_API = '/api/capture/ingest';

  // ── 状态 ──
  let captureCount = 0;
  let enabled = true;
  let queuedCredentials = []; // 本地后端不可达时的缓冲队列

  // ── 初始化：等待平台适配器加载 ──
  const platforms = window.__AT_PLATFORMS || [];

  // ── 发送到本地后端 ──
  async function sendToBackend(credential) {
    if (!credential) return;

    try {
      const resp = await fetch(`${BACKEND_URL}${CAPTURE_API}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credential),
      });
      
      if (resp.ok) {
        captureCount++;
        console.log(`[AT] ✅ 已采集 #${captureCount}: ${credential.product} | ${credential.type}`);
        // 通知 background 更新计数
        chrome.runtime.sendMessage({
          type: 'CAPTURED',
          credential,
          count: captureCount,
        });
      } else {
        console.warn(`[AT] ⚠️ 后端返回 ${resp.status}`, credential);
      }
    } catch (err) {
      // 后端不可达，加入缓冲队列
      queuedCredentials.push(credential);
      console.warn(`[AT] ⏸ 后端不可达，已缓冲 ${queuedCredentials.length} 条`);
      chrome.runtime.sendMessage({
        type: 'BACKEND_OFFLINE',
        queued: queuedCredentials.length,
      });
    }
  }

  // ── 策略 1: postMessage 拦截（捕获阶段）──
  // 在页面自身的 message handler 执行之前拦截
  window.addEventListener('message', function(event) {
    if (!enabled) return;
    
    const msg = event.data;
    if (!msg || !msg.action) return;

    // 遍历所有平台的 handler 尝试匹配
    for (const platform of platforms) {
      // 检查 origin
      if (platform.origins) {
        const originMatch = platform.origins.some(o => event.origin.startsWith(o));
        if (!originMatch) continue;
      }

      for (const handler of (platform.messageHandlers || [])) {
        // action 匹配
        if (handler.action !== msg.action) continue;
        
        // 自定义 match 函数校验
        if (handler.match && !handler.match(msg)) continue;

        // extract 提取凭证
        let credential;
        try {
          credential = handler.extract(msg);
        } catch (e) {
          console.error('[AT] extract error:', e);
          continue;
        }

        if (credential) {
          // 补充元数据
          credential.source = 'postmessage';
          credential.origin = event.origin;
          credential.url = window.location.href;
          
          sendToBackend(credential);

          // 通知 background 显示通知
          chrome.runtime.sendMessage({
            type: 'NOTIFY',
            title: `已采集 ${credential.product}`,
            message: `${credential.type}: ${(credential.value || '').substring(0, 60)}...`,
          });

          return; // 一个消息只处理一次
        }
      }
    }
  }, true); // true = 捕获阶段！

  // ── 策略 2: 网络请求拦截 ──
  // 拦截 fetch/XHR 请求中可能的支付凭证

  // 存储请求体用于请求-响应配对（web_save 需要请求体中的 openid）
  const _requestBodies = new Map();

  // ── web_save 专用拦截：捕获请求体 + 响应体 → 带账号信息的支付凭证 ──
  function isWebSave(url) {
    return url.includes('/v1/r/') && url.includes('web_save');
  }

  function parseFormBody(body) {
    if (!body || typeof body !== 'string') return {};
    const params = {};
    body.split('&').forEach(pair => {
      const [k, v] = pair.split('=').map(decodeURIComponent);
      if (k) params[k] = v;
    });
    return params;
  }

  function captureWebSave(requestBody, responseBody, url) {
    const req = parseFormBody(requestBody);
    const openid = req.openid || '';
    const payMethod = req.pay_method || '';
    const offerId = (url.match(/\/v1\/r\/(\d+)\/web_save/) || [])[1] || '';

    // 提取 weixin:// 支付 URL
    const payUrlMatch = responseBody.match(/weixin:\/\/wxpay\/bizpayurl\?pr=[^\s"'}]+/);
    if (!payUrlMatch) return; // 没有微信支付 URL 则不采集

    const credential = {
      type: 'payment_url',
      value: payUrlMatch[0],
      platform: 'qq_midas',
      product: 'Q币',
      product_id: offerId,
      source: 'web_save',
      api_url: url,
      // ⭐ 关键：携带请求体中的 openid 用于账号匹配
      openid: openid,
      pay_method: payMethod,
      body: requestBody,
      captured_at: new Date().toISOString(),
    };

    console.log(`[AT] ✅ 捕获 web_save: openid=${openid.substr(0,8)}... pay_method=${payMethod}`);
    sendToBackend(credential);
  }

  function interceptNetwork() {
    // ── fetch 拦截 ──
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
      const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
      const requestInit = args[1] || {};
      const method = (requestInit.method || 'GET').toUpperCase();
      let requestBody = requestInit.body || '';

      // ── web_save 专用拦截 ──
      if (isWebSave(url) && method === 'POST') {
        // 1) 取出请求体（form data 可能被消费，需提前读取）
        if (!requestBody && args[0] instanceof Request) {
          requestBody = await args[0].clone().text();
        }

        // 2) 发起真实请求
        const response = await originalFetch.apply(this, args);

        // 3) 读取响应体并匹配
        if (response.ok) {
          try {
            const clone = response.clone();
            const text = await clone.text();
            captureWebSave(requestBody, text, url);
          } catch (e) {
            console.warn('[AT] web_save response read error:', e);
          }
        }
        return response;
      }

      // ── 通用平台 API pattern 匹配 ──
      let matchedPlatform = null;
      for (const platform of platforms) {
        for (const pattern of (platform.apiPatterns || [])) {
          if (pattern.test(url)) {
            matchedPlatform = platform;
            break;
          }
        }
        if (matchedPlatform) break;
      }

      if (!matchedPlatform) {
        return originalFetch.apply(this, args);
      }

      const response = await originalFetch.apply(this, args);
      if (!response.ok) return response;

      try {
        const clone = response.clone();
        const text = await clone.text();
        checkResponseForCredentials(text, url, matchedPlatform.name);
      } catch (e) {}

      return response;
    };

    // ── XHR 拦截 ──
    const originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
      this._at_url = typeof url === 'string' ? url : url?.toString() || '';
      this._at_method = method;
      return originalOpen.apply(this, arguments);
    };

    const originalSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function(body) {
      const url = this._at_url || '';
      const method = (this._at_method || 'GET').toUpperCase();
      const xhr = this;

      // web_save 专用拦截（XHR 方式）
      if (isWebSave(url) && method === 'POST') {
        const reqBody = typeof body === 'string' ? body : '';
        xhr.addEventListener('load', function() {
          try {
            if (xhr.status >= 200 && xhr.status < 300) {
              captureWebSave(reqBody, xhr.responseText, url);
            }
          } catch (e) {}
        });
      } else {
        // 通用平台 pattern
        let matchedPlatform = null;
        for (const platform of platforms) {
          for (const pattern of (platform.apiPatterns || [])) {
            if (pattern.test(url)) {
              matchedPlatform = platform;
              break;
            }
          }
          if (matchedPlatform) break;
        }

        if (matchedPlatform) {
          xhr.addEventListener('load', function() {
            try {
              checkResponseForCredentials(xhr.responseText, url, matchedPlatform.name);
            } catch (e) {}
          });
        }
      }

      return originalSend.apply(this, arguments);
    };
  }

  // ── 检查响应中是否包含支付凭证（通用）──
  function checkResponseForCredentials(text, url, platformName) {
    if (!text || text.length > 100000) return;

    // 检查 weixin:// 支付 URL
    const wxPayMatch = text.match(/weixin:\/\/wxpay\/bizpayurl\?pr=[^\s"'}]+/);
    if (wxPayMatch) {
      sendToBackend({
        type: 'payment_url',
        value: wxPayMatch[0],
        platform: platformName,
        product: 'Q币',
        source: 'api_response',
        api_url: url,
        without_openid: true,
        captured_at: new Date().toISOString(),
      });
      return;
    }

    // 检查 https://wx.tenpay.com/ 支付 URL
    const payUrlMatch = text.match(/https?:\/\/wx\.tenpay\.com\/[^\s"']+/);
    if (payUrlMatch) {
      sendToBackend({
        type: 'payment_url',
        value: payUrlMatch[0],
        platform: platformName,
        product: 'Q币',
        source: 'api_response',
        api_url: url,
        captured_at: new Date().toISOString(),
      });
      return;
    }

    // 检查微信支付参数
    if (text.includes('getBrandWCPayRequest') || text.includes('wx_appid')) {
      sendToBackend({
        type: 'payment_params_raw',
        value: text.substring(0, 2000),
        platform: platformName,
        product: 'Q币',
        source: 'api_response',
        api_url: url,
        captured_at: new Date().toISOString(),
      });
    }
  }

  // ── 策略 3: DOM 监控 ──
  function watchDOM() {
    const observer = new MutationObserver((mutations) => {
      if (!enabled) return;

      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          // 检查新增 iframe
          if (node.tagName === 'IFRAME') {
            monitorIframe(node);
          }

          // 检查新增 img 是否包含二维码
          if (node.tagName === 'IMG' && isQrImage(node)) {
            captureQrImage(node);
          }
        }
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  // ── iframe 监控 ──
  function monitorIframe(iframe) {
    try {
      const src = iframe.src || '';
      const payDomains = ['pay.qq.com', 'tenpay.com', 'unipay.qq.com'];
      
      if (payDomains.some(d => src.includes(d))) {
        // 监听 iframe 的 URL 变化
        let lastSrc = src;
        const checkInterval = setInterval(() => {
          try {
            const currentSrc = iframe.src;
            if (currentSrc !== lastSrc) {
              lastSrc = currentSrc;
              sendToBackend({
                type: 'iframe_url',
                value: currentSrc,
                platform: 'QQ Midas',
                product: 'Q币',
                source: 'iframe_monitor',
                captured_at: new Date().toISOString(),
              });
              clearInterval(checkInterval);
            }
          } catch (e) {
            clearInterval(checkInterval);
          }
        }, 500);
      }
    } catch (e) {}
  }

  // ── 二维码检测 ──
  function isQrImage(img) {
    const src = (img.src || '').toLowerCase();
    const alt = (img.alt || '').toLowerCase();
    const cls = (img.className || '').toLowerCase();
    
    return src.includes('qr') || 
           alt.includes('二维码') || 
           alt.includes('qrcode') ||
           cls.includes('qr');
  }

  // ── 二维码截图捕获 ──
  function captureQrImage(img) {
    try {
      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth || 200;
      canvas.height = img.naturalHeight || 200;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0);
      
      const dataUrl = canvas.toDataURL('image/png');
      
      sendToBackend({
        type: 'qr_image',
        value: dataUrl,
        platform: 'QQ Midas',
        product: 'Q币',
        source: 'dom_monitor',
        captured_at: new Date().toISOString(),
      });
    } catch (e) {}
  }

  // ── 缓冲队列重试 ──
  async function flushQueue() {
    if (queuedCredentials.length === 0) return;
    
    const batch = [...queuedCredentials];
    queuedCredentials = [];
    
    for (const cred of batch) {
      await sendToBackend(cred);
    }
  }

  // ── 与 background 通信 ──
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    switch (msg.type) {
      case 'TOGGLE':
        enabled = msg.enabled;
        sendResponse({ enabled });
        break;
      case 'STATUS':
        sendResponse({
          enabled,
          captureCount,
          queuedCount: queuedCredentials.length,
          platformCount: platforms.length,
          url: window.location.href,
        });
        break;
      case 'FLUSH':
        flushQueue().then(() => sendResponse({ flushed: true }));
        return true;
    }
  });

  // ── 初始化 ──
  function init() {
    console.log('[AT] Agent Terminal 已加载');
    console.log(`[AT] 已注册 ${platforms.length} 个平台适配器:`, 
      platforms.map(p => p.name).join(', '));

    // 策略 1: postMessage 拦截 (已在顶部注册)
    // 策略 2: 网络请求拦截
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        interceptNetwork();
        watchDOM();
      });
    } else {
      interceptNetwork();
      watchDOM();
    }

    // 通知 background 已注入
    chrome.runtime.sendMessage({
      type: 'CONTENT_LOADED',
      url: window.location.href,
      platforms: platforms.map(p => p.name),
    });

    // 定期刷新缓冲队列（每30秒）
    setInterval(flushQueue, 30000);
  }

  init();
})();
