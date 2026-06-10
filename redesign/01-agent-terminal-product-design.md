# Agent Terminal — 支付凭证自动化采集系统

## 产品设计文档 v1.0

> 作者：bboyhan
> 版本：1.0
> 日期：2026-06-09

---

## 一、产品定位

### 1.1 一句话定义

> **一个全流量拦截系统，自动捕获用户在浏览器、PC端游、桌面应用等各场景下的支付凭证，为下游 API 支付商提供自动化供货能力。**

### 1.2 产品边界

| 支付场景 | 采集方式 | 代表产品 |
|----------|----------|----------|
| **浏览器 H5 支付** | Chrome 插件拦截 postMessage | pay.qq.com Q币充值、网页游戏充值 |
| **PC 端游内置支付** | 系统代理 (mitmproxy) 抓取 CEF/WebView 流量 | DNF、英雄联盟、梦幻西游客户端 |
| **桌面应用支付** | 系统代理抓取 HTTP 请求 | 腾讯手游助手、模拟器内支付 |
| **手机 App 支付** | WiFi 代理 / VPN 隧道抓包 | 手机 QQ 充值、各类手游 App内购 |

### 1.3 核心价值

| 角色 | 痛点 | 解决方案 |
|------|------|----------|
| **API 支付商** | 需要批量有效的支付凭证（Token/支付链接）才能自动下单 | 提供持续供给的凭证池，覆盖多场景 |
| **凭证采集者** | 需要为不同场景切换不同工具 | 统一代理 + 插件，一次配置全场景覆盖 |
| **系统本身** | 需要兼容多种平台和支付协议 | 统一流量拦截管道，平台适配可插拔 |

### 1.4 设计原则

1. **零重量客户端** — 代理商不需要安装模拟器、虚拟机、Playwright 等重型依赖
2. **被动采集** — 不主动模拟操作，而是截获代理商正常操作中产生的数据
3. **全场景覆盖** — 浏览器、PC端游、桌面应用统一采集管道
4. **一次配置，持续采集** — 登录态保持期间自动捕获所有后续凭证
5. **平台无关抽象** — 采集机制统一，平台适配可插拔

---

## 二、核心架构

### 2.1 产品形态：Electron 桌面应用

**一个安装程序，包含一切。**

```
agent-terminal-setup.exe  (≈ 150MB)
  │
  ├── Electron 壳（Chromium 114+）
  │   └── 内嵌浏览器 + postMessage 拦截
  │
  ├── mitmproxy（Windows 二进制）
  │   └── HTTPS 流量拦截引擎
  │
  ├── Python 后端（编译为 exe）
  │   └── 凭证存储 + 平台同步
  │
  └── Wi-Fi 热点工具
      └── 一键创建手机采集热点
```

代理商打开应用，看到的是：

```
┌─────────────────────────────────────────────────┐
│  Agent Terminal                        ─ □ ✕    │
├─────────────────────────────────────────────────┤
│                                                   │
│  ┌───────────────────────────────────────────┐   │
│  │                                           │   │
│  │   ① 浏览器采集       ② PC端游采集         │   │
│  │                     ③ 手机端采集          │   │
│  │                                           │   │
│  │   点击「开始采集」→ 应用内打开浏览器        │   │
│  │   扫码登录 → 点击支付 → 自动捕获凭证        │   │
│  │                                           │   │
│  │   已采集: 127 条             查看库存 ▶   │   │
│  └───────────────────────────────────────────┘   │
│                                                   │
├─────────────────────────────────────────────────┤
│  网络: 正常  │  后台: 运行中  │  平台: 已连接    │
└─────────────────────────────────────────────────┘
```

### 2.2 三管道采集架构

