# Fiddler vs mitmproxy — 腾讯页面无感知切入分析

## 两者的根本区别

| 对比项 | Fiddler | mitmproxy |
|--------|---------|-----------|
| **TLS 实现** | Windows SChannel（系统原生） | Go crypto/tls（第三方） |
| **TLS 指纹 (JA3)** | 与 Chrome/Edge **完全一致** | 不同，Go 的 TLS ClientHello 特征明显 |
| **CA 证书格式** | 完整的 X.509 v3 扩展 | 可能缺少关键扩展 |
| **系统集成** | .NET / Windows 原生 | Python 跨平台 |

## 为什么 Fiddler 无感知？

### 1. TLS 指纹一致（最关键）

Chrome 浏览器在 Windows 上使用 **SChannel**（Windows 内置的 TLS 实现）。Fiddler 同样使用 SChannel。这意味着：

```
Chrome TLS 指纹 (JA3) = xxxxxx    ← SChannel
Fiddler TLS 指纹 (JA3) = xxxxxx    ← SChannel（完全相同！）
```

腾讯服务器在 TLS 握手阶段看到的是和 Chrome 完全一样的指纹，无法区分。

而 mitmproxy 使用 **Go 的 crypto/tls**，它的 ClientHello 包里：
- 密码套件顺序不同
- TLS 扩展顺序不同  
- 椭圆曲线偏好不同

```
mitmproxy TLS 指纹 (JA3) = yyyyyy  ← 与 Chrome 不同
```

腾讯服务器可以通过 JA3 指纹检测到中间人代理。

### 2. 证书透明度 (Certificate Transparency)

Chrome 要求 DV/OV 证书必须在 CT 日志中记录。Fiddler 会特殊处理，而 mitmproxy 的自签名 CA 不在 CT 日志中，在某些 Chrome 版本中会被拒绝。

### 3. HSTS 处理

腾讯的 `pay.qq.com` 开启了 HSTS：
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

Chrome 强制 HTTPS 连接，如果 mitmproxy 在处理 HSTS 连接时有任何证书问题，浏览器直接拒绝。

## 解决方案

### 方案 A：让 mitmproxy 匹配浏览器 TLS（推荐尝试）

mitmproxy 可以通过 `--set tls_version=...` 等参数调整 TLS 行为。但底层仍是 Go 的 crypto/tls，指纹差异无法完全消除。

### 方案 B：使用 WinDivert + Python 原生代理（类似 Fiddler 原理）

在 Windows 上使用 WinDivert 库实现透明代理，不走 Go 的 TLS，而是通过 Windows API 处理 HTTPS：

```
浏览器 → WinDivert (网络层拦截) → Python 代理 → 用 SChannel 转发 → 腾讯服务器
                                          ↓
                                    提取支付凭证
```

复杂但彻底。

### 方案 C：混合模式（推荐，立即可行）

**不依赖代理，发挥我们已验证成功的方案优势：**

```
XHR 注入（已验证成功） + 自动 Cookie 注入 + 账号轮询
```

具体做法：
- 用 Electron **只用来控制浏览器行为**（注入 Cookie、注入 XHR 拦截脚本）
- 但页面渲染用 **系统真实 Chrome**（通过 CDP 协议连接）
- 通过 CDP (Chrome DevTools Protocol) 连接到用户正在使用的 Chrome 浏览器
- 在真实 Chrome 中执行页面操作和拦截

```
CDP 连接真实 Chrome → 注入 Cookie → 注入 XHR 拦截脚本
                                          ↓
用户操作网页 → XHR 拦截 → 捕获支付码 → 写入数据库
```

**优势**：
- ✅ 使用用户真实 Chrome → 没有 TLS 指纹问题
- ✅ 不受页面 CSP 限制（CDP 注入的脚本在 Chrome 层面执行）
- ✅ 不依赖任何代理
- ✅ 可以控制多个账号的 Cookie 注入
- ✅ 今天 POC 已验证了 XHR 拦截本身是可行的

### 方案 D：像 Fiddler Everywhere 那样做

Fiddler Everywhere 是跨平台版的 Fiddler，它实际上把 mitmproxy 包了一层（Fiddler Everywhere 的引擎基于 mitmproxy！）。关键区别是它对证书做了特殊处理：

1. 使用 OpenSSL 生成标准 CA 证书（非 Go 生成）
2. 正确设置了 X.509 v3 扩展
3. 操作系统级别的信任链

我们可以复制这个思路：用 OpenSSL 生成 CA 证书替代 mitmproxy 自生成的证书。

## 建议路线

**短期**：用 CDP + 真实 Chrome（方案 C），立即可行，已验证核心逻辑

**长期**：构建基于 WinDivert 的透明代理（方案 B），彻底解决代理检测问题
