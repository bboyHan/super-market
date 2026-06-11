namespace Oracle.Shared;

/// <summary>
/// 通道能力声明 — 描述一个采集通道能做什么。
/// 路由引擎根据此信息为 Target 匹配最优 Channel。
/// </summary>
public class ChannelCapability
{
    /// <summary>是否需要管理员权限</summary>
    public bool RequiresAdmin { get; set; }

    /// <summary>能否解密 TLS</summary>
    public bool CanDecryptTls { get; set; }

    /// <summary>支持的协议列表</summary>
    public string[] SupportedProtocols { get; set; } = Array.Empty<string>();

    /// <summary>是否需要安装 CA 证书</summary>
    public bool RequiresCertInstall { get; set; }

    /// <summary>覆盖范围描述</summary>
    public string ScopeDescription { get; set; } = "";
}

/// <summary>
/// 原始数据包 — Channel 产出的统一格式。
/// 后续由协议层(Protocol Parser)解析为 NormalizedTransaction。
/// </summary>
public class RawPacket
{
    public byte[] Data { get; set; } = Array.Empty<byte>();
    public string SourceChannel { get; set; } = "";
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;
    public PacketMetadata Metadata { get; set; } = new();
}

public class PacketMetadata
{
    public string? Sni { get; set; }
    public int SourcePort { get; set; }
    public int DestPort { get; set; }
    public string? SourceAddress { get; set; }
    public string? DestAddress { get; set; }
    public int ProcessId { get; set; }
    public string? ProcessName { get; set; }
    public string? Protocol { get; set; }
}

/// <summary>
/// 采集通道接口 — 每种数据采集方式实现一个 Channel。
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
    event Action<RawPacket>? OnPacket;
}