```
┌─────────────────────────────────────────────────────────────────────┐
│  Agent Terminal (Electron)                                           │
│                                                                      │
│  ┌────────────────┬────────────────┬────────────────────────┐       │
│  │  管道 A         │  管道 B         │  管道 C                 │       │
│  │  浏览器采集      │  PC端游采集     │  手机端采集              │       │
│  │                 │                │                        │       │
│  │  Electron      │  mitmproxy     │  mitmproxy              │       │
│  │  内置浏览器     │  (系统代理)     │  (WiFi 热点)            │       │
│  │                 │                │                        │       │
│  │  用户操作       │  启动游戏      │  手机连接热点            │       │
│  │  ↓              │  ↓             │  ↓                     │       │
│  │  postMessage    │  HTTP 请求     │  支付 HTTP 请求          │       │
│  │  捕获支付凭证   │  捕获支付参数   │  捕获支付参数            │       │
│  └───────┬────────┘  └──────┬───────┘  └──────────┬──────────┘       │
│          │                  │                     │                  │
│          └──────────────────┼─────────────────────┘                  │
│                             ▼                                       │
│                    ┌──────────────────┐                              │
│                    │  内置采集后端     │                              │
│                    │  (Python exe)    │                              │
│                    │  SQLite 存储     │                              │
│                    │  同步到平台      │                              │
│                    └──────────────────┘                              │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.3 三种采集模式切换

用户在主界面一个下拉/标签切换：

| 模式 | 做了什么 | 用户操作 |
|------|---------|----------|
| **浏览器采集** | 打开内置 Chromium 浏览器 | 跟平时一样上网操作 |
| **PC端游采集** | 设置系统代理 → 启动 mitmproxy | 正常打开游戏 |
| **手机端采集** | 启动 WiFi 热点 → 启动 mitmproxy | 手机连热点 → 打开 App |

**全程零配置。** 用户只需要点击对应模式的「开始」按钮。

### 2.4 跟原有 Agent Terminal 的关系

```
Agent Terminal (Electron 桌面壳)
       │
       ├── Playwright 采集模式（保留）
       │   └── 用于初始化 OAuth 账号绑定
       │
       ├── Chrome 插件模式（废弃）
       │   └── 被内置浏览器替代，不需要单独装插件
       │
       ├── 手动输入模式（保留）
       │   └── 兜底方案
       │
       └── 内置浏览器采集模式（新增，主力）← 本文档设计
           └── 单 .exe，一键启动，零配置
```

Chrome 插件的概念**不再需要**——Electron 内嵌的 Chromium 浏览器天然可以注入采集脚本，不需要经过 Chrome Web Store 发布流程。

---

## 三、核心采集机制

### 3.1 统一拦截模型

所有主流支付平台（腾讯 Midas、微信支付、支付宝、苹果内购等）的 H5 支付流程都遵循相似的架构模式：

```
支付 SDK (页面 A)
  │
  ├── 打开 iframe / 弹窗
  │   └── iframe 内完成订单创建
  │
  ├── iframe → parent postMessage
  │   └── {action: "wechat_buy" | "pay", data: {支付参数}}
  │
  └── parent 页面根据参数发起支付
      ├── WeixinJSBridge.invoke("getBrandWCPayRequest", ...)
      ├── location.href = 支付URL
      └── (其他支付方式)
```

**关键洞察：** 在桌面浏览器中，如果不存在 `WeixinJSBridge` / `MidasJSBridge`，父页面会 **fallback 到 `location.href = 支付URL`**。这个 URL 就是我们需要的最终凭证。

### 3.2 拦截策略（三层递进）

#### 策略 1：postMessage 拦截（最高优先级）

```javascript
// content.js — 捕获阶段拦截所有 postMessage
window.addEventListener('message', (event) => {
    const msg = event.data;
    if (!msg || !msg.action) return;
    
    // 匹配已知支付 action
    const handlers = PLATFORM_HANDLERS[event.origin] || [];
    for (const handler of handlers) {
        if (handler.match(msg)) {
            // 提取支付凭证
            const credential = handler.extract(msg);
            // 发送到本地后端
            sendToBackend(credential);
            break;
        }
    }
}, true); // 捕获阶段 = true —— 先于页面自身的 handler
```

#### 策略 2：网络请求拦截（备选）

```javascript
// content.js — 拦截 XHR / fetch 中携带支付信息的请求
const originalFetch = window.fetch;
window.fetch = function(...args) {
    const url = args[0];
    if (PAYMENT_API_PATTERNS.some(p => url.match(p))) {
        // 克隆响应，解析支付数据
        return originalFetch.apply(this, args).then(async (resp) => {
            const clone = resp.clone();
            const data = await clone.text();
            /* 提取凭证逻辑 */
            return resp;
        });
    }
    return originalFetch.apply(this, args);
};
```

#### 策略 3：DOM 监控（兜底）

```javascript
// content.js — 检测 iframe URL 变化 / DOM 中出现支付二维码
const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
        for (const node of m.addedNodes) {
            if (node.tagName === 'IFRAME') {
                monitorFrame(node);
            }
        }
    }
});
observer.observe(document.body, { childList: true, subtree: true });
```

### 3.3 支付凭证类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `payment_url` | 可直接访问的支付链接 | `https://wx.tenpay.com/...` |
| `payment_params` | 结构化支付参数 | `{appId, timeStamp, nonceStr, package, signType, paySign}` |
| `access_token` | API 访问令牌 | `pay_openid` + `pay_openkey` |
| `qr_image` | 支付二维码图片（base64） | `data:image/png;base64,...` |
| `order_id` | 订单号 | `M2026060912345678` |

