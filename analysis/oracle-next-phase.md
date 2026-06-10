# 神谕 (Oracle) 下一阶段 — 全应用透明捕获架构

## 现状与目标

```
当前能力:
  浏览器 CONNECT 代理 → ✅ 完整捕获
  WinDivert SNIFF     → ✅ 流量监控（只读）
  微信小程序/端游      → ❌ 无法捕获

下一阶段目标:
  系统级透明代理 → 零配置自动捕获所有应用的支付流量
```

## 方案全景对比

| 方案 | 原理 | 浏览器 | 微信小程序 | PC端游 | 复杂度 | 稳定性 |
|------|------|--------|-----------|--------|--------|--------|
| ① **DNS 劫持 + TLS 代理** | 伪造 DNS 返回 127.0.0.1，应用连过来 | ✅ | ✅ | ✅ | ⭐⭐ | ⭐⭐⭐⭐ |
| ② **WFP 连接重定向** | 内核态拦截 connect()，透明转给代理 | ✅ | ✅ | ✅ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| ③ **TUN 虚拟网卡** | 全流量走虚拟网卡，用户态处理 | ✅ | ✅ | ✅ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| ④ **WinDivert DNS + TUN 混合** | DNS 劫持 + TUN 兜底 | ✅ | ✅ | ✅ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 方案 ①：DNS 劫持 + TLS 代理（推荐）

### 原理

```
App 请求 pay.qq.com
  → 系统 DNS 查询 (UDP 53)
  → WinDivert 拦截 DNS 响应
  → 修改响应 IP 为 127.0.0.1
  → App 连接 127.0.0.1:443
  → TLS 代理接收 → 提取 SNI → 连接真实服务器 → MITM
```

### 关键组件

```python
# WinDivert DNS 劫持
class DnsSpoofer:
    """DNS 响应劫持器 — 将支付域名的 DNS 响应替换为 127.0.0.1"""

    SPOOF_DOMAINS = {"pay.qq.com.", "api.unipay.qq.com.", ...}
    SPOOF_IP = 0x0100007F  # 127.0.0.1 in network byte order

    def handle_dns_response(self, packet):
        """拦截 DNS 响应，检查是否包含支付域名"""
        dns = DnsPacket(packet)
        for question in dns.questions:
            if question.name in self.SPOOF_DOMAINS:
                # 修改 A 记录为 127.0.0.1
                dns.set_answer(question.name, self.SPOOF_IP)
                # 重新计算 DNS 校验和
                packet.payload = dns.to_bytes()
                return packet  # 发回修改后的包
        return packet  # 原样转发
```

```csharp
// TLS 代理 — 需要支持 SNI 回退
// 当客户端直接连到 127.0.0.1:443 时，
// 从 ClientHello 提取 SNI 来确定目标服务器
public class TlsProxy
{
    // 现有逻辑已支持：读取 ClientHello → 提取 SNI → 连接真实服务器
    // 只需要添加：
    //   - 监听 443 端口（除了 18802）
    //   - 按 SNI 白名单决定是否 MITM
    //   - 非支付域名 SNI → 直接透传（不做 MITM）
}
```

### 优点
- **不需要修改 TCP 包** — DNS 是 UDP，修改后重发校验和即可
- **所有应用受影响** — 只要应用做 DNS 解析就会命中
- **TLS 代理已有** — 只需加 443 端口监听
- **白名单控制** — 只劫持支付域名，其他不受影响

### 局限性
- 应用硬编码 IP 时无效（如微信支付有时直接连 IP）
- DoH (DNS over HTTPS) 绕过 DNS 劫持
- 部分应用会验证 DNS 签名 (DNSSEC)

---

## 方案 ②：WFP 连接重定向（终极方案）

### 原理

Windows Filtering Platform (WFP) 是 Windows 网络栈的标准过滤接口。在 **ALE Connect 层**注册 callout，当应用发起 TCP 连接时，判断目标地址，重定向到本地代理。

```
App (任何应用)
  → connect(pay.qq.com:443)
  → WFP ALE Connect Layer
  → Callout 判断目标域名/IP → 重定向
  → TCP 连接到 127.0.0.1:18802
  → TLS 代理正常处理
```

### 架构

