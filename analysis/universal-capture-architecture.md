# 万能支付凭证采集器 — 架构设计

## 要覆盖的介质

| 介质 | 技术方案 | 优先级 |
|------|---------|--------|
| 浏览器（Chrome/Edge） | CDP 注入 | P0 |
| PC 端游（CEF/WebView） | WinDivert 驱动层 | P0 |
| 微信小程序 | WinDivert 驱动层 | P1 |
| 手机 App（热点） | WinDivert + WiFi 热点 | P1 |

## 整体架构

```
┌────────────────────────────────────────────────────────────┐
│                    支付采集器 (Electron App)                 │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  采集控制层                           │  │
│  │  选择采集方式：CDP / WinDivert / 手动                 │  │
│  └────────┬──────────┬──────────────┬───────────────────┘  │
│           │          │              │                       │
│  ┌────────▼──┐ ┌─────▼──────┐ ┌─────▼─────────┐          │
│  │ CDP 引擎   │ │WinDivert  │ │ 手动输入       │          │
│  │           │ │ 驱动层     │ │               │          │
│  │ Chrome    │ │ 网络包过滤  │ │ 粘贴链接/二维码 │          │
│  │ CDP 连接  │ │ TLS 解密   │ │               │          │
│  │ 脚本注入  │ │ 响应提取   │ │               │          │
│  │ Cookie    │ │           │ │               │          │
│  │ 注入      │ │           │ │               │          │
│  └─────┬─────┘ └─────┬─────┘ └──────┬────────┘          │
│        │             │              │                     │
│        └─────────────┼──────────────┘                     │
│                      ▼                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              统一凭证处理层                            │  │
│  │  去重 → 账号匹配 → 平台归类 → 存入 SQLite → 自动上传  │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                  │
│                         ▼                                  │
│              平台 API (POST /api/terminal/inventory/upload) │
└─────────────────────────────────────────────────────────────┘
```

## 核心技术实现

### Layer 1: CDP 引擎（浏览器场景）

**已可落地**——今天已验证 XHR 拦截可行。

```
CDP 连接到用户 Chrome（通过 chrome.exe --remote-debugging-port=9222）
  ↓
对每个目标页面：
  1. Network.setCookies → 注入 QQ 账号的 Cookie
  2. Page.addScriptToEvaluateOnNewDocument → 注入 XHR 拦截脚本
  3. Page.navigate → 打开 goods.shtml
  ↓
用户点击支付 → XHR 拦截脚本捕获 web_save 响应
  ↓
CDP Runtime.evaluate → 从页面取回捕获数据
  ↓
写入本地凭证库
```

**关键优势**：CDP 注入的脚本在 V8 引擎层面执行，比 content.js 更底层，**完全绕过 CSP**。

### Layer 2: WinDivert 驱动层（端游/小程序/App）

这是真正的"Fiddler"级方案：

```
Windows 网络驱动层
  │
  WinDivert 过滤规则：
  │  ├── 目标域名 = api.unipay.qq.com, pay.qq.com, tenpay.com
  │  └── 目标端口 = 443
  │
  拦截到网络包 → 提取原始 TCP 流
  │
  ↓
  本地 TLS 代理（用 Windows SChannel 解密）
  │  ← 关键：和 Chrome 使用相同的 TLS 库，指纹完全一致
  │
  ↓
  提取 HTTP 请求/响应
  │
  ↓
  匹配 web_save → 提取支付码
  │
  ↓
  转发到真实服务器（应用无感知）
```

和当前 mitmproxy 的核心区别：

| | mitmproxy（当前） | WinDivert 方案 |
|--|-----------------|--------------|
| **TLS 库** | Go crypto/tls | Windows SChannel |
| **TLS 指纹** | 被腾讯识别 ❌ | 和 Chrome 一致 ✅ |
| **接入方式** | 系统代理 | 驱动层透明 |
| **被进程检测** | 可检测 | 不可检测 |
| **pydivert** | — | 已有依赖 |

### WinDivert 技术可行性

`pydivert` 已安装（在 tools server 的 requirements.txt 中）。它包装了 WinDivert 驱动：

```python
import pydivert

# 过滤支付域名
filter_rule = (
    "outbound and "
    "tcp.DstPort == 443 and "
    "(tcp.PayloadLength > 0)"
)

with pydivert.WinDivert(filter_rule) as w:
    for packet in w:
        # 提取 TCP 负载
        payload = packet.payload
        # 检测 TLS ClientHello 中的 SNI
        sni = extract_sni(payload)
        if sni in PAY_DOMAINS:
            # 重定向到本地代理
            packet.dst_addr = "127.0.0.1"
            packet.dst_port = 8802
        w.send(packet)
```

## 实施路线

| 阶段 | 内容 | 周期 |
|------|------|------|
| **Phase 1** | CDP 引擎 + Cookie 注入 | 这周 |
| | 账号管理系统（多 QQ 号添加/轮询） | 这周 |
| **Phase 2** | WinDivert 驱动代理 | 下周 |
| | Windows SChannel TLS 解密 | 下周 |
| **Phase 3** | 手机热点 + VPN 隧道 | 后续 |
| | WebSocket 小程序流量 | 后续 |

## 关键结论

**CDP + WinDivert 两条线并行**：
- CDP 解决浏览器场景（今天已验证可行性）
- WinDivert 解决端游/小程序/App 场景（和 Fiddler 同级别的底层切入）

两者共享同一套后端处理逻辑（凭证提取、账号映射、上传），上层统一。
