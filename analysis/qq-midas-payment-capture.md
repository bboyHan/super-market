# QQ Midas 支付流程深度分析 — 微信支付码捕获方案

## 一、页面流程还原

```
用户访问 SPA 页面
  → https://pay.qq.com/s/one?offer_id=1450000186&s=1SVj98TOaq8...
      ↓
  未登录 → 点击「立即登陆」→ QQ 扫码登录
      ↓ 获取 pay_openid + pay_openkey
  显示商品金额（不同面值点券）
      ↓ 用户选择金额
  弹出三种支付方式：Q币 / 微信支付 / QQ钱包
      ↓ 用户选择「微信支付」
  POST web_save → 创建订单 → 返回支付参数
      ↓
  调用 get_qr_image.cgi → 渲染微信支付二维码 ← 目标捕获点
```

## 二、关键请求深度解析

### 请求①：web_save（核心）

```
POST https://api.unipay.qq.com/v1/r/1450049871/web_save
```

**为什么这是核心请求？**
- `pay_method=wechat` → 指定微信支付
- 服务端响应中会返回 `weixin://wxpay/bizpayurl?pr=XXX` 
- 这个 URL 就是微信支付的凭证，扫码即可付款

**参数中的关键字段：**

| 参数 | 来源 | 说明 |
|------|------|------|
| `openid` / `openkey` | QQ OAuth Cookie | 已解决（PC OAuth 扫码） |
| `sck` | `MD5(offer_id + openkey).upper()` | ✅ 已逆向，`FB165B66F908B6900377CF7ADFA014ED` |
| `encrypt_msg` | AES-ECB 加密 | ⚠️ 已逆向但字段顺序难对齐 |
| `web_token` | DOM 中的 `xMidasToken` | 页面生成，浏览器自动处理 |
| `pay_method` | 用户选择 | `wechat` / `qqwallet` / `qpay` |

### 请求②：get_qr_image.cgi（QR 码渲染）

```
GET https://pay.qq.com/cgi-bin/account/get_qr_image.cgi
  ?url=weixin%3A%2F%2Fwxpay%2Fbizpayurl%3Fpr%3D5QQN1Ssp8qnueJmE
  &size=120&t=1781072007764&orig=1
```

**关键发现：** `url` 参数就是 weixin:// 深层链接，**这个 URL 才是真正的支付凭证**，QR 码只是它的可视化形式。

## 三、最优捕获方案

### 方案 A：✅ 拦截 web_save 响应（推荐，零额外工作）

**原理：** 用户通过真实浏览器完成全部操作（登录、选择金额、选择微信支付），我们只需要在浏览器层面**拦截 web_save 的 fetch 响应**，提取返回体中的 `weixin://wxpay/bizpayurl?pr=XXX`。

```
用户操作 → 浏览器处理所有复杂逻辑（加密/token/签名）
    ↓
浏览器发起 POST web_save → 服务端返回支付 URL
    ↓
content.js 拦截 fetch 响应 ← 只需这一行代码
    ↓
提取 weixin://wxpay/bizpayurl?pr=XXX → 存入凭证库
    ↓
调用 get_qr_image.cgi 生成二维码（可选，用于展示）
```

**优势：**
- ✅ 不需要逆向 `encrypt_msg` 的字段顺序
- ✅ 不需要提取 `web_token`（页面自动生成）
- ✅ 不需要处理任何加密算法
- ✅ 兼容所有支付方式（微信/Q币/QQ钱包）
- ✅ 已有的 content.js 框架可以直接实现

**content.js 核心代码：**
```javascript
// 拦截 web_save 的 fetch 响应
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
    
    if (url.includes('/v1/r/') && url.includes('web_save')) {
        const response = await originalFetch.apply(this, args);
        const clone = response.clone();
        const text = await clone.text();
        
        // 提取 weixin:// 支付 URL
        const match = text.match(/weixin:\/\/wxpay\/bizpayurl\?pr=[^\s"'}]+/);
        if (match) {
            sendToBackend({
                type: 'payment_url',
                value: match[0],
                platform: 'qq_midas',
                product: 'Q币',
                source: 'web_save_response',
            });
        }
        return response;
    }
    return originalFetch.apply(this, args);
};
```

### 方案 B：mitmproxy 代理拦截（作为兜底）

**原理：** 在 mitmproxy 层面拦截 `web_save` 的 HTTPS 响应，同样提取 `weixin://` URL。

```python
# mitm_script.py 增强
def response(flow):
    host = flow.request.pretty_host
    path = flow.request.path
    
    if "api.unipay.qq.com" in host and "web_save" in path:
        body = flow.response.text
        for match in re.finditer(r'weixin://wxpay/bizpayurl\?pr=[^\s"\'<>]+', body):
            send_credential({
                "type": "payment_url",
                "value": match.group(0),
                "platform": "qq_midas",
                "source": "mitmproxy_web_save",
            })
    
    # 也捕获 get_qr_image 的图片（备选）
    if "get_qr_image.cgi" in path:
        # 可以保存二维码图片本身
        pass
```

### 方案 C：postMessage 拦截（如果页面有）

部分 Midas 页面通过 postMessage 与父页面通信。`content.js` 已经在捕获阶段注册了 listener：

```javascript
window.addEventListener('message', (event) => {
    const msg = event.data;
    // 可能的 action: "wechat_wapbuy", "wechat_buy", "pay_success"
    if (msg?.action === 'wechat_wapbuy' && msg.data?.url) {
        sendToBackend({
            type: 'payment_url',
            value: msg.data.url,
            platform: 'qq_midas',
            source: 'postmessage',
        });
    }
}, true); // 捕获阶段
```

## 四、方案对比

| 方案 | 实现难度 | 可靠性 | 额外依赖 |
|------|---------|--------|---------|
| **A: fetch 拦截** ⭐ | 低（~10行代码） | 高 | content.js 注入 |
| **B: mitmproxy** | 中（~20行） | 中（HTTPS证书依赖） | 系统代理配置 |
| **C: postMessage** | 低 | 低（页面不一定使用） | 无 |

## 五、推荐实施路径

**短期（立即可用）：**
1. 在现有的 `content.js` 中添加 `web_save` fetch 拦截（方案 A）
2. 在现有的 `mitm_script.py` 中添加 web_save 响应解析（方案 B）
3. 即可实现「用户登录 → 选择支付 → 自动捕获支付 URL」

**验证方法：**
1. 在 Electron 内置浏览器中打开目标页面
2. QQ 扫码登录
3. 选择商品 → 选择微信支付
4. 观察 content.js 是否捕获到 `weixin://wxpay/bizpayurl?pr=XXX`
5. 验证该 URL 可以通过 `get_qr_image.cgi` 转为可扫描的二维码

**注意：** weixin:// 深层链接在 Android 上可以直接拉起微信支付。在桌面端可以将此 URL 传递给手机使用，或转为二维码图片展示。
