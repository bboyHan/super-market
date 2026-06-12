using System.IO.Compression;
using System.Text;

namespace Oracle.Shared;

public static class GzipHelper
{
    public static string DecompressBody(string raw)
    {
        if (raw == null) return raw;

        // Check for gzip content encoding
        if (raw.IndexOf("Content-Encoding: gzip", StringComparison.OrdinalIgnoreCase) < 0)
            return raw;

        // Find the header/body separator
        var sep = raw.IndexOf("\r\n\r\n");
        if (sep < 0) return raw;

        // Get body bytes
        var bodyStr = raw[(sep + 4)..];
        var gzBytes = Encoding.UTF8.GetBytes(bodyStr);

        // Check gzip magic bytes
        if (gzBytes.Length < 2 || gzBytes[0] != 0x1F || gzBytes[1] != 0x8B)
            return raw;

        try
        {
            using var compressed = new MemoryStream(gzBytes);
            using var gzip = new GZipStream(compressed, CompressionMode.Decompress);
            using var output = new MemoryStream();
            gzip.CopyTo(output);
            var decoded = Encoding.UTF8.GetString(output.ToArray());
            return raw[..(sep + 4)] + decoded;
        }
        catch
        {
            return raw; // Decompress failed, return original
        }
    }
}