---

## 四、PC 端游采集机制

### 4.1 适用场景

PC 端游（DNF、英雄联盟、梦幻西游、剑网三等）的支付流程典型结构：

```
游戏启动器 → 游戏客户端 → 点击充值/商城
                              │
               ┌──────────────┴──────────────┐
               │                              │
         内置 WebView (CEF)              原生支付 SDK
               │                              │
   加载支付 H5 页面                     直接调用系统支付
   同浏览器插件方案                     或跳转浏览器
```

### 4.2 mitmproxy 拦截方案

#### 原理

```
游戏客户端 ──HTTPS──► mitmproxy:8802 ──► 真实服务器
                         │
                         ├── 解密 HTTPS 流量
                         ├── 匹配支付 API 请求
                         │   (api.unipay.qq.com, tenpay.com, etc.)
                         ├── 提取支付参数
                         │   (URL、Token、订单信息)
                         └── POST /api/collect → 本地后端
```

#### 关键点

1. **HTTPS 降级** — mitmproxy 在本地生成 CA 证书，需要安装到系统受信任的根证书颁发机构
2. **流量过滤** — 只拦截支付相关的 API 域名，减少干扰
3. **无需修改游戏** — 游戏客户端无感知，mitmproxy 透明转发

#### 过滤规则（mitmproxy 脚本）

```python
# mitm_scripts/pay_collector.py
import json, requests

PAY_DOMAINS = [
    'api.unipay.qq.com',
    'pay.qq.com',
    'wx.tenpay.com',
    'tenpay.com',
    'api.mch.weixin.qq.com',
]

def request(flow):
    host = flow.request.pretty_host
    if not any(d in host for d in PAY_DOMAINS):
        return  # 非支付流量，放行
    
    # 提取支付参数
    credential = {
        'type': 'api_request',
        'platform': 'qq_midas',
        'method': flow.request.method,
        'url': flow.request.pretty_url,
        'headers': dict(flow.request.headers),
        'body': flow.request.text[:5000],
        'captured_at': str(datetime.now()),
    }
    
    # 发送到本地后端
    try:
        requests.post('http://localhost:8801/api/collect', json=credential, timeout=1)
    except:
        pass

def response(flow):
    host = flow.request.pretty_host
    if not any(d in host for d in PAY_DOMAINS):
        return
    
    # 响应中可能包含支付 URL、微信支付参数等
    credential = {
        'type': 'api_response',
        'platform': 'qq_midas',
        'url': flow.request.pretty_url,
        'status': flow.response.status_code,
        'body': flow.response.text[:10000],
        'captured_at': str(datetime.now()),
    }
    
    try:
        requests.post('http://localhost:8801/api/collect', json=credential, timeout=1)
    except:
        pass
```

### 4.3 跟浏览器插件的关系

```
浏览器插件覆盖：            mitmproxy 覆盖：
Chrome 中的支付流程        全系统的 HTTP 流量
                                   │
                    ┌──────────────┴──────────────┐
                    │                              │
                Chrome 中的流量              游戏 / 应用的流量
                (插件优先拦截)               (代理兜底拦截)
                    │                              │
                    └──────────┬───────────────────┘
                               ▼
                        本地后端统一入库
```

### 4.4 局限性

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 游戏检测代理 | 部分游戏检测系统代理设置并拒绝启动 | 使用进程级代理注入绕过 |
| 证书锁定 | 游戏客户端自带固定证书（Certificate Pinning） | 需要 Hook 底层网络库（难度大） |
| 非 HTTP 协议 | 部分游戏使用 TCP/UDP 自定义协议 | 无法拦截，换用其他方式 |
| 反作弊系统 | 检测到 mitmproxy 可能触发反作弊 | 需要白名单或免代理模式 |

---

## 五、手机端采集机制

### 5.1 适用场景

手机 App（手机 QQ、微信、各类手游）的支付流程：

