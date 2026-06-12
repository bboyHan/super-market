namespace Oracle.Shared;

/// <summary>
/// Oracle 万能数据采集引擎 — 全局配置。
/// 所有配置项均有默认值，可通过 config.json 或环境变量覆盖。
/// </summary>
public class OracleConfig
{
    // ── WinDivert ─────────────────────────────────────
    public int WinDivertQueueLen { get; set; } = 8192;
    public int MaxConnections { get; set; } = 50000;
    public int ConnectionTimeoutSec { get; set; } = 60;
    public int ConnectionCleanupIntervalSec { get; set; } = 10;
    public int PacketQueueSize { get; set; } = 10000;

    // ── TLS Proxy ─────────────────────────────────────
    public int TlsProxyPort { get; set; } = 18802;
    public int CertCacheSize { get; set; } = 1024;
    public int CertValidHours { get; set; } = 1;
    public string CaSubject { get; set; } = "CN=Oracle Data Collector CA, O=Oracle, C=CN";
    public int TlsHandshakeTimeoutMs { get; set; } = 5000;
    public int TlsRelayBufferSize { get; set; } = 65536;

    // ── Management API ────────────────────────────────
    public int ApiPort { get; set; } = 18801;
    public string ApiBindAddress { get; set; } = "127.0.0.1";

    // ── Backend Output ────────────────────────────────
    // 采集到的结构化数据输出目标。可为空（仅本地存储）。
    public string? BackendUrl { get; set; } = null;
    public string IngestEndpoint { get; set; } = "/api/capture/ingest";
    public int BatchSize { get; set; } = 10;
    public int BatchIntervalMs { get; set; } = 1000;
    public int HttpTimeoutSec { get; set; } = 5;

    // ── Target Domains ────────────────────────────────
    // 用户感兴趣的目标域名白名单。
    // 引擎只会深度处理命中此列表的流量（TLS 解密、正文提取）。
    // 空列表 = 处理所有流量（性能较低）。
    // 设置方式：启动后通过 API 动态配置，或启动时加载 config.json。
    public string[] TargetDomains { get; set; } = Array.Empty<string>();

    // ── DNS Spoof Domains ─────────────────────────────
    // DNS 劫持的目标域名列表。命中此列表的 DNS 响应会被篡改为 127.0.0.1。
    // 空列表 = 不进行 DNS 劫持。
    // 通常与 TargetDomains 配合使用：劫持域名 → 重定向到 TlsProxy → 解密 → 提取。
    public string[] SpoofDomains { get; set; } = Array.Empty<string>();

    // ── SNI Keywords ──────────────────────────────────
    // SNI 关键词匹配列表。WinDivert 通道使用此列表判断是否将连接交给 TlsProxy。
    // 匹配方式：SNI 包含列表中的任一关键词即命中。
    // 空列表 = 所有 HTTPS 流量都经过 TlsProxy。
    public string[] SniKeywords { get; set; } = Array.Empty<string>();

    // ── Storage ───────────────────────────────────────
    public string AppDataPath { get; set; } = "";
    public string CaCertFileName { get; set; } = "oracle_ca.p12";
    public string ConfigFileName { get; set; } = "oracle_config.json";

    public string GetCaCertPath()
    {
        var basePath = AppDataPath;
        if (string.IsNullOrEmpty(basePath))
        {
            basePath = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Oracle");
        }
        Directory.CreateDirectory(basePath);
        return Path.Combine(basePath, CaCertFileName);
    }

    public string GetConfigPath()
    {
        var basePath = AppDataPath;
        if (string.IsNullOrEmpty(basePath))
        {
            basePath = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Oracle");
        }
        Directory.CreateDirectory(basePath);
        return Path.Combine(basePath, ConfigFileName);
    }
}
