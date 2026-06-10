# 神谕 v1.0 — 全局审查报告

## 已完成

| 模块 | 功能 | 状态 |
|------|------|------|
| WinDivert 捕获 | SNIFF 模式捕获 443 端口流量，SNI 域名过滤 | ✅ |
| SChannel MITM | 动态证书生成，TLS 握手，双向转发 | ✅ |
| HTTP 解析 | HTTP/1.1 请求行 + 头部 + Body 解析 | ✅ |
| 规则引擎 | JSON 数据驱动，热加载，匹配 + 提取 | ✅ |
| 凭证队列 | 批量上报到 Python 工具端 | ✅ |
| 管理 API | /status /start /stop /config /inject | ✅ |
| 可扩展性 | platforms/*.json 定义平台，加平台加 JSON | ✅ |

## 发现的遗漏

### 1. 🔴 TLS 代理与捕获层未打通

**当前状态：**
- WinDivert 在 SNIFF 模式下**只是复制包**，不重定向到 TLS 代理
- TLS 代理在 18802 端口**被动等待**，没有流量自动流向它
- 两者之间是断开的

**后果：**
- 必须手动 `--resolve` 才能测试 TLS 代理
- 真实的浏览器流量不会被解密
- 凭证提取 Pipeline 永远不会收到真实数据

**解决方案：** 有两个方向

| 方向 | 原理 | 工作量 |
|------|------|--------|
| **A: HTTP CONNECT 代理** | TLS 代理同时支持 CONNECT 协议，浏览器设代理即可用 | ~50 行 |
| **B: WinDivert DIVERT 模式** | 驱动拦截支付域名，重定向到 TLS 代理 | 需解决网络断连 |

**方向 A 更务实**——Fiddler 就是这么干的。浏览器原生支持 HTTPS 代理，根本不需要 WinDivert 参与 TLS 解密。我们的 TLS 代理只需要加一个 CONNECT 处理分支。

### 2. 🟡 管线未端到端验证

**未测试的链路：**
```
浏览器 → [代理] → Oracle TLS 代理 → 凭证提取 → Python 工具端
```

当前只验证了：
```
curl --resolve → TLS 代理 → 腾讯服务器 ✅
curl --resolve → TLS 代理 → 无凭证提取（因为没有真实支付响应）
```

### 3. 🟡 退出时凭证丢失

`CredentialQueue` 中的凭证在进程被 Kill 时丢失。应该：
- 停止时 flush 队列
- 或写到磁盘临时文件

### 4. 🟢 规则引擎错误信息不明确

JSON 加载失败时只说 "Failed to load"，没有具体行号或字段名。

### 5. 🟢 性能考虑

当前每收到一个 HTTPS 包都要完整解析并提取。在 1000+ QPS 下 CPU 可能成为瓶颈（不过这是后续优化点）。

## 当前架构的真正价值

```
Oracle 引擎目前已经搭建了完整的数据管道：
  网络包 → TLS 解密 → HTTP 解析 → 规则匹配 → 凭证提取 → 批量上报 → Python 工具端

缺少的只是"流量如何进入这个管道"的最后一环。
```

## 建议

**方向 A（CONNECT 代理）是当前最务实的补全方案：**

```
浏览器设置代理到 127.0.0.1:18802
  → Chrome 发送 CONNECT api.unipay.qq.com:443 HTTP/1.1
  → Oracle 响应 200 Connection Established
  → Chrome 发送 TLS ClientHello（认为已连接到腾讯服务器）
  → Oracle 用 SChannel 做 MITM（生成假证书）
  → 解密流量 → HTTP 解析 → Pipeline 提取
  → 加密后转发到真实的腾讯服务器
```

这就是 Fiddler 的工作原理。而且我们不需要 WinDivert 参与——Chrome 原生就支持这种方式。

加 ~50 行代码即可实现。
