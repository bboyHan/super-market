using System.Text.RegularExpressions;

namespace Oracle.Shared;

/// <summary>
/// 应用目标 — 描述要捕获数据的应用
/// 支持多种介质类型：browser（浏览器网页）、desktop（PC应用）、emulator（模拟器手游）
/// </summary>
public class AppTarget
{
    /// <summary>介质类型：browser | desktop | emulator | hotspot</summary>
    public string Type { get; set; } = "browser";

    /// <summary>进程名列表（桌面应用），如 ["QQ.exe", "WeChat.exe"]</summary>
    public List<string> Processes { get; set; } = new();

    /// <summary>包名（模拟器/手机），如 ["com.tencent.tmgp.sgame"]</summary>
    public List<string> Packages { get; set; } = new();

    /// <summary>关联域名列表</summary>
    public List<string> Domains { get; set; } = new();
}

/// <summary>
/// 快捷字段定义 — 用户通过"示例值"快速定义要采集的字段
/// 引擎自动推断 source 和 pattern
/// </summary>
public class FieldDefinition
{
    /// <summary>字段名（用户可读），如 "支付链接"</summary>
    public string Name { get; set; } = "";

    /// <summary>数据来源：response_body | request_body | header | query</summary>
    public string Source { get; set; } = "response_body";

    /// <summary>示例值（用户提供，用于自动推断 pattern）</summary>
    public string Example { get; set; } = "";

    /// <summary>提取正则（用户可手动指定，或留空让引擎根据 example 自动生成）</summary>
    public string Pattern { get; set; } = "auto";

    /// <summary>映射到 Credential 的字段</summary>
    public string OutputField { get; set; } = "value";

    /// <summary>
    /// 捕获模式：auto（默认，正则提取）| full_body（捕获整个响应体存为 Base64）
    /// </summary>
    public string CaptureMode { get; set; } = "auto";
}

/// <summary>
/// 平台规则 — 纯数据，定义如何匹配和提取凭证。
/// 从 JSON 文件加载，可在运行时热更新。
/// 支持新旧两种格式：
///   旧格式: Matchers + Extractors（精准控制）
///   新格式: AppTarget + Fields（快捷采集，自动推断）
/// </summary>
public class PlatformRule
{
    public string Name { get; set; } = "";             // "qq_midas"
    public string Description { get; set; } = "";      // "腾讯 Midas 支付"
    public bool Enabled { get; set; } = true;
    public int Priority { get; set; } = 100;           // 数值越小优先级越高
    public string? Id { get; set; }                    // 唯一标识（文件名字）

    // ── 新格式字段 ──

    /// <summary>应用目标（介质类型 + 进程 + 域名）</summary>
    public AppTarget? App { get; set; }

    /// <summary>建议使用的采集通道</summary>
    public List<string>? Channels { get; set; }

    /// <summary>快捷字段定义（用户通过示例值定义）</summary>
    public List<FieldDefinition>? Fields { get; set; }

    // ── 旧格式字段（向后兼容） ──

    public List<MatcherRule> Matchers { get; set; } = new();
    public List<ExtractorRule> Extractors { get; set; } = new();

    // ── 运行时统计 ──

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime? LastMatchedAt { get; set; }
    public long TotalCaptured { get; set; }

    /// <summary>
    /// 将快捷字段定义编译为标准 ExtractorRule 列表
    /// </summary>
    public List<ExtractorRule> CompileFields()
    {
        if (Fields == null || Fields.Count == 0)
            return Extractors;

        return Fields.Select(f =>
        {
            // full_body mode: capture entire response as base64
            if (f.CaptureMode == "full_body")
                return new ExtractorRule { Name = f.Name, Source = "response_body_raw",
                    OutputField = f.OutputField, CredentialType = "qr_image", Pattern = "" };

            return new ExtractorRule { Name = f.Name, Source = f.Source,
                OutputField = f.OutputField, Pattern = InferPattern(f) };
        }).ToList();
    }

    private static string InferPattern(FieldDefinition field)
    {
        if (!string.IsNullOrEmpty(field.Pattern) && field.Pattern != "auto")
            return field.Pattern;

        // 如果来源是响应体/请求体，用字段名匹配 JSON key
        // 字段名 "result_url" → "result_url"\s*:\s*"([^"]+)
        if (field.Source == "response_body" || field.Source == "request_body")
        {
            var key = Regex.Escape(field.Name);
            return $"\"{key}\"\\s*:\\s*\"([^\"]+)";
        }

        if (string.IsNullOrEmpty(field.Example)) return ".*";

        var ex = field.Example;

        if (ex.StartsWith("weixin://")) return "weixin://[^\\s\"'<>)}]+";
        if (ex.StartsWith("http://") || ex.StartsWith("https://")) return "https?://[^\\s\"'<>)}]+";
        if (Regex.IsMatch(ex, @"^[A-Z0-9]{16,}$")) return "([A-Z0-9]{16,})";
        if (Regex.IsMatch(ex, @"^\d+$")) return "(\\d+)";
        if (ex.Contains("=")) return Regex.Escape(ex);

        return Regex.Escape(ex);
    }
}

