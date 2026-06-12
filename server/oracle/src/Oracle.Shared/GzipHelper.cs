using System.IO.Compression;
using System.Text;

namespace Oracle.Shared;

/// <summary>
/// HTTP 响应体解压工具：
///   1. 如果 Transfer-Encoding: chunked → 先解码 chunked 分块
///   2. 如果 Content-Encoding: gzip → 再解压 gzip
/// </summary>
public static class GzipHelper
{
    /// <summary>
    /// 对 HTTP 原始响应（含头部）进行传输层解码：
    ///   - chunked 分块 → 合并为完整 body
    ///   - gzip 压缩 → 解压
    /// 返回还原后的完整 HTTP 消息（头部不变，body 替换）。
    /// </summary>
    public static string DecompressBody(string raw)
    {
        if (raw == null) return raw;

        var isChunked = raw.IndexOf("Transfer-Encoding: chunked", StringComparison.OrdinalIgnoreCase) >= 0;
        var isGzip = raw.IndexOf("Content-Encoding: gzip", StringComparison.OrdinalIgnoreCase) >= 0;

        if (!isChunked && !isGzip)
            return raw;

        // Find the header/body separator
        var sep = raw.IndexOf("\r\n\r\n");
        if (sep < 0) return raw;

        var headers = raw[..(sep + 4)];
        var bodyStr = raw[(sep + 4)..];

        // Step 1: Decode chunked transfer encoding
        if (isChunked)
            bodyStr = DecodeChunked(bodyStr);

        // Step 2: Decompress gzip
        if (isGzip)
            bodyStr = DecompressGzip(bodyStr);

        return headers + bodyStr;
    }

    /// <summary>
    /// 解码 HTTP chunked 传输编码。
    /// 格式：chunk-size\r\nchunk-data\r\n ... 0\r\n\r\n
    /// </summary>
    private static string DecodeChunked(string body)
    {
        if (string.IsNullOrEmpty(body)) return body;

        var result = new StringBuilder(body.Length);
        var pos = 0;

        while (pos < body.Length)
        {
            // Read chunk size line (hex) — ends with \r\n
            var crlf = body.IndexOf("\r\n", pos, StringComparison.Ordinal);
            if (crlf < 0) break;

            var sizeStr = body[pos..crlf].Trim();
            if (sizeStr == "") break;

            // Chunk size may have chunk extensions after ';'
            var semiIdx = sizeStr.IndexOf(';');
            if (semiIdx >= 0) sizeStr = sizeStr[..semiIdx];

            if (!int.TryParse(sizeStr,
                System.Globalization.NumberStyles.HexNumber,
                System.Globalization.CultureInfo.InvariantCulture,
                out var chunkSize))
                break;

            if (chunkSize == 0)
                break; // Last chunk

            // Move past the \r\n after chunk size
            var chunkStart = crlf + 2;
            if (chunkStart + chunkSize > body.Length)
                break; // Truncated

            result.Append(body, chunkStart, chunkSize);

            // Move to next chunk (skip the trailing \r\n after chunk data)
            pos = chunkStart + chunkSize;
            if (pos + 1 < body.Length && body[pos] == '\r' && body[pos + 1] == '\n')
                pos += 2;
        }

        var decoded = result.ToString();
        return decoded.Length > 0 ? decoded : body;
    }

    /// <summary>
    /// 解压 gzip 压缩的数据。
    /// </summary>
    private static string DecompressGzip(string body)
    {
        if (string.IsNullOrEmpty(body)) return body;

        var rawBytes = Encoding.UTF8.GetBytes(body);

        // Check gzip magic bytes: 0x1F 0x8B
        if (rawBytes.Length < 2 || rawBytes[0] != 0x1F || rawBytes[1] != 0x8B)
            return body;

        try
        {
            using var compressed = new MemoryStream(rawBytes);
            using var gzip = new GZipStream(compressed, CompressionMode.Decompress);
            using var output = new MemoryStream();
            gzip.CopyTo(output);
            return Encoding.UTF8.GetString(output.ToArray());
        }
        catch
        {
            return body; // Decompress failed, return original
        }
    }
}
