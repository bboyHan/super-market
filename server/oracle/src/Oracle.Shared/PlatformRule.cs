using System.Text.RegularExpressions;

namespace Oracle.Shared;

/// <summary>
/// 平台规则 — 纯数据，定义如何匹配和提取凭证。
/// 从 JSON 文件加载，可在运行时热更新。
/// 添加新平台 = 添加一个新 JSON 文件，无需修改代码。
/// </summary>
public class PlatformRule
{
    public string Name { get; set; } = "";             // "qq_midas"
    public string Description { get; set; } = "";      // "腾讯 Midas 支付"
    public bool Enabled { get; set; } = true;
    public int Priority { get; set; } = 100;           // 数值越小优先级越高

    public List<MatcherRule> Matchers { get; set; } = new();
    public List<ExtractorRule> Extractors { get; set; } = new();
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

    private Regex? _compiled;

    /// <summary>
    /// 从 NormalizedTransaction 中提取值
    /// </summary>
    public string? Extract(NormalizedTransaction tx)
    {
        var source = Source.ToLower() switch
        {
            "request_body" => tx.RequestBody,
            "response_body" => tx.ResponseBody,
            "path" => tx.Path,
            "query" => tx.QueryString,
            "domain" => tx.Domain,
            "method" => tx.Method,
            "url" => tx.Url,
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