public class MatcherRule
{
    /// <summary>
    /// 匹配字段：domain | path | method | status | header.xxx
    /// </summary>
    public string Field { get; set; } = "";

    /// <summary>
    /// 匹配操作：equals | contains | regex | starts_with | not
    /// </summary>
    public string Operator { get; set; } = "contains";

    /// <summary>
    /// 匹配值
    /// </summary>
    public string Value { get; set; } = "";

    /// <summary>
    /// 对 NormalizedTransaction 执行匹配
    /// </summary>
    public bool IsMatch(NormalizedTransaction tx)
    {
        var target = Field.ToLower() switch
        {
            "domain" => tx.Domain,
            "path" => tx.Path,
            "method" => tx.Method,
            "status" => tx.StatusCode.ToString(),
            "query" => tx.QueryString,
            var h when h.StartsWith("header.") => LookupHeader(h, tx),
            _ => ""
        };

        return Operator.ToLower() switch
        {
            "equals" => target.Equals(Value, StringComparison.OrdinalIgnoreCase),
            "contains" => target.Contains(Value, StringComparison.OrdinalIgnoreCase),
            "starts_with" => target.StartsWith(Value, StringComparison.OrdinalIgnoreCase),
            "regex" => Regex.IsMatch(target, Value, RegexOptions.IgnoreCase),
            "not" => !target.Contains(Value, StringComparison.OrdinalIgnoreCase),
            _ => false
        };
    }

    private static string LookupHeader(string field, NormalizedTransaction tx)
    {
        var name = field["header.".Length..].Trim();
        if (tx.ResponseHeaders.TryGetValue(name, out var v)) return v;
        if (tx.RequestHeaders.TryGetValue(name, out var v2)) return v2;
        return "";
    }
}

public class ExtractorRule
{
    /// <summary>
    /// 提取名称（用于日志和调试）
    /// </summary>
    public string Name { get; set; } = "";

    /// <summary>
    /// 数据来源：request_body | response_body | path | header.xxx
    /// </summary>
    public string Source { get; set; } = "response_body";

    /// <summary>
    /// 提取完成后映射到 Credential 的哪个字段
    /// value | platform | openid | pay_method | product_id | account_name
    /// </summary>
    public string OutputField { get; set; } = "value";

    /// <summary>
    /// 凭证类型（仅当 output_field = value 时有效）
    /// payment_url | access_token | qr_image | card_key | raw_data
    /// </summary>
    public string CredentialType { get; set; } = "payment_url";

    /// <summary>
    /// 提取正则表达式
    /// </summary>
    public string Pattern { get; set; } = "";

    private static string LookupHeader(string field, NormalizedTransaction tx)
    {
        var name = field["header.".Length..].Trim();
        if (tx.ResponseHeaders.TryGetValue(name, out var v)) return v;
        if (tx.RequestHeaders.TryGetValue(name, out var v2)) return v2;
        return "";
    }

    private Regex? _compiled;

    /// <summary>
    /// 从 NormalizedTransaction 中提取值
    /// </summary>
    public string? Extract(NormalizedTransaction tx)
    {
        // response_body_raw 特殊处理：返回整个响应体的 Base64
        if (Source.ToLower() == "response_body_raw")
        {
            var b64 = tx.ResponseBodyBase64;
            if (string.IsNullOrEmpty(b64)) return null;
            return b64;
        }

        var source = Source.ToLower() switch
        {
            "request_body" => tx.RequestBody,
            "response_body" => tx.ResponseBody,
            "path" => tx.Path,
            "query" => tx.QueryString,
            "domain" => tx.Domain,
            "method" => tx.Method,
            "url" => tx.Url,
            var h when h.StartsWith("header.") => LookupHeader(h, tx),
            _ => ""
        };

        if (string.IsNullOrEmpty(source)) return null;

        _compiled ??= new Regex(Pattern, RegexOptions.Compiled | RegexOptions.Multiline);

        var match = _compiled.Match(source);
        return match.Success
            ? (match.Groups.Count > 1 ? match.Groups[1].Value : match.Value)
            : null;
    }
}