```
手机 App (iOS/Android)
  │
  ├── 点击「充值」/「购买」
  ├── 调起支付 SDK（微信支付/支付宝/苹果内购）
  │
  ├── HTTP API 请求 ◄─── 目标
  │   └── POST https://api.unipay.qq.com/...
  │   └── POST https://api.mch.weixin.qq.com/...
  │   └── POST https://pay.qq.com/...
  │
  └── 调起第三方支付 App（微信/支付宝）
       └── 支付完成 → 回调
```

### 5.2 两种采集方案

#### 方案 A：PC WiFi 热点转发（推荐，零手机配置）

利用代理商的 PC 作为 WiFi 热点，手机连上后所有流量经过 PC 的 mitmproxy：

```
代理商 PC                             手机
  │                                     │
  ├── 开启 WiFi 热点 ───────────────► 连接热点
  │   (Windows: 移动热点)                │
  │                                     │
  ├── mitmproxy 运行在 :8802             │
  │   (监听所有网络接口)                  │
  │                                     │
  │  手机发起支付请求 ──────────────────► │
  │    (通过热点)                        │
  │                                     │
  ├── mitmproxy 拦截请求                  │
  │   ├── 提取支付参数                    │
  │   ├── 转发到真实服务器                │
  │   └── POST /api/collect              │
  │                                     │
  └──◄──── 正常返回 ──────────────────── │
```

**配置步骤：**
```
1. PC 开启 WiFi 热点（Win10/11 自带「移动热点」功能）
2. 启动 mitmproxy：mitmproxy --listen-host 0.0.0.0 --listen-port 8802 --mode transparent
3. 手机连接 PC 热点
4. 首次访问 http://mitm.it 安装 CA 证书
5. 打开手机 App → 点击充值 → 自动采集 ✓
```

#### 方案 B：VPN 隧道 App（跨网络可用）

手机安装专用 VPN App，通过 WireGuard / OpenVPN 隧道将流量转发到 PC 的 mitmproxy：

```
代理商 PC（有公网 IP 或内网穿透）         手机（任何网络）
  │                                         │
  ├── WireGuard 服务端 ────────────────► WireGuard 客户端
  │   :8802 转发到 mitmproxy               │ (VPN App)
  │                                         │
  │  mitmproxy 拦截所有隧道流量               │
  │  提取支付凭证                            │
  │                                         │
  └─────────────────────────────────────────┘
```

**适用场景：** 手机无法连接 PC 热点时（如不在同一地点），通过互联网隧道采集。

### 5.3 与 PC 端游的复用关系

手机端采集**复用 PC 端游的 mitmproxy 基础设施**：

```
系统代理 (PC端游) ──► mitmproxy:8802 ◄── 手机热点/VPN
                            │
                ┌───────────┴───────────┐
                │                       │
          PC游戏流量              手机App流量
                │                       │
                └───────┬───────────────┘
                        ▼
                 本地后端统一入库
```

手机端不需要独立的采集组件，只需要确保：
1. mitmproxy 监听在 `0.0.0.0:8802`（所有网络接口）
2. 手机流量能路由到 PC（通过热点或 VPN）
3. 手机安装了 mitmproxy 的 CA 证书

### 5.4 局限性

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| Apple ATS | iOS 要求 HTTPS + 证书锁定 | 需越狱或企业证书（难度大） |
| Android 证书锁定 | 部分 App 自带固定证书 | 需 Magisk + JustTrustMe 模块 |
| 微信/支付宝内支付 | 调起原生支付 App，不走 HTTP | 无法拦截（App 间跳转） |
| 不同网络环境 | 手机不在 PC 同一网络 | 使用 VPN 隧道方案 |

## 六、腾讯系产品参考实现

### 6.1 调研结论

> **截止 2026年6月，腾讯 Midas 支付体系不支持通过纯 API 创建订单获取支付链接。**

#### 尝试过的方案及结果

| 方案 | 结果 | 原因 |
|------|------|------|
| `POST /v1/r/{offer_id}/create_order` | 404 | API 不存在 |
| `GET /v1/r/{offer_id}/get_pay_info` | 200 但 ret=1018 | 需浏览器 session 认证 |
| `GET /v1/r/{offer_id}/query_order` | 200 | 需订单 ID |
| `GET /v1/r/{offer_id}/get_balance` | 200 返回空 | — |
| PC OAuth + Cookie 注入 | ✅ Token 有效 | 可验证身份但不能获取支付码 |
| Playwright + Hash 覆盖 Shop SPA | ✅ 登录态识别 | 「立即充值」按钮 disabled，无法调起支付 |
| H5 index.shtml dialog 模式 | ❌ 安全拦截 | "因安全因素，您当前的访问无法继续" |

