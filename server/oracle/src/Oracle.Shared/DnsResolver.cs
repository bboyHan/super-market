using System.Net;
using System.Net.Sockets;

namespace Oracle.Shared;

/// <summary>
/// DNS 解析器 — 直接查询上游 DNS 服务器，绕过系统 hosts 文件。
/// 用于 TlsProxy 透传转发时获取真实服务器 IP。
/// </summary>
public static class DnsResolver
{
    private static IPAddress _dnsServer = IPAddress.Parse("8.8.8.8");
    private static int _timeoutMs = 3000;

    /// <summary>设置 DNS 服务器地址（默认 8.8.8.8）</summary>
    public static void SetDnsServer(string ip)
    {
        if (IPAddress.TryParse(ip, out var addr))
            _dnsServer = addr;
    }

    /// <summary>直接查询 DNS A 记录，不走系统 hosts</summary>
    public static async Task<IPAddress?> ResolveAsync(string hostname)
    {
        try
        {
            // 先尝试系统解析（不走 hosts 的纯 DNS 查询）
            // 在 Windows 上 GetHostEntry 会走 hosts，所以我们用原始 UDP DNS 查询

            // Build DNS query packet
            var query = BuildDnsQuery(hostname);
            using var udp = new UdpClient();
            udp.Client.ReceiveTimeout = _timeoutMs;
            udp.Client.SendTimeout = _timeoutMs;

            await udp.SendAsync(query, query.Length, _dnsServer.ToString(), 53);

            var result = await udp.ReceiveAsync();
            var ip = ParseDnsResponse(result.Buffer);
            return ip;
        }
        catch
        {
            // Fallback: try system DNS (may hit hosts, but better than nothing)
            try
            {
                var entries = await Dns.GetHostAddressesAsync(hostname);
                return entries.FirstOrDefault(a => a.AddressFamily == AddressFamily.InterNetwork);
            }
            catch
            {
                return null;
            }
        }
    }

    /// <summary>解析主机名并连接到指定端口</summary>
    public static async Task<Socket> ConnectAsync(string hostname, int port, CancellationToken ct = default)
    {
        // Try direct DNS query first
        var ip = await ResolveAsync(hostname);

        // If that returns localhost (hosts file), force public DNS
        if (ip == null || IPAddress.IsLoopback(ip))
        {
            // Force resolve via Google DNS
            ip = await ForceResolveAsync(hostname);
        }

        if (ip == null)
            throw new SocketException((int)SocketError.HostNotFound);

        var socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
        await socket.ConnectAsync(new IPEndPoint(ip, port), ct);
        return socket;
    }

    /// <summary>强制通过指定 DNS 解析（绕过 hosts）</summary>
    private static async Task<IPAddress?> ForceResolveAsync(string hostname)
    {
        var query = BuildDnsQuery(hostname);
        using var udp = new UdpClient();

        // Try Google DNS
        foreach (var dns in new[] { "8.8.8.8", "1.1.1.1", "114.114.114.114" })
        {
            try
            {
                udp.Client.ReceiveTimeout = 2000;
                udp.Client.SendTimeout = 2000;
                await udp.SendAsync(query, query.Length, dns, 53);
                var result = await udp.ReceiveAsync();
                var ip = ParseDnsResponse(result.Buffer);
                if (ip != null) return ip;
            }
            catch { continue; }
        }
        return null;
    }

    private static byte[] BuildDnsQuery(string hostname)
    {
        var id = (ushort)new Random().Next();
        var bytes = new List<byte>();

        // DNS header
        bytes.Add((byte)(id >> 8)); bytes.Add((byte)id);     // ID
        bytes.Add(0x01); bytes.Add(0x00);                     // Flags: recursion desired
        bytes.Add(0x00); bytes.Add(0x01);                     // QDCOUNT: 1 question
        bytes.Add(0x00); bytes.Add(0x00);                     // ANCOUNT: 0
        bytes.Add(0x00); bytes.Add(0x00);                     // NSCOUNT: 0
        bytes.Add(0x00); bytes.Add(0x00);                     // ARCOUNT: 0

        // Question: hostname encoded as labels
        foreach (var label in hostname.Split('.'))
        {
            bytes.Add((byte)label.Length);
            bytes.AddRange(System.Text.Encoding.ASCII.GetBytes(label));
        }
        bytes.Add(0x00);                                      // Terminator

        bytes.Add(0x00); bytes.Add(0x01);                     // QTYPE: A record
        bytes.Add(0x00); bytes.Add(0x01);                     // QCLASS: IN

        return bytes.ToArray();
    }

    private static IPAddress? ParseDnsResponse(byte[] response)
    {
        if (response.Length < 12) return null;

        // Skip header (12 bytes) + question section
        var pos = 12;
        while (pos < response.Length && response[pos] != 0)
        {
            pos += response[pos] + 1;
            if (pos >= response.Length) return null;
        }
        pos += 5; // Skip null terminator + QTYPE + QCLASS

        // Parse answer records
        while (pos + 12 < response.Length)
        {
            // Name pointer or label
            if ((response[pos] & 0xC0) == 0xC0)
                pos += 2;
            else
            {
                while (pos < response.Length && response[pos] != 0) pos++;
                pos++;
            }
            if (pos + 10 > response.Length) return null;

            var type = (response[pos] << 8) | response[pos + 1];
            var rdlength = (response[pos + 8] << 8) | response[pos + 9];
            pos += 10;

            if (type == 1 && rdlength == 4 && pos + 4 <= response.Length) // A record
            {
                return new IPAddress(new[] { response[pos], response[pos + 1], response[pos + 2], response[pos + 3] });
            }
            pos += rdlength;
        }

        return null;
    }
}
