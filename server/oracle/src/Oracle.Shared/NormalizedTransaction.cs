namespace Oracle.Shared;

/// <summary>
/// 标准化后的 HTTP 事务 — 不包含任何平台特定逻辑。
/// 这是 Oracle 核心引擎和平台规则层之间的唯一数据契约。
///
/// 任何平台规则（QQ Midas、支付宝、淘宝等）都基于此数据进行匹配和提取。
/// 添加新平台不需要修改此模型。
/// </summary>
public class NormalizedTransaction
{
    // ── 连接标识 ──
    public string ConnectionId { get; set; } = "";
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;

    // ── 网络层 ──
    public string Domain { get; set; } = "";         // api.unipay.qq.com
    public string RemoteIp { get; set; } = "";       // 服务器 IP
    public int RemotePort { get; set; }

    // ── 请求 ──
    public string Method { get; set; } = "";         // GET / POST
    public string Path { get; set; } = "";           // /v1/r/1450049871/web_save
    public string QueryString { get; set; } = "";    // ?t=123456
    public string RequestBody { get; set; } = "";
    public int BodyLength => RequestBody.Length;

    // ── 响应 ──
    public int StatusCode { get; set; }
    public string ResponseBody { get; set; } = "";

    /// <summary>
    /// 原始响应体（Base64 编码），用于二进制数据（二维码图片等）
    /// </summary>
    public string? ResponseBodyBase64 { get; set; }

    /// <summary>响应头（小写 key）</summary>
    public Dictionary<string, string> ResponseHeaders { get; set; } = new();
    /// <summary>请求头（小写 key）</summary>
    public Dictionary<string, string> RequestHeaders { get; set; } = new();

    // ── 快捷属性 ──
    public string Url => $"https://{Domain}{Path}";
    public string FullUrl => $"https://{Domain}{Path}{QueryString}";

    /// <summary>
    /// 简短的标识字符串（用于日志和调试）
    /// </summary>
    public string ShortId => $"{Method} {Domain}{Path}";
}
