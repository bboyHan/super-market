namespace Oracle.Shared;

public class OracleConfig
{
    // WinDivert
    public int WinDivertQueueLen { get; set; } = 8192;
    public int MaxConnections { get; set; } = 50000;
    public int ConnectionTimeoutSec { get; set; } = 60;
    public int ConnectionCleanupIntervalSec { get; set; } = 10;
    public int PacketQueueSize { get; set; } = 10000;

    // TLS Proxy
    public int TlsProxyPort { get; set; } = 18802;
    public int CertCacheSize { get; set; } = 1024;
    public int CertValidHours { get; set; } = 1;
    public string CaSubject { get; set; } = "CN=Oracle Payment Collector CA, O=Oracle, C=CN";
    public int TlsHandshakeTimeoutMs { get; set; } = 5000;
    public int TlsRelayBufferSize { get; set; } = 65536;

    // Management API
    public int ApiPort { get; set; } = 18801;
    public string ApiBindAddress { get; set; } = "127.0.0.1";

    // Python Backend
    public string BackendUrl { get; set; } = "http://127.0.0.1:8800";
    public string IngestEndpoint { get; set; } = "/api/capture/ingest";
    public int BatchSize { get; set; } = 10;
    public int BatchIntervalMs { get; set; } = 1000;
    public int HttpTimeoutSec { get; set; } = 5;

    // Payment Domains (SNI filtering)
    public string[] PayDomains { get; set; } =
    {
        "api.unipay.qq.com",
        "pay.qq.com",
        "pagedoo.pay.qq.com",
        "storeapi.pay.qq.com",
        "wx.tenpay.com",
        "myun.tenpay.com",
        "jspay.qq.com",
        "tenpay.com",
        "api.mch.weixin.qq.com",
        "pay.weixin.qq.com",
        "qpay.qq.com",
    };

    // Storage
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
