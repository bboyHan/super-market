using System.Collections.Concurrent;

namespace Oracle.Shared;

/// <summary>
/// 流量缓冲区 — 保存最近解密后的 HTTP 请求/响应数据。
/// 供 Dashboard 的「流量查看器」功能使用。
/// 默认保留最近 100 条，每条最多 10KB。
/// </summary>
public class TrafficBuffer
{
    private readonly ConcurrentQueue<CapturedTraffic> _items = new();
    private readonly int _maxItems;
    private readonly int _maxBodySize;

    public TrafficBuffer(int maxItems = 500, int maxBodySize = 50_240)
    {
        _maxItems = maxItems;
        _maxBodySize = maxBodySize;
    }

    /// <summary>记录一条解密后的流量</summary>
    public void Record(string domain, string method, string path, string requestBody,
        int statusCode, Dictionary<string, string> responseHeaders, string responseBody,
        bool isPaymentDomain = true)
    {
        var item = new CapturedTraffic
        {
            Timestamp = DateTime.UtcNow,
            Domain = domain,
            Method = method,
            Path = path,
            StatusCode = statusCode,

            RequestHeaders = responseHeaders?.GetValueOrDefault("request-headers", "") ?? "",
            RequestBody = Truncate(requestBody, _maxBodySize),

            ResponseHeaders = responseHeaders?.Aggregate("", (s, kv) => s + $"{kv.Key}: {kv.Value}\n") ?? "",
            IsPaymentDomain = isPaymentDomain,
            ResponseBody = Truncate(responseBody, _maxBodySize),
        };

        _items.Enqueue(item);
        while (_items.Count > _maxItems)
            _items.TryDequeue(out _);
    }

    /// <summary>获取所有记录</summary>
    public List<CapturedTraffic> GetAll() => _items.Reverse().ToList();

    private static string Truncate(string s, int max) =>
        s.Length <= max ? s : s[..max] + $"\n... (truncated, {s.Length} bytes total)";
}

/// <summary>
/// 一条捕获的 HTTP 流量记录
/// </summary>
public class CapturedTraffic
{
    public DateTime Timestamp { get; set; }
    public string Domain { get; set; } = "";
    public string Method { get; set; } = "";
    public string Path { get; set; } = "";
    public int StatusCode { get; set; }
    public string RequestHeaders { get; set; } = "";
    public string RequestBody { get; set; } = "";
    public string ResponseHeaders { get; set; } = "";
    public string ResponseBody { get; set; } = "";
    public bool IsPaymentDomain { get; set; } = true;
    public string ShortLabel => $"{Method} {Domain}{Path}";
    public string TimestampStr => Timestamp.ToLocalTime().ToString("HH:mm:ss");
}