#### 可用产品线

| offer_id | 产品 | 采集方式 |
|----------|------|----------|
| `1450000186` | Q币 | postMessage 拦截 |
| `1450000238` | DNF 端游 | postMessage 拦截 |
| `1450015040` | QQ飞车 | postMessage 拦截 |
| `1450026248` | 天涯明月刀 | postMessage 拦截 |
| `1450029577` | 英雄联盟手游 | postMessage 拦截 |
| `1450030204` | 金铲铲之战 | postMessage 拦截 |
| `800000008` | QQ飞车手游直播小店 | postMessage 拦截 |

### 6.2 腾讯系拦截规则

```javascript
// platforms/qq_midas.js
module.exports = {
    name: 'QQ Midas',
    origins: ['https://pay.qq.com', 'https://graph.qq.com'],
    
    // postMessage 匹配规则
    messageHandlers: [
        {
            // 微信支付参数（桌面 fallback 到 URL）
            action: 'wechat_wapbuy',
            extract: (msg) => ({
                type: 'payment_url',
                value: msg.data.url,
                platform: 'qq_midas',
                product: 'Q币',
            }),
        },
        {
            // 微信支付参数（原生桥调用）
            action: 'wechat_buy',
            extract: (msg) => ({
                type: 'payment_params',
                value: JSON.stringify(msg.data.info),
                platform: 'qq_midas',
            }),
        },
        {
            // MidasJSBridge 原生支付
            action: 'MidasJSBridge_call',
            match: (msg) => msg.data?.cmd === 'launchPaySign',
            extract: (msg) => ({
                type: 'payment_params',
                value: JSON.stringify(msg.data.params),
                platform: 'qq_midas',
            }),
        },
    ],
    
    // 网络请求匹配
    apiPatterns: [
        'api.unipay.qq.com/v1/r/',
        'pay.qq.com/h5/index.shtml?m=buy',
    ],
};
```

---

## 七、平台扩展框架

### 7.1 平台适配规范

每个新平台需要提供一个适配器文件 `platforms/{name}.js`：

```javascript
// platforms/apple.js — 苹果支付示例
module.exports = {
    name: 'Apple Pay',
    // 目标页面 URL 匹配
    origins: ['https://buy.itunes.apple.com', 'https://sandbox.itunes.apple.com'],
    
    // postMessage 拦截规则
    messageHandlers: [...],
    
    // API 请求拦截规则
    apiPatterns: ['/WebObjects/MZFinance.woa/wa/buyProduct'],
    
    // DOM 监控规则
    domRules: {
        qrSelector: 'img[src*="qr"], canvas[aria-label*="qr"]',
        iframeUrlPattern: '/checkout/',
    },
    
    // 凭证提取逻辑
    extractCredential: (rawData) => ({
        type: 'payment_url' | 'payment_params' | 'access_token',
        value: extracted_value,
        platform: 'apple',
        product: product_name,
        amount: price,
    }),
};
```

### 7.2 已知可扩展平台

| 平台 | 切入点 | 拦截难度 |
|------|--------|----------|
| **腾讯 Midas** | postMessage `wechat_wapbuy` / `wechat_buy` | ⭐⭐ |
| **微信支付 H5** | `WeixinJSBridge` invoke 参数拦截 | ⭐⭐ |
| **支付宝** | `AlipayJSBridge` postMessage | ⭐⭐ |
| **苹果内购** | `SKPaymentQueue` 需越狱/模拟器 | ⭐⭐⭐⭐⭐ |
| **话费充值** | 取决于具体渠道商 | ⭐~⭐⭐⭐ |
| **网易点券** | 取决于具体支付对接方式 | ⭐⭐⭐ |

---

## 八、部署方案

### 8.1 代理商部署步骤（唯一方式）

```
下载 agent-terminal-setup.exe → 双击安装 → 打开软件
                                                         ↓
                                    ┌─────────────────────────┐
                                    │  首次使用引导             │
                                    │  1. 登录 Super Market 账号 │
                                    │  2. 配置平台 API 地址      │
                                    │  3. 开始采集              │
                                    └─────────────────────────┘
```

