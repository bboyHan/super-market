namespace Oracle.Shared;

public enum CredentialType
{
    PaymentUrl,      // weixin://wxpay/bizpayurl?pr=XXX
    PaymentParams,   // WeChatJSBridge parameters
    AccessToken,     // pay_openid + pay_openkey
    QrImage,        // QR code image (base64)
    CardKey,        // card key credential
    RawData,        // unrecognized raw data
}

public class Credential
{
    public string Id { get; set; } = $"cred_{Guid.NewGuid():N}";
    public CredentialType Type { get; set; } = CredentialType.RawData;
    public string Value { get; set; } = "";
    public string Platform { get; set; } = "";
    public string ProductId { get; set; } = "";
    public string Source { get; set; } = "oracle";
    public string AccountName { get; set; } = "";
    public string OpenId { get; set; } = "";
    public string PayMethod { get; set; } = "";
    public Dictionary<string, string> Metadata { get; set; } = new();

    public object ToIngestPayload() => new
    {
        type = Type switch
        {
            CredentialType.PaymentUrl => "payment_url",
            CredentialType.PaymentParams => "payment_params",
            CredentialType.AccessToken => "access_token",
            CredentialType.QrImage => "qr_image",
            CredentialType.CardKey => "card_key",
            _ => "raw_data"
        },
        value = Value,
        platform = Platform,
        product_id = ProductId,
        source = Source,
        openid = OpenId,
        pay_method = PayMethod,
        body = Metadata.GetValueOrDefault("request_body", ""),
    };
}
