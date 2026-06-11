# 神谕 (Oracle) — 技术架构 v2

> 技术方案说明书
> 版本：2.0
> 日期：2026-06-11
> 配套文档：`08-oracle-product-spec-v2.md`（产品规格）

---

## 目录

1. [架构总览](#一架构总览)
2. [通道层 (Channel Layer)](#二通道层-channel-layer)
3. [协议层 (Protocol Layer)](#三协议层-protocol-layer)
4. [提取层 (Extraction Layer)](#四提取层-extraction-layer)
5. [输出层 (Output Layer)](#五输出层-output-layer)
6. [目标注册表 (Target Registry)](#六目标注册表-target-registry)
7. [反检测机制](#七反检测机制)
8. [Windows 流量截获技术选型详解](#八windows-流量截获技术选型详解)
9. [部署架构](#九部署架构)
10. [扩展指南](#十扩展指南)

---

## 一、架构总览

### 核心理念

> **通道层负责"怎么拿数据"，协议层负责"怎么解析数据"，提取层负责"要什么数据"——三层完全解耦。**

每一层都可以独立替换、独立扩展。加一个新的数据来源，不需要改任何其他层的代码。

### 分层架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              神谕 (Oracle) 引擎                              │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        目标注册表 (Target Registry)                     │  │
│  │                                                                       │  │
│  │  用户定义: { "name": "QQ支付", "domain": "api.unipay.qq.com",         │  │
│  │              "channel": ["WinDivert","DnsSpoof","TlsProxy"],          │  │
│  │              "extract": ["weixin_url","openid"] }                     │  │
│  └──────────────────────────────┬────────────────────────────────────────┘  │
│                                 │                                            │
│                         路由决策引擎                                          │
│                    (根据Target自动选择Channel)                                │
│                                 │                                            │
│           ┌─────────────────────┼─────────────────────┐                     │
│           ▼                     ▼                     ▼                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                │
│  │   通道层         │  │   协议层        │  │   提取层        │                │
│  │  (Channel)      │  │  (Protocol)    │  │  (Extractor)   │                │
│  │                 │  │                │  │                │                │
│  │  WinDivert ────▶│  │  HTTP/1.1 ────▶│  │  规则引擎 ─────▶│──▶ 输出       │
│  │  DnsSpoof  ────▶│  │  HTTPS/MITM ──▶│  │  (JSON规则)    │                │
│  │  WFP Callout ──▶│  │  WebSocket ──▶│  │                │                │
│  │  进程注入 ─────▶│  │  自定义协议 ──▶│  │  脚本提取       │                │
│  │  TUN/TAP ──────▶│  │                │  │  (JS/Lua)      │                │
│  │  CDP注入 ──────▶│  │                │  │                │                │
│  └────────────────┘  └────────────────┘  └────────────────┘                │
│         │                    │                     │                        │
│         └────────────────────┴─────────────────────┘                        │
│                               │                                             │
│                       统一数据管道                                            │
│                  NormalizedTransaction → Credential                         │
│                               │                                             │
│                               ▼                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          输出层 (Output)                              │  │
│  │                                                                       │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │  │
│  │  │Dashboard │  │HTTP POST │  │WebSocket │  │文件导出   │             │  │
│  │  │(本地展示) │  │(Python端)│  │(实时推送) │  │(CSV/JSON)│             │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 数据流转全链路

```
WinDivert 捕获网络包
    │
    ▼
DnsSpoofer 劫持 DNS 响应 → 目标域名指向 127.0.0.1
    │
    ▼
TlsProxy 接收连接 → SChannel MITM 解密
    │  (JA3 指纹 = Chrome，腾讯无法检测)
    ▼
Protocol Parser 解析 HTTP/HTTPS 内容
    │  (也支持 WebSocket、二进制协议等)
    ▼
Rule Engine 匹配目标规则 → 提取结构化数据
    │
    ▼
Credential → 同时写入:
    ├── Dashboard（WebSocket 实时推送）
    ├── CredentialQueue → HTTP POST → Python 后端
    └── 本地日志文件（CSV/JSON）
```

---

## 二、通道层 (Channel Layer)

### 2.1 核心接口

```csharp
/// <summary>
/// 采集通道接口。
/// 每一种数据采集方式实现一个 Channel。
/// Channel 之间完全独立，互不依赖。
/// </summary>
public interface ICaptureChannel
{
    /// <summary>通道唯一标识，如 "WinDivert"、"DnsSpoof"</summary>
    string Name { get; }

    /// <summary>人类可读的描述</summary>
    string Description { get; }

    /// <summary>通道能力声明（供路由决策使用）</summary>
    ChannelCapability Capability { get; }

    /// <summary>初始化（安装驱动、分配资源等）</summary>
    Task<bool> InitializeAsync();

    /// <summary>开始采集</summary>
    Task StartAsync();

    /// <summary>停止采集</summary>
    Task StopAsync();

    /// <summary>健康检查</summary>
    bool IsHealthy { get; }

    /// <summary>采集到的原始数据事件</summary>
    event Action<RawPacket> OnPacket;
}

/// <summary>
/// 通道能力声明。
/// 路由引擎根据 Target 需求匹配 Channel。
/// </summary>
public class ChannelCapability
{
    /// <summary>是否需要管理员权限</summary>
    public bool RequiresAdmin { get; set; }

    /// <summary>能否解密 TLS</summary>
    public bool CanDecryptTls { get; set; }

    /// <summary>支持的协议列表</summary>
    public string[] SupportedProtocols { get; set; }

    /// <summary>是否需要安装 CA 证书</summary>
    public bool RequiresCertInstall { get; set; }

    /// <summary>覆盖范围描述</summary>
    public string ScopeDescription { get; set; }
}

/// <summary>
/// 原始数据包。
/// 这是从 Channel 产出的统一格式。
/// 后续由协议层解析。
/// </summary>
public class RawPacket
{
    public byte[] Data { get; set; }          // 原始字节
    public string SourceChannel { get; set; } // 来源 Channel 名称
    public DateTime Timestamp { get; set; }   // 捕获时间戳
    public PacketMetadata Metadata { get; set; } // 来源元数据
}

public class PacketMetadata
{
    public string Protocol { get; set; }       // 检测到的协议
    public string Sni { get; set; }            // TLS SNI
    public int SourcePort { get; set; }
    public int DestPort { get; set; }
    public string SourceAddress { get; set; }
    public string DestAddress { get; set; }
    public int ProcessId { get; set; }         // 来源进程 ID（WFP 支持）
    public string ProcessName { get; set; }    // 来源进程名（WFP 支持）
}
```

### 2.2 通道生命周期

```
          Register      Initialize       Start        Stop     Unregister
              │              │              │           │           │
    ┌─────────▼──────────┐   │              │           │           │
    │     Registered      │   │              │           │           │
    └─────────────────────┘   │              │           │          
              │                ▼              │           │
              │         ┌────────────┐        │           │
              └─────────▶  Initialized │        │           │
                        └──────┬─────┘        │           │
                               │               ▼           │
                               │        ┌───────────┐      │
                               └────────▶  Running   │      │
                                        └─────┬─────┘      │
                                              │             │
                                              ▼             │
                                        ┌───────────┐      │
                                        │  Stopped   │──────┘
                                        └───────────┘

初始化异常 → Failed 状态 → ChannelManager 自动重试（最多 3 次）
运行异常 → 自动重启 + 日志告警
健康检查失败 → 标记异常 → 路由引擎自动切换备用 Channel
```

### 2.3 通道管理器 (ChannelManager)

```csharp
/// <summary>
/// 通道管理器 — 统一管理所有 Channel 的注册、启停、路由。
/// </summary>
public class ChannelManager
{
    private readonly Dictionary<string, ICaptureChannel> _channels = new();

    /// <summary>注册一个通道</summary>
    public void Register(ICaptureChannel channel) { ... }

    /// <summary>根据 Target 自动匹配最优通道集合</summary>
    public ICaptureChannel[] SelectChannels(Target target)
    {
        // 匹配逻辑：
        // 1. 遍历所有已注册的 Channel
        // 2. 匹配 Capability 和 Target 需求
        // 3. 按优先级排序（精确匹配 > 模糊匹配）
        // 4. 返回得分最高的 N 个
    }

    /// <summary>启动所有通道</summary>
    public async Task StartAllAsync() { ... }

    /// <summary>停止所有通道</summary>
    public async Task StopAllAsync() { ... }

    /// <summary>健康巡检（按配置间隔执行）</summary>
    public async Task HealthCheckAsync()
    {
        foreach (var ch in _channels.Values)
        {
            if (!ch.IsHealthy)
            {
                Log.Warn($"Channel {ch.Name} 异常，尝试重启...");
                await ch.StopAsync();
                await ch.InitializeAsync();
                await ch.StartAsync();
            }
        }
    }
}
```

### 2.4 内置通道清单

#### WinDivertChannel

```
用途: 最底层的网络包捕获
实现: WinDivert 内核驱动 (P/Invoke)
状态: ✅ 已有 (WinDivertDriver.cs)
覆盖: PC 上所有应用的 TCP/443 流量
限制:
  - 只能看包级别，没有进程关联
  - 需要驱动签名 (Win11 强制)
  - 被检测风险 (anti-cheat 扫描驱动列表)

数据产出:
  RawPacket.Data = TCP 负载（可能是 TLS ClientHello 等）
  Metadata.Sni = 从 ClientHello 提取的 SNI
  Metadata.DestPort = 443
```

#### DnsSpoofChannel

```
用途: DNS 响应劫持，将支付域名指向 127.0.0.1
实现: 独立的 WinDivert 实例 (DIVERT 模式, UDP 53)
状态: ✅ 已有 (DnsSpoofer.cs)
覆盖: 所有走系统 DNS 解析的应用
关键:
  - 必须同时劫持 A 记录 (IPv4 → 127.0.0.1)
  - AND AAAA 记录 (IPv6 → ::1)
  - 目的: 让客户端 QUIC over IPv6 失败 → 降级 TCP over IPv4
  - 这是我们破解 QUIC 的关键手段

数据产出: 无直接产出（修改 DNS 响应，让流量流向 TlsProxy）
```

#### TlsProxyChannel

```
用途: TLS 中间人代理，解密 HTTPS 流量
实现: SChannel (Windows 原生 TLS, 通过 SslStream)
状态: ✅ 已有 (TlsProxy.cs)
覆盖: 所有被 DNS 劫持或手动设代理的 HTTPS 连接
关键:
  - 使用 SChannel = JA3 指纹和 Chrome 完全一致
  - 动态生成域名证书 (2048位 RSA, 1h 缓存)
  - 非支付域名 → 透传 (TransparentForward)
  - 支付域名 → MITM → 协议解析 → 提取

流程:
  Client → TlsProxy:443
    → 提取 SNI
    → 检查 Target Registry 是否匹配
    → 匹配: SChannel MITM (服务端 + 客户端双重握手)
    → 不匹配: 透传转发
    → 解密后的数据 → Protocol Layer
```

#### WfpQuicBlockChannel (规划中)

```
用途: 在系统 ALE 层阻止 QUIC 连接，强制降级 TCP
实现: WFP Callout 驱动
状态: 🔧 规划 (Phase 2)
覆盖: 全系统所有 QUIC 连接
关键:
  - 注册到 FWPM_LAYER_ALE_AUTH_CONNECT_V4
  - 检测: 协议=UDP, 端口=443, 且进程匹配目标
  - 动作: FWP_ACTION_BLOCK
  - 客户端发现 QUIC 失败 → 自动重试 TCP
  - 于是流量进入 WinDivert/DNS 劫持链路

这解决了当前架构中最大的能力缺口。
```

#### ProcessInjectChannel (规划中)

```
用途: 注入目标进程，hook 网络 API 获取解密后的数据
实现: Frida / MinHook
状态: 🔧 规划 (Phase 3)
覆盖: PC 端游、有证书固定的应用
关键:
  - 不需要 TLS 解密！hook 的是解密后的数据
  - 适用于做了 Certificate Pinning 的应用
  - 也可以 hook 加密函数的输入/输出

流程:
  Frida attach QQ.exe
    → hook schannel.dll!DecryptMessage
    → 在应用读取解密数据前截获
    → 直接拿到明文 HTTP 内容
    → 进入 Protocol Layer
```

#### AndroidEmulatorChannel (规划中)

```
用途: 控制 Android 模拟器，抓取手游流量
实现: ADB + 模拟器代理
状态: 🔧 规划 (Phase 3)
覆盖: 手游 (王者荣耀、和平精英等)
流程:
  模拟器启动
    → ADB 设置系统代理到宿主机 TlsProxy 端口
    → ADB 注入 CA 证书到模拟器系统证书存储
    → ADB 启动目标 App
    → 手游的 HTTP 流量经过 TlsProxy → MITM 解密
  ADB 命令:
    adb shell settings put global http_proxy 192.168.1.100:18802
    adb push oracle_ca.cer /sdcard/
    adb shell su -c "mv /sdcard/oracle_ca.cer /system/etc/security/cacerts/"
    adb shell am start -n com.tencent.tmgp.sgame/.MainActivity
```

---

## 三、协议层 (Protocol Layer)

### 3.1 核心接口

```csharp
/// <summary>
/// 协议解析器接口。
/// 每种协议 (HTTP/WebSocket/二进制) 实现一个。
/// 输入: RawPacket（来自任意 Channel）
/// 输出: NormalizedTransaction（统一结构化格式）
/// </summary>
public interface IProtocolParser
{
    /// <summary>协议名称</summary>
    string ProtocolName { get; }

    /// <summary>判断是否能解析这个数据包</summary>
    bool CanParse(ReadOnlySpan<byte> data);

    /// <summary>解析数据包</summary>
    ParseResult Parse(RawPacket rawPacket);
}

/// <summary>
/// 统一结构化请求/事务格式。
/// 不管数据来自 HTTP/WebSocket/自制协议，都转成这个格式。
/// </summary>
public class NormalizedTransaction
{
    public string Id { get; set; }             // 唯一 ID
    public string Method { get; set; }         // 方法 (GET/POST/或自定义)
    public string Host { get; set; }           // 目标主机
    public string Path { get; set; }           // 路径
    public Dictionary<string, string> Headers { get; set; }  // 请求头
    public string Body { get; set; }           // 请求体
    public int StatusCode { get; set; }        // 响应状态码 (如适用)
    public Dictionary<string, string> ResponseHeaders { get; set; }
    public string ResponseBody { get; set; }   // 响应体
    public DateTime Timestamp { get; set; }
    public string SourceChannel { get; set; }  // 来源通道
    public string Sni { get; set; }            // TLS SNI
    public int ProcessId { get; set; }         // 进程 ID
    public string ProcessName { get; set; }    // 进程名
}
```

### 3.2 协议解析器链

```
RawPacket.Data (byte[])
    │
    ├── HTTP/1.1 Parser ──── 检测: 以 GET/POST/ 开头
    │                        → 产出 NormalizedTransaction
    │
    ├── HTTP/2 Parser ────── 检测: 以 PRI * HTTP/2.0 开头
    │                        → 产出 NormalizedTransaction
    │
    ├── WebSocket Parser ──── 检测: WebSocket 升级帧
    │                        → 产出 NormalizedTransaction
    │
    ├── 自定义协议 Parser ─── 检测: 注册的协议特征
    │                        → 产出 NormalizedTransaction
    │
    └── 未知协议 ─────────── → RawPacket 标记未解析，跳过
```

### 3.3 协议解析器注册

```csharp
/// <summary>
/// 协议解析器注册表。
/// 新协议只需要 AddParser() 即可。
/// </summary>
public class ProtocolRegistry
{
    private readonly List<IProtocolParser> _parsers = new();

    public void AddParser(IProtocolParser parser) { ... }

    public IProtocolParser SelectParser(ReadOnlySpan<byte> data)
    {
        // 按注册顺序尝试，第一个 CanParse 返回 true 的就用它
        foreach (var parser in _parsers)
            if (parser.CanParse(data))
                return parser;
        return null; // 无法识别
    }
}
```

### 3.4 已实现 + 可扩展的协议

```
协议              状态        检测方式             备注
────────────────────────────────────────────────────────────
HTTP/1.1          ✅ 已有     GET/POST/PUT/DELETE    HttpParser.cs
HTTP/2            🔧 规划     PRI * HTTP/2.0        需要实现 HPACK 解码
WebSocket         🔧 规划     Upgrade: websocket    需要实现帧解析
TLS ClientHello   ✅ 已有     ContentType=0x16       TlsHelper.cs (只提取 SNI)
自定义二进制协议   🔧 可扩展   注册特征码            需要逆向分析
```

---

## 四、提取层 (Extraction Layer)

### 4.1 规则引擎

```csharp
/// <summary>
/// 提取规则。
/// 定义从 NormalizedTransaction 中提取什么数据、怎么提取。
/// </summary>
public class ExtractionRule
{
    public string Name { get; set; }                         // 规则名
    public string TargetId { get; set; }                     // 关联目标 ID
    public bool Enabled { get; set; } = true;

    // 匹配条件：满足所有条件才执行提取
    public List<Matcher> Matchers { get; set; }               // 匹配器列表

    // 提取器：从匹配的请求/响应中提取字段
    public List<Extractor> Extractors { get; set; }

    // 提取策略
    public ExtractionPolicy Policy { get; set; }              // 提取策略
}

public class Matcher
{
    public enum MatcherField { Domain, Path, Method, StatusCode, Header, Body }
    public enum MatcherOperator { Equals, Contains, Regex, Prefix }

    public MatcherField Field { get; set; }
    public MatcherOperator Operator { get; set; }
    public string Value { get; set; }
}

public class Extractor
{
    public enum ExtractSource { RequestBody, ResponseBody, RequestHeader, ResponseHeader, Url, Cookie }

    public string FieldName { get; set; }                     // 产出字段名
    public ExtractSource Source { get; set; }                  // 从哪提取
    public string Pattern { get; set; }                        // 正则表达式
    public int GroupIndex { get; set; } = 1;                   // 捕获组索引
    public string OutputField { get; set; }                    // 映射到凭证的哪个字段
}

public class ExtractionPolicy
{
    public bool FirstMatchOnly { get; set; } = true;           // 只取第一个匹配
    public bool IncludeRawData { get; set; } = false;          // 是否保留原始数据
    public int MaxBodySize { get; set; } = 100_000;            // 最大 body 解析大小
}
```

### 4.2 规则文件格式 (JSON)

```json
{
  "targets": [
    {
      "id": "qq_midas",
      "name": "QQ Midas 支付",
      "enabled": true,

      "channels": ["WinDivert", "DnsSpoof", "TlsProxy"],

      "protocol": "http",

      "matchers": [
        { "field": "domain", "operator": "contains", "value": "api.unipay.qq.com" },
        { "field": "path", "operator": "regex", "value": "(web_save|CommonCallMpgo|wechat_query)" }
      ],

      "extractors": [
        {
          "name": "支付链接",
          "source": "response_body",
          "pattern": "weixin://wxpay/bizpayurl\\?pr=[^\\s\"'<>)]+",
          "output_field": "value"
        },
        {
          "name": "openid",
          "source": "request_body",
          "pattern": "openid=([A-F0-9]+)",
          "output_field": "openid"
        },
        {
          "name": "支付方式",
          "source": "request_body",
          "pattern": "pay_method=(\\w+)",
          "output_field": "pay_method"
        },
        {
          "name": "商品ID",
          "source": "request_body",
          "pattern": "appid=(\\d+)",
          "output_field": "product_id"
        }
      ]
    },

    {
      "id": "tenpay_payment",
      "name": "微信支付 Tenpay",
      "enabled": true,

      "channels": ["WinDivert", "DnsSpoof", "TlsProxy"],

      "matchers": [
        { "field": "domain", "operator": "contains", "value": "wx.tenpay.com" }
      ],

      "extractors": [
        {
          "name": "支付链接",
          "source": "response_body",
          "pattern": "https?://wx\\.tenpay\\.com/[^\\s\"']+",
          "output_field": "value"
        }
      ]
    }
  ]
}
```

### 4.3 提取结果统一模型

```csharp
public class Credential
{
    public string Id { get; set; } = $"cred_{Guid.NewGuid():N}";
    public string Type { get; set; }              // 凭证类型
    public string Value { get; set; }             // 提取的值
    public string Platform { get; set; }          // 平台标识
    public string TargetId { get; set; }          // 关联目标
    public string Source { get; set; }            // 来源描述
    public string AccountName { get; set; }       // 关联账号

    // 可扩展字段：提取规则可以任意添加
    public Dictionary<string, string> Metadata { get; set; } = new();

    public DateTime CapturedAt { get; set; } = DateTime.UtcNow;
}
```

### 4.4 规则热加载

```
规则文件存储在: C:\Oracle\platforms\*.json

启动时:
  1. 扫描 platforms/ 目录
  2. 加载所有 .json 文件
  3. 构建匹配树（优化查询性能）
  4. 启动 FileSystemWatcher 监听文件变更

运行时:
  用户修改/新增 JSON 文件 → FileSystemWatcher 触发
    → 重新加载变更文件
    → 更新匹配树
    → 下次请求生效（无需重启）

状态:
  - 每条规则显示 "生效/失效" 状态
  - Dashboard 上有规则总数、生效数
  - 语法错误时回滚到上一个有效版本 + 日志告警
```

---

## 五、输出层 (Output Layer)

### 5.1 输出接口

```csharp
public interface ICredentialOutput
{
    string Name { get; }
    Task OutputAsync(Credential credential);
    Task FlushAsync();
}

public class OutputManager
{
    private readonly List<ICredentialOutput> _outputs = new();

    public void AddOutput(ICredentialOutput output) { ... }

    public async Task EmitAsync(Credential credential)
    {
        foreach (var output in _outputs)
        {
            try { await output.OutputAsync(credential); }
            catch (Exception ex) { Log.Error($"输出失败 [{output.Name}]: {ex.Message}"); }
        }
    }
}
```

### 5.2 内置输出

```
输出                类型         说明
──────────────────────────────────────────────────
Dashboard          内存+WebSocket  实时推送到前端展示
CredentialQueue    HTTP POST      批量上报到 Python 后端
LogFile            文件日志       按日滚动的 CSV/JSON 文件
EventLog           Windows 事件日志   系统级审计日志
```

---

## 六、目标注册表 (Target Registry)

### 6.1 核心逻辑

```
Target Registry 是整个系统的"路由表"：

输入: 一个网络连接 (SNI + 端口 + 协议)
输出: 匹配的 Target 列表 + 需要的 Channel

决策流程:

  网络连接建立
    │
    ▼
  提取 SNI (例如: api.unipay.qq.com)
    │
    ▼
  Target Registry 查询:
    ├── 域名匹配 → api.unipay.qq.com 匹配 qq_midas target
    ├── 路径匹配 → 需要在 TLS 解密后进一步匹配
    └── 进程匹配 → 如果有 WFP，匹配进程名 QQ.exe
    │
    ▼
  决策结果:
    ┌──────────────────────────────────────────┐
    │ Target: qq_midas                         │
    │ 需要 Channel: [DnsSpoof, TlsProxy]       │
    │ 需要 MITM: true                          │
    │ 提取规则: qq_midas.json                  │
    └──────────────────────────────────────────┘
    │
    ▼
  ChannelManager 确保所需 Channel 已启动
    │
    ▼
  流量进入 TlsProxy MITM 解密
```

### 6.2 查询优化

```
匹配树结构（预编译，O(1) 查询）：

            ┌──────────────────┐
            │   域名索引        │
            │   (哈希表)        │
            └────────┬─────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
  api.unipay   wx.tenpay.com   qpay.qq.com
        │            │            │
        ▼            ▼            ▼
  ┌─────────┐  ┌─────────┐  ┌─────────┐
  │路径匹配器│  │路径匹配器│  │路径匹配器│
  │ (Trie)  │  │ (Trie)  │  │ (Trie)  │
  └────┬────┘  └────┬────┘  └────┬────┘
       │            │            │
       ▼            ▼            ▼
  ┌─────────┐  ┌─────────┐  ┌─────────┐
  │提取规则集│  │提取规则集│  │提取规则集│
  └─────────┘  └─────────┘  └─────────┘

查询复杂度: O(1) 域名哈希 + O(m) 路径 Trie 匹配 (m=路径长度)
```

---

## 七、反检测机制

### 7.1 反 TLS 指纹检测

```
目标: 腾讯服务器通过 JA3 指纹识别中间人代理

技术                   检测风险    方案
──────────────────────────────────────────
mitmproxy (Go crypto)   高        ❌ JA3 = Go，明显不同
OpenSSL MITM            中        ⚠️ JA3 与 Chrome 部分不同
SChannel MITM           极低      ✅ JA3 与 Chrome 完全一致（相同 TLS 库）
进程注入 (Frida)        无        ✅ 不涉及 TLS，直接拿解密数据

结论:
  - 浏览器/PC QQ: SChannel MITM ✅
  - 有证书固定的应用: Frida 进程注入 ✅
  - 永远不直接用 Go/OpenSSL 做 MITM
```

### 7.2 反证书固定 (Certificate Pinning)

```
应用内置了证书固定检测:
  比较服务器证书公钥是否匹配预设值
  SChannel 伪造的证书公钥不匹配 → 连接拒绝

绕过方案（三选一，按优先级）:

方案 A: 不绕过，走浏览器
  通过 CDP 控制 Chrome 访问目标页面
  Chrome 自己管理证书链，不需要我们处理
  适用于所有 Web 场景

方案 B: Frida 进程注入
  Hook 证书验证函数 (CertVerifyCertificateChainPolicy)
  让固定检查总是返回成功
  适用于 PC 客户端

方案 C: Hyper-V 虚拟机
  在虚拟机内安装真实证书
  应用以为自己连的是真实服务器
  适用于最顽固的场景
```

### 7.3 反驱动态检测

```
一些应用 (如腾讯 ACE/TP) 会扫描已加载的驱动列表:

可检测的驱动:
  WinDivert.sys ← 在驱动列表中可见
  TAP-Windows.sys ← 可见
  OpenVPN TAP ← 可见

不可检测的驱动:
  WFP Callout ← Windows 原生组件，不被扫描
  NDIS LWF ← 极底层，安全软件级别的隐藏

策略:
  Phase 1: WinDivert 验证管道，不担心检测
  Phase 2: 对需要反检测的场景走 WFP
  Phase 3: 对最强保护的场景走进程注入/虚拟机
```

---

## 八、Windows 流量截获技术选型详解

### 8.1 全景对比

```
技术              层级           API 难度   检测难度   进程关联    QUIC 处理    维护方
────────────────────────────────────────────────────────────────────────────────────
WinDivert         网络/传输层     ★☆☆        ★★★       ❌        ❌          开源(个人)
WFP Callout       应用/传输/网络层 ★★★★       ★★★★★     ✅        ✅          微软
TUN/TAP           网络层(虚拟网卡) ★★        ★★★★★     ❌        ✅(IP层面)   OpenVPN/自研
NDIS LWF          链路层(最底层)   ★★★★★     ★★★★★     ❌        ✅          微软
eBPF for Windows  可编程内核      ★★★        ★★★★★     ❌        ❌(能力有限) 微软
WinpkFilter(商业)  NDIS 封装       ★★         ★★★★      ❌        ✅          商业公司
CDP/DevTools      浏览器应用层     ★☆☆        ★         ✅        N/A         Chrome
进程注入(Frida)   应用层          ★★         ★★★       ✅(目标进程) N/A        Frida
```

### 8.2 技术选型矩阵（按场景）

```
场景             推荐技术    备选        理由
────────────────────────────────────────────────────
浏览器 HTTPS 捕获  SChannel MITM  CDP      浏览器走 CONNECT 代理，SChannel JA3 匹配
PC 应用 HTTPS 捕获  DNS 劫持 + SChannel  WFP     DNS 劫持将流量导入本地代理
QUIC 降级 TCP     WFP Callout    DNS AAAA 伪造  WFP 在连接前阻止 QUIC，最可靠
手机热点捕获       TUN 虚拟网卡    WFP 转发   TUN 天然适合路由手机流量到本地
证书固定绕过       Frida 进程注入  Hyper-V   Hook 证书验证函数
反检测要求高       WFP Callout    NDIS LWF  WFP 是 Windows 原生，不会被检测
快速原型验证       WinDivert      手动代理    API 最简单，支持 SNIFF/DIVERT 双模式
```

### 8.3 推荐技术演进路线

```
                    ┌──────────────────────┐
                    │  Phase 1 (现在)       │
                    │                      │
                    │  WinDivert + DNS劫持  │
                    │  + SChannel MITM     │
                    │                      │
                    │  覆盖: 浏览器HTTP/PC应用│
                    │  检测风险: 中          │
                    │  开发投入: 低          │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Phase 2 (1月后)      │
                    │                      │
                    │  + WFP QUIC 阻断      │
                    │  + WFP 进程过滤       │
                    │                      │
                    │  覆盖: + PC QQ 客户端  │
                    │  检测风险: 极低        │
                    │  开发投入: 中(写一个驱动)│
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Phase 3 (2月后)      │
                    │                      │
                    │  + Frida 进程注入      │
                    │  + Android 模拟器     │
                    │                      │
                    │  覆盖: + 端游 + 手游   │
                    │  检测风险: 无(TLS绕过) │
                    │  开发投入: 中          │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Phase 4 (远期)       │
                    │                      │
                    │  + TUN 虚拟网卡       │
                    │  + Hyper-V 集成       │
                    │                      │
                    │  覆盖: + 手机热点     │
                    │  检测风险: 极低        │
                    │  开发投入: 高          │
                    └──────────────────────┘
```

### 8.4 WinDivert vs WFP — 详细技术对比

```
比较项              WinDivert               WFP Callout
────────────────────────────────────────────────────────────────
作者/维护方        basil00 (个人)          微软 (Windows 团队)
开源              是 (BSD License)         否 (Windows DDK 示例)
许可费用           免费                     Windows Driver Kit 免费

API 复杂度         低 (几十个函数)         高 (数百个 API + 内核编程)
开发语言           C#/C++/Python/Pascal    C/Driver Kit
用户态接口         WinDivert.dll           无需，WFP 自带
安装方式           注册驱动服务             通过 INF 安装驱动

驱动签名           需要 EV 代码签名         需要 WHQL 签名
Win11 兼容性       有潜在问题 (严格签名)    完全兼容

检测规避           可被扫描驱动列表         不可检测 (Windows 原生)
Anti-cheat         腾讯ACE/TP 可检测       无法检测

过滤粒度           包级 (IP 头 + 负载)      连接级 (ALE) + 包级 + 流级
进程关联           不支持                   原生支持 (ALE 层获取 PID)
连接重定向         修改 IP 头 (包级)         FwpsRedirectHandle (连接级)

QUIC 阻断          不支持 (只能看 UDP 包)    ALE 层直接阻止 UDP 443

性能               中 (用户态-内核态切换)    高 (内核态执行)
可靠性             中 (第三方驱动)          高 (微软内核组件)

学习资源           多 (文档 + 示例 + 社区)   少 (微软文档 + 少量示例)

结论:
  WinDivert: 快速上手，适合原型验证
  WFP:      产品化选择，适合生产部署

  → 先用 WinDivert 跑通全链路
  → 再在 Phase 2 引入 WFP 解决 QUIC 和检测问题
  → 两者可以共存：WinDivert 负责数据面，WFP 负责控制面
```

---

## 九、部署架构

### 9.1 目录结构

```
C:\Oracle\
├── Oracle.Service.exe          # Windows 服务 (核心引擎)
├── Oracle.Console.exe          # 控制台版本 (调试用)
├── Oracle.Tray.exe             # 托盘图标程序
├── WinDivert.dll               # WinDivert 运行时
├── WinDivert64.sys             # WinDivert 内核驱动
│
├── wwwroot/                    # Dashboard 前端
│   ├── index.html
│   ├── app.js
│   └── style.css
│
├── platforms/                  # 规则文件 (热加载)
│   ├── qq_midas.json
│   ├── tenpay.json
│   └── wechat_pay.json
│
├── data/                       # 数据存储
│   └── credentials.db          # SQLite 本地缓存
│
├── logs/                       # 日志
│   ├── oracle-2026-06-11.log
│   └── crash_dumps/
│
├── certs/                      # 证书
│   └── oracle_ca.p12           # 根 CA (DPAPI 加密)
│
└── config.json                 # 主配置
```

### 9.2 进程模型

```
┌────────────────────────────────────────────────────────┐
│  进程: Oracle.Service.exe                               │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  主线程                                           │  │
│  │  ← 初始化所有组件                                  │  │
│  │  ← 启动健康检查定时器                               │  │
│  │  ← 等待停止信号                                    │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │  Channel 线程池    │  │  ASP.NET Core Web 服务    │   │
│  │                   │  │                          │   │
│  │  WinDivert 循环    │  │  GET  /status            │   │
│  │  DnsSpoofer 循环   │  │  POST /start             │   │
│  │  TlsProxy 循环     │  │  POST /stop              │   │
│  │  WFP 回调          │  │  GET  /stats             │   │
│  │                   │  │  GET  /config             │   │
│  │                   │  │  GET  /platforms          │   │
│  │                   │  │  GET  /data               │   │
│  │                   │  │  WS   /events (实时推送)   │   │
│  └──────────────────┘  └──────────────────────────┘   │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  辅助线程                                         │  │
│  │  ← CredentialQueue 批量发送                       │  │
│  │  ← 连接跟踪器超时清理                              │  │
│  │  ← 规则文件热加载                                  │  │
│  │  ← 健康检查                                       │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

### 9.3 服务管理

```
安装服务:
  sc create OracleService binPath="C:\Oracle\Oracle.Service.exe"
  sc description OracleService "神谕数据采集引擎"
  sc start OracleService

启动参数:
  Oracle.Service.exe
    --install       安装为服务
    --uninstall     卸载服务
    --start         启动服务
    --console       前台运行（调试用）

服务恢复策略（Windows 服务管理器配置）:
  第一次失败: 等待 10 秒后重启
  第二次失败: 等待 30 秒后重启
  后续失败: 等待 60 秒后重启
  重置失败计数: 24 小时后
```

---

## 十、扩展指南

### 10.1 如何添加一个新的采集目标

```
不需要改代码，只需要写一个 JSON 文件:

1. 创建 target JSON 文件
  C:\Oracle\platforms\my_game.json

2. 写入目标配置
  {
    "targets": [{
      "id": "my_game",
      "name": "我的游戏支付",
      "enabled": true,
      "channels": ["WinDivert", "DnsSpoof", "TlsProxy"],
      "matchers": [
        { "field": "domain", "operator": "regex", "value": "api\\.mygame\\.com" }
      ],
      "extractors": [
        { "name": "支付码", "source": "response_body",
          "pattern": "paycode=([A-Z0-9]+)", "output_field": "value" }
      ]
    }]
  }

3. 文件保存后自动热加载
  → Dashboard 上立刻显示新目标
  → 下次匹配的流量自动按新规则提取

完成。整个过程 2 分钟。
```

### 10.2 如何添加一个新的采集通道

```
需要写代码，但不需要改现有代码:

1. 实现 ICaptureChannel 接口
  public class MyNewChannel : ICaptureChannel
  {
      public string Name => "MyNewChannel";
      public string Description => "通过某新技术采集";
      public ChannelCapability Capability => new() { ... };

      public Task<bool> InitializeAsync() { ... }
      public Task StartAsync() { ... }
      public Task StopAsync() { ... }
      public bool IsHealthy { get; }

      public event Action<RawPacket> OnPacket;
  }

2. 注册到 ChannelManager
  channelManager.Register(new MyNewChannel());

3. 在 Target JSON 中引用
  {
    "channels": ["WinDivert", "MyNewChannel", ...]
  }

4. 无需改其他任何代码
```

### 10.3 如何添加一个新的协议解析器

```
1. 实现 IProtocolParser 接口
  public class MyProtocolParser : IProtocolParser
  {
      public string ProtocolName => "MyGameProtocol";

      public bool CanParse(ReadOnlySpan<byte> data)
      {
          // 检查数据特征码
          return data.Length > 4 && data[0] == 0xAA && data[1] == 0xBB;
      }

      public ParseResult Parse(RawPacket rawPacket)
      {
          // 解析自定义协议 → NormalizedTransaction
          return new ParseResult { Transaction = ... };
      }
  }

2. 注册到 ProtocolRegistry
  protocolRegistry.AddParser(new MyProtocolParser());

3. 无需改其他任何代码
```

### 10.4 如何添加新的输出方式

```
1. 实现 ICredentialOutput 接口
  public class MyOutput : ICredentialOutput
  {
      public string Name => "MyOutput";

      public Task OutputAsync(Credential credential)
      {
          // 写到消息队列、数据库等
      }

      public Task FlushAsync() { ... }
  }

2. 注册到 OutputManager
  outputManager.AddOutput(new MyOutput());

3. 无需改其他任何代码
```

### 10.5 扩展性总结

```
扩展点           需要改什么             工作量    频率
──────────────────────────────────────────────────────
加新采集目标     写一个 JSON 文件        2 分钟   每天
加新采集通道     实现一个接口 + 注册     1-3 天   每月
加新协议解析器   实现一个接口 + 注册     1-5 天   偶尔
加新输出方式     实现一个接口 + 注册     1-2 天   偶尔

核心引擎代码     ❌ 永远不改            —        —
```

---

## 附录：当前代码到目标架构的差距分析

```
模块                当前状态               目标                工作量
────────────────────────────────────────────────────────────────────
WinDivvertDriver     SNIFF 模式            可切换 SNIFF/DIVERT   1天
DnsSpoofer           独立文件，未集成       作为 Channel 接入      <1天
TlsProxy             MITM 白名单不全        完整 MITM 路由        1天
ICaptureChannel      不存在                从 WinDivertDriver    <1天
                                          提取接口
ChannelManager       不存在                新增                 2天
ProtocolRegistry     不存在                从 HttpParser 提取    1天
Target Registry      用 PayDomains 数组    完整匹配树            2天
规则引擎             qq_midas.json         热加载 + 多规则       1天
Dashboard            无                    HTML + JS 单页        2-3天
托盘图标             无                    小型 C# 程序          2天
安装程序             散落 ps1 脚本          集成 Inno Setup       2天
Windows Service      Console 应用          改造为 Service        1天
WFP Callout          不存在                QUIC 阻断驱动         5天
```
