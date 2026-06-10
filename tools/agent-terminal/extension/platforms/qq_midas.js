/**
 * QQ Midas 支付平台适配器
 * 
 * 拦截目标：
 *   - pay.qq.com 的 Midas SDK iframe 发往父页面的 postMessage
 *   - wechat_wapbuy → 包含支付 URL（桌面浏览器 fallback）
 *   - wechat_buy    → 包含微信支付参数（appId, timeStamp, nonceStr, package, signType, paySign）
 *   - MidasJSBridge_call → 原生桥调用参数
 * 
 * 参考文档：redesign/01-agent-terminal-product-design.md
 * 
 * 调研结论（2026-06-09）：
 *   - Web 端不存在可直接提取的支付二维码
 *   - 支付二维码由微信/QQ App 原生生成
 *   - 桌面浏览器中 fallback 到 location.href = 支付 URL
 *   - 这个 URL 就是最终要采集的凭证
 */

window.__AT_PLATFORMS = window.__AT_PLATFORMS || [];
window.__AT_PLATFORMS.push({
  name: 'QQ Midas',
  
  // 匹配的页面来源
  origins: [
    'https://pay.qq.com',
    'https://graph.qq.com',
    'https://api.unipay.qq.com',
  ],

  // ── postMessage 拦截规则 ──
  // 匹配规则: { action, match(msg) → bool?, extract(msg) → credential }
  messageHandlers: [

    // ── 规则 1: 微信支付 URL 跳转（桌面浏览器 fallback）──
    // iframe 检测到桌面环境 → 通过跳转 URL 方式支付
    {
      action: 'wechat_wapbuy',
      extract(msg) {
        const url = msg.data?.url;
        if (!url) return null;
        return {
          type: 'payment_url',
          value: url,
          platform: 'qq_midas',
          product: this._detectProduct(url),
          captured_at: new Date().toISOString(),
        };
      },
    },

    // ── 规则 2: 微信支付参数（原生桥调用）──
    // 参数中包含 wx_appid, wx_time, wx_nonce, wx_package, wx_sign
    {
      action: 'wechat_buy',
      extract(msg) {
        const info = msg.data?.info;
        if (!info) return null;
        return {
          type: 'payment_params',
          value: JSON.stringify(info),
          platform: 'qq_midas',
          product: this._detectProduct(info.wx_appid || ''),
          captured_at: new Date().toISOString(),
        };
      },
    },

    // ── 规则 3: Midas 原生桥支付 ──
    {
      action: 'MidasJSBridge_call',
      match(msg) {
        return msg.data?.cmd === 'launchPaySign';
      },
      extract(msg) {
        return {
          type: 'payment_params',
          value: JSON.stringify(msg.data?.params || {}),
          platform: 'qq_midas',
          product: 'Q币',
          captured_at: new Date().toISOString(),
        };
      },
    },

    // ── 规则 4: mqq 支付 ──
    {
      action: 'mqq_buy',
      extract(msg) {
        const info = msg.data?.info;
        if (!info) return null;
        return {
          type: 'payment_params',
          value: JSON.stringify(info),
          platform: 'qq_midas',
          product: '游戏充值',
          captured_at: new Date().toISOString(),
        };
      },
    },

    // ── 规则 5: 通用支付 URL 跳转 ──
    {
      action: 'jump_face_url',
      extract(msg) {
        const url = msg.data?.schemaUrl || msg.data?.h5Url;
        if (!url) return null;
        return {
          type: 'payment_url',
          value: url,
          platform: 'qq_midas',
          product: '通用',
          captured_at: new Date().toISOString(),
        };
      },
    },

    // ── 规则 6: schema 跳转 ──
    {
      action: 'launch_schema',
      extract(msg) {
        const url = msg.data?.url;
        if (!url) return null;
        return {
          type: 'payment_url',
          value: url,
          platform: 'qq_midas',
          product: '通用',
          captured_at: new Date().toISOString(),
        };
      },
    },
  ],

  // ── 网络请求匹配 ──
  apiPatterns: [
    /api\.unipay\.qq\.com\/v1\/r\//,
    /pay\.qq\.com\/h5\/index\.shtml\?m=buy/,
    /tenpay\.com\/cgi-bin\/v1\.0\/pay\.cgi/,
  ],

  // ── DOM 监控规则 ──
  domRules: {
    // 支付弹窗选择器
    payDialogSelectors: [
      '[class*="pay"]',
      '[class*="dialog"]',
      '[class*="modal"]',
    ],
    // 二维码图片选择器
    qrSelectors: [
      'img[src*="qr"]',
      'img[src*="qrcode"]',
      'img[src*="wxpay"]',
      'canvas',
    ],
  },

  // ── 辅助方法 ──
  _detectProduct(url) {
    if (!url) return '未知';
    if (url.includes('qb') || url.includes('qcoin')) return 'Q币';
    if (url.includes('game')) return '游戏充值';
    if (url.includes('vip') || url.includes('svip')) return '会员';
    return 'Q币';
  },
});