**代理商不需要理解：** Python、Chrome 插件、mitmproxy、代理设置、CA 证书、命令行。

### 8.2 安装包内容

| 组件 | 技术 | 大小 | 说明 |
|------|------|------|------|
| 桌面壳 | Electron + React | ≈ 80MB | 界面 + 内置浏览器 |
| 采集引擎 | TypeScript (preload) | 内嵌 | postMessage 拦截脚本 |
| 代理引擎 | mitmproxy (Windows 二进制) | ≈ 30MB | HTTPS 流量拦截 |
| 后端 | Python → PyInstaller exe | ≈ 30MB | 凭证存储 + 平台同步 |
| CA 证书生成器 | OpenSSL | 内嵌 | 首次运行自动生成并安装 |

**总计 ≈ 150MB，单文件安装包。**

### 8.3 技术选型

| 层 | 技术 | 原因 |
|----|------|------|
| 桌面壳 | Electron + Chromium | 内嵌浏览器 = 天然采集环境 |
| 界面 | React / Vue | 团队已有的前端技术栈 |
| 代理 | mitmproxy (embedded) | 成熟的 HTTPS 中间人代理 |
| 后端 | Go（推荐）或 Python → exe | 单二进制，零运行时依赖 |
| 持久化 | SQLite | 单文件，零配置 |
| 安装包 | NSIS / Inno Setup | 业界标准 Windows 安装器 |

---

## 九、与现有 Agent Terminal 的关系

```
Agent Terminal (Electron 桌面壳)
       │
       ├── 内置浏览器采集模式（新增，主力）
       │   └── 单 .exe，一键启动，零配置
       │
       ├── Playwright 模式（保留）
       │   └── 用于初始化 OAuth 账号绑定
       │
       └── 手动输入模式（保留）
           └── 兜底方案
```

三种模式的关系：

| 模式 | 用途 | 用户场景 |
|------|------|----------|
| **内置浏览器采集** | 日常采集主力 | 打开应用 → 浏览/操作 → 自动捕获 |
| **Playwright 模式** | 首次 OAuth 绑定 | 扫二维码获取初始 Token |
| **手动输入** | 兜底 | 从其他渠道获取的凭证手动录入 |

---

## 十、产品路线图

### 10.1 Phase 1 — MVP（2周）

- [ ] Chrome 插件基础框架（content.js + background.js）
- [ ] 腾讯 Midas 拦截规则
- [ ] 本地后端（接收 + SQLite 存储）
- [ ] 端到端验证：访问 pay.qq.com → 触发支付 → 插件捕获 → 入库

### 10.2 Phase 2 — 平台扩展（每平台1-3天）

- [ ] 微信支付 H5 拦截规则
- [ ] 支付宝拦截规则
- [ ] 话费充值渠道
- [ ] 网易/盛大等游戏平台

### 10.3 Phase 3 — 体验完善

- [ ] 插件状态面板（实时采集计数、连接状态）
- [ ] 凭证管理界面（筛选、导出）
- [ ] 自动同步到 Super Market 平台
- [ ] 凭证过期预警

---

## 十一、附录

### 11.1 附录 A：腾讯 Midas 支付协议结构图

```
┌───────────────┐     postMessage      ┌───────────────┐
│  iframe 支付页  │ ──────────────────►  │  父页面       │
│  (pay.qq.com)  │   {action, data}     │               │
│               │                       │  ┌─────────┐  │
│  生成支付参数   │                       │  │Chrome   │  │
│  wx_appid      │                       │  │Plugin   │  │
│  wx_time       │                       │  │(capture)│  │
│  wx_nonce      │                       │  └────┬────┘  │
│  wx_package    │                       │       │       │
│  wx_sign       │                       │       ▼       │
└───────────────┘                       │  localhost     │
                                        │  :8801         │
                                        └───────────────┘
```

### 11.2 附录 B：关键缩写

| 缩写 | 全称 |
|------|------|
| Midas | 腾讯移动支付平台 |
| Unipay | 腾讯统一支付 API |
| offer_id | 产品 ID，用于标识不同游戏/服务 |
| openid | 用户在该应用下的唯一标识 |
| openkey | 用户的 OAuth 访问令牌 |
| p_uin | QQ 号（带 o 前缀） |
| p_skey | QQ 会话密钥 |
| WeixinJSBridge | 微信原生 JS 桥 |
| MidasJSBridge | Midas 原生 JS 桥 |
