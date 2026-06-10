using Oracle.Http;
using Oracle.Shared;

namespace Oracle.Extractor;

/// <summary>
/// Extracts payment credentials from intercepted HTTP traffic.
/// Matches known Tencent payment endpoints and extracts weixin:// URLs.
/// </summary>
public class CredentialExtractor
{
    private readonly HttpParser _parser;
    private readonly string[] _payEndpoints =
    {
        "/web_save",
        "/CommonCallMpgo",
        "/wechat_query",
        "/create_order",
    };

    public CredentialExtractor(HttpParser parser)
    {
        _parser = parser;
    }

    /// <summary>
    /// Try to extract a payment credential from an intercepted response.
    /// </summary>
    public Credential? Extract(HttpRequest? request, byte[] responseData)
    {
        if (request == null) return null;

        // Only interested in payment endpoints
        if (!_payEndpoints.Any(e => request.Url.Contains(e)))
            return null;

        var response = _parser.ParseResponse(responseData);
        if (response == null || response.StatusCode != 200)
            return null;

        var body = response.BodyString;

        // Extract weixin:// payment URL
        var payUrl = _parser.ExtractPayUrl(body);
        if (string.IsNullOrEmpty(payUrl))
            return null;

        // Extract openid from request body
        var openid = _parser.ExtractOpenId(request.BodyString);

        // Extract product_id
        var productId = _parser.ExtractProductId(request.Url, request.BodyString);

        // Detect platform
        var platform = DetectPlatform(request.Url);

        // Detect pay method
        var payMethod = ExtractPayMethod(request.BodyString);

        return new Credential
        {
            Type = CredentialType.PaymentUrl,
            Value = payUrl,
            Platform = platform,
            ProductId = productId,
            Source = "oracle",
            OpenId = openid,
            PayMethod = payMethod,
            Metadata = new Dictionary<string, string>
            {
                ["api_url"] = request.Url,
                ["method"] = request.Method,
                ["pay_method"] = payMethod,
                ["request_body"] = request.BodyString.Length > 3000
                    ? request.BodyString[..3000]
                    : request.BodyString,
            },
        };
    }

    private static string DetectPlatform(string url)
    {
        if (url.Contains("unipay.qq.com")) return "QQ Midas";
        if (url.Contains("tenpay.com")) return "WeChat Pay";
        if (url.Contains("pay.qq.com")) return "QQ Midas";
        return "Unknown";
    }

    private static string ExtractPayMethod(string body)
    {
        var match = System.Text.RegularExpressions.Regex.Match(body, @"pay_method=(\w+)");
        return match.Success ? match.Groups[1].Value : "unknown";
    }
}
