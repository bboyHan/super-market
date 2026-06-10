# 支付采集器 — 多账号持续采集技术方案

## 一、核心架构

```
┌────────────────────────────────────────────────────────┐
│                 代理商电脑（本地工具）                    │
│                                                         │
│  ┌──────────────────────────────────────────────┐      │
│  │ ① 账号管理：批量 QQ 账号的登录凭证存储          │      │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐      │      │
│  │  │ QQ号A1   │ │ QQ号A2   │ │ QQ号A3   │ ...  │      │
│  │  │ openid   │ │ openid   │ │ openid   │      │      │
│  │  │ cookies  │ │ cookies  │ │ cookies  │      │      │
│  │  └──────────┘ └──────────┘ └──────────┘      │      │
│  └───────────────────┬──────────────────────────┘      │
│                      ▼                                 │
│  ┌──────────────────────────────────────────────┐      │
│  │ ② 采集循环：轮询各账号生成支付码               │      │
│  │                                              │      │
│  │  ┌─────────┐   ┌─────────┐   ┌─────────┐    │      │
│  │  │ 注入Cookie│ → │ 打开页面  │ → │ 触发支付  │ →  │      │
│  │  │ QQ号A1  │   │ goods   │   │ (web_save)│    │      │
│  │  └─────────┘   └─────────┘   └────┬────┘    │      │
│  │                                    ▼         │      │
│  │  ┌─────────┐   ┌─────────┐   ┌─────────┐    │      │
│  │  │ 捕获支付码│ ← │ 拦截XHR  │ ← │ 响应返回  │    │      │
│  │  │ weixin://│   │ 响应体   │   │          │    │      │
│  │  └────┬────┘   └─────────┘   └─────────┘    │      │
│  └───────┼──────────────────────────────────────┘      │
│          ▼                                             │
│  ┌──────────────────────────────────────────────┐      │
│  │ ③ 自动上传：标记账号 → 上传到平台代理商库存池    │      │
│  │                                              │      │
│  │  支付码 + 标记QQ号A1 + 标记代理商ID           │      │
│  │  → POST /api/terminal/inventory/upload       │      │
│  │  → 存入平台 inventory_items（带agent_id）     │      │
│  └──────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────┘
```

## 二、三个技术难题与解决方案

### 难题 1：如何持续采集？（代替手动 F12）

**现状痛点**：目前需要手动 F12 粘贴脚本，无法持续。

**解决方案**：利用 Electron 内置浏览器，自动注入拦截脚本。

Electron 的 BrowserView 是一个真实的 Chromium 浏览器，我们可以在它加载页面之前注入 JavaScript，而且**不存在 CSP 限制**（因为 Electron 不受网页 CSP 约束）：

```javascript
// Electron main.js 中注入采集脚本（不受 CSP 限制）
collectorView.webContents.executeJavaScript(`
    // 拦截 XHR 的代码 — 和今天验证通过的完全一样
    const X = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(m,u){this._url=u;return X.apply(this,arguments)};
    const S = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function(b) {
        const u = this._url || '';
        if (u.includes('web_save')) {
            const x = this;
            x.addEventListener('load', function() {
                const t = x.responseText;
                const idx = t.indexOf('weixin://wxpay/bizpayurl?pr=');
                if (idx >= 0) {
                    const url = t.substring(idx, idx+80).split('"')[0].split(' ')[0];
                    // 直接 Electron IPC 发送到后端，没有 CSP 阻碍
                    require('http').post('http://localhost:8800/...', url);
                }
            });
        }
        return S.apply(this, arguments);
    };
`);
```

**为什么 Electron 可行**：
- ✅ 真实 Chromium 浏览器 → 腾讯无法检测是机器人
- ✅ 不受页面 CSP 限制 → 可以自由收发数据
- ✅ 可以注入 Cookie → 免去每次扫码登录
- ✅ 可以控制页面跳转 → 自动化操作路径

### 难题 2：如何持久化 QQ 登录态？（免重复扫码）

**已解决的问题**：PC OAuth 扫码一次后，`pay_openid` + `pay_openkey` 长期有效。

**流程**：

```
首次添加 QQ 账号：
  工具端 → 启动 Playwright → 打开 QQ OAuth 页面
  → 用户扫码 → 保存 pay_openid + pay_openkey + 全部 cookies
  → 存入本地 SQLite qq_accounts 表

后续采集（免扫码）：
  读取 qq_accounts 中的 cookies
  → 注入到 Electron BrowserView 的 CookieStore
  → 打开 goods.shtml（页面自动识别已登录）
  → 用户点「微信支付」即可
```

Cookie 持久化字段（已实现）：

| 字段 | 来源 | 用途 |
|------|------|------|
| `pay_openid` | OAuth Cookie | 支付认证核心 |
| `pay_openkey` | OAuth Cookie | 支付认证核心 |
| `p_uin` | OAuth Cookie | QQ 号 |
| `p_skey` | OAuth Cookie | 会话密钥 |
| `pt4_token` | OAuth Cookie | 防 CSRF Token |

### 难题 3：账号与支付码的隔离

**已经解决**——今天 POC 已经验证了。

```
web_save 请求体中的 openid → 本地 qq_accounts 表查询 → 获取 QQ 昵称
  ↓
凭证 metadata 中记录 account_name + openid
  ↓
上传到平台时标记 agent_id（由授权码决定）
```

## 三、实现路线图

### Phase 1：账号管理（本周可做）

| 功能 | 说明 |
|------|------|
| 添加 QQ 账号 | 扫码绑定，保存完整登录态 |
| 账号列表 | 显示昵称、状态、有效期 |
| 批量操作 | 全选、删除、切换 |

### Phase 2：Electron 内置浏览器采集（下周）

| 功能 | 说明 |
|------|------|
| Electron 预注入拦截脚本 | 无 CSP 限制的 XHR 拦截 |
| Cookie 注入 | 免登录打开支付页 |
| 单账号采集模式 | 选择一个账号 → 打开浏览器 → 用户点支付 → 自动捕获 |
| 多账号轮询采集 | 自动在各账号间切换 |

### Phase 3：自动上传与持续循环

| 功能 | 说明 |
|------|------|
| 捕获即上传 | web_save 捕获后自动上传到平台库存 |
| 采集队列 | 多个账号排队采集，循环执行 |
| 过期账号标记 | Cookie 失效时自动标记为 EXPIRED |

## 四、关键技术验证

今天 POC 已证明的：
- ✅ XHR web_save 拦截可以提取 `weixin://` 支付 URL
- ✅ openid 可以从请求体提取并用于账号映射
- ✅ 支付码 + openid 写入本地数据库
- ✅ new Image() 可以绕过 CSP（但 Electron 不需要，因为不受 CSP 限制）
- ✅ 本地上传到平台的接口已经联调通过

待验证的：
- ⏳ Electron BrowserView 中注入脚本的效果
- ⏳ 腾讯对 Electron 浏览器指纹的检测（理论上 Electron = Chromium，不应触发 bot 检测）
- ⏳ Cookie 注入后页面自动识别登录态的成功率