```
┌─────────────────────────────────────────────┐
│          WFP Callout Driver (C/C++)          │
│                                              │
│  ALE_CONNECT_REDIRECT_LAYER_V4               │
│  ├── 拦截所有 TCP connect()                   │
│  ├── 检查目标 IP:Port                         │
│  │   ├── port == 443 AND ip in 支付列表       │
│  │   │   → 重定向到 127.0.0.1:18802          │
│  │   └── 否则 → 放行                         │
│  └── 通过 IOCTL 与用户态通信                   │
└──────────────────┬──────────────────────────┘
                   │ IOCTL / 共享内存
                   ▼
┌─────────────────────────────────────────────┐
│          Oracle 用户态 (.NET)                 │
│                                              │
│  ├── 管理 WFP 过滤规则                        │
│  ├── 动态更新支付 IP 列表                     │
│  ├── TLS 代理 (已有)                          │
│  └── Pipeline 提取 (已有)                     │
└─────────────────────────────────────────────┘
```

### 实现要点

```c
// WFP Callout — 连接重定向
void ALEConnectRedirect(...) {
    // 获取目标地址
    SOCKADDR_IN* remoteAddr = ...;
    
    // 检查是否支付端口
    if (ntohs(remoteAddr->sin_port) != 443) return;
    
    // 检查是否支付 IP
    if (!IsPayIp(remoteAddr->sin_addr.S_un.S_addr)) return;
    
    // 重定向到本地代理
    FWPS_CONNECT_REQUEST* request = ...;
    request->localAddress = 127.0.0.1:18802;
    request->remoteAddress = 127.0.0.1:18802;
    FwpsRedirectConnect(request);
}
```

### 优点
- **最彻底的方案** — 所有 TCP 连接都能重定向
- **不需要 DNS 劫持** — 在 connect() 层面处理
- **无需修改包** — WFP 处理重定向，包内容不变
- **白名单过滤** — 只重定向支付域名/IP

### 局限性
- Callout 驱动必须用 C/C++ 开发
- Windows 驱动签名要求（Win 10/11 需要 EV 证书签名）
- 开发周期长（估计 3-4 周）

---

## 方案 ③：TUN 虚拟网卡 + 路由表

### 原理

安装一个虚拟网络适配器（TUN），修改系统路由表让所有流量经过它，在用户态做过滤和转发。

```
所有流量 → TUN 虚拟网卡 → 用户态程序
                          ├── 支付域名 → TLS 代理 → MITM
                          └── 其他 → 原生转发
```

### 优点
- **成熟技术** — OpenVPN TAP 驱动、Tun2Socks 等有成熟实现
- **用户态处理** — 不需要写内核代码
- **跨平台** — TUN 在 Linux/macOS 上也有

### 局限性
- 需要安装虚拟网卡驱动（需管理员）
- 全流量经过用户态，性能受影响
- 路由表冲突风险
- 需要处理 ARP、ICMP 等协议

---

## 推荐路线

```
Phase 1（当前）: CONNECT 代理 → 浏览器捕获 ✅
Phase 2（2周） : DNS 劫持 (WinDivert) → 覆盖大部分应用
Phase 3（3-4周）: WFP Callout → 完全透明捕获
```

### Phase 2 实现要点

```
WinDivert 过滤规则改为:
  (outbound and tcp.DstPort == 443) OR
  (udp.DstPort == 53 and udp.PayloadLength > 0)

DNS 劫持流程:
  WinDivertRecv DNS 响应
    → 解析 DNS 包
    → 匹配支付域名 → 修改 A 记录为 127.0.0.1
    → 重新计算校验和
    → WinDivertSend（DIVERT 模式，只改 DNS 不改 TCP）

TLS 代理改动:
  监听 443 端口（新增）
  按 SNI 白名单过滤 → 是支付域名则 MITM，否则透传
```

### 为什么跳过 WinDivert TCP 重定向

WinDivert 在 TCP 层面的 DIVERT 模式有根本性问题：
1. 无法在 SYN 阶段识别域名（还没有 SNI）
2. TCP 流状态跟踪复杂，容易丢包
3. 校验和修改后容易出问题

**DNS 劫持 + TLS 代理可以完全绕过这些问题**，因为：
1. DNS 是 UDP（无状态，修改简单）
2. DNS 响应中包含完整的域名
3. 应用自己发起到 127.0.0.1 的 TCP 连接（正常的 TCP 握手）
4. TLS 代理已有完整的 SChannel MITM 实现

## 结论

**推荐路线：DNS 劫持（Phase 2）→ WFP Callout（Phase 3）**

DNS 劫持用 2 周可以覆盖 90% 的应用场景，WFP 是终极方案覆盖剩下的 10%。
