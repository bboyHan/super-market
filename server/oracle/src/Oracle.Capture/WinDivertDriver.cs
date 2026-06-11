using System.Net;
using System.Runtime.InteropServices;

namespace Oracle.Capture;

/// <summary>
/// WinDivert kernel driver wrapper via P/Invoke.
///
/// DIVERT mode: intercepts packets at kernel level. Every packet received
/// MUST be re-injected via WinDivertSend or the connection drops silently.
///
/// Payment domain traffic → redirected to TLS proxy (127.0.0.1:18802)
/// All other traffic → recalculates checksums and re-injects unchanged
/// </summary>
public class WinDivertDriver : ICaptureDriver
{
    private const string DllName = "WinDivert.dll";
    private nint _handle;
    private bool _disposed;
    private byte[] _packetBuffer = new byte[65535];
    private WinDivertAddress _addr;
    private long _directPacketCount;

    public long DirectPacketCount => Interlocked.Read(ref _directPacketCount);
    public event Action<CapturedPacket>? OnPacketCaptured;

    [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
    private static extern nint WinDivertOpen(string filter, int layer, short priority, long flags);

    [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
    private static extern bool WinDivertClose(nint handle);

    [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
    private static extern bool WinDivertSetParam(nint handle, int param, long value);

    [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
    private static extern bool WinDivertRecv(nint handle, byte[] pPacket, int packetLen, out int recvLen, ref WinDivertAddress pAddr);

    [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
    private static extern bool WinDivertSend(nint handle, byte[] pPacket, int packetLen, out int sendLen, ref WinDivertAddress pAddr);

    [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
    private static extern ulong WinDivertHelperCalcChecksums(byte[] pPacket, int packetLen, ref WinDivertAddress pAddr, ulong flags);

    private const int WINDIVERT_PARAM_QUEUE_LEN = 0;
    private const int WINDIVERT_LAYER_NETWORK = 0;
    
    [StructLayout(LayoutKind.Sequential)]
    private struct WinDivertAddress
    {
        public long Timestamp;     // 0-7
        public uint LayerEvent;    // 8-11
        public uint IfIdx;         // 12-15
        public uint SubIfIdx;      // 16-19
        public uint DstAddr;       // 20-23
        public uint SrcAddr;       // 24-27
        public ushort DstPort;     // 28-29
        public ushort SrcPort;     // 30-31
    }

        // Resolved IP addresses of payment servers (for SYN packet matching)
    private static readonly HashSet<uint> PayIpSet = new()
    {
        // pay.qq.com
        BitConverter.ToUInt32(new byte[] { 117, 48, 151, 123 }),  // 123.151.48.117
        // api.unipay.qq.com
        BitConverter.ToUInt32(new byte[] { 170, 183, 81, 42 }),   // 42.81.183.170
        BitConverter.ToUInt32(new byte[] { 167, 183, 81, 42 }),   // 42.81.183.167
        // storeapi.pay.qq.com
        BitConverter.ToUInt32(new byte[] { 43, 76, 35, 101 }),    // 101.35.76.43
        BitConverter.ToUInt32(new byte[] { 187, 216, 69, 81 }),   // 81.69.216.187
        // pagedoo.pay.qq.com
        BitConverter.ToUInt32(new byte[] { 55, 240, 185, 27 }),   // 27.185.240.55
        BitConverter.ToUInt32(new byte[] { 186, 42, 138, 150 }),  // 150.138.42.186
        // pagedooapi.pay.qq.com
        BitConverter.ToUInt32(new byte[] { 89, 229, 151, 61 }),   // 61.151.229.89
        BitConverter.ToUInt32(new byte[] { 157, 65, 89, 101 }),   // 101.89.41.157
        // wx.tenpay.com
        BitConverter.ToUInt32(new byte[] { 128, 56, 13, 1 }),     // 1.13.56.128
        BitConverter.ToUInt32(new byte[] { 128, 131, 13, 1 }),    // 1.13.131.128
    };

private static readonly string[] PayDomains = {
        "api.unipay.qq.com", "pay.qq.com", "pagedoo.pay.qq.com",
        "pagedooapi.pay.qq.com", "storeapi.pay.qq.com",
        "wx.tenpay.com", "tenpay.com", "api.mch.weixin.qq.com",
        "pay.weixin.qq.com", "qpay.qq.com",
    };

    private static bool IsPayDomain(ReadOnlySpan<char> sni)
    {
        foreach (var d in PayDomains)
        {
            if (sni.Length < d.Length) continue;
            var match = sni.Length == d.Length
                ? sni.SequenceEqual(d.AsSpan())
                : sni[sni.Length - d.Length - 1] == '.' &&
                  sni.Slice(sni.Length - d.Length).SequenceEqual(d.AsSpan());
            if (match) return true;
        }
        return false;
    }

    public void Open(int queueLen = 8192)
    {
        // DIVERT mode (flags=0): packets removed from stack.
        // Every Recv -> Send pair is mandatory.
        // SNIFF mode: monitor HTTPS traffic without modification.
        var filter = "outbound and tcp.DstPort == 443 and tcp.PayloadLength > 0";
        _handle = WinDivertOpen(filter, WINDIVERT_LAYER_NETWORK, 0, 0x0001); /* SNIFF */

        if (_handle == nint.Zero || _handle == (nint)(-1))
        {
            var error = Marshal.GetLastWin32Error();
            throw new InvalidOperationException(
                $"WinDivert open failed (error {error}). Requires Administrator.");
        }
        WinDivertSetParam(_handle, WINDIVERT_PARAM_QUEUE_LEN, queueLen);
        var t = new Thread(CaptureThread) { Name = "WinDivert", IsBackground = true };
        t.Start();
    }

    public void Close()
    {
        if (_handle != nint.Zero && _handle != (nint)(-1))
            WinDivertClose(_handle);
        _handle = nint.Zero;
    }

    public bool Read(out CapturedPacket packet) { packet = null!; return false; }
    public void Send(CapturedPacket packet) { }

    private void CaptureThread()
    {
        try
        {
            while (!_disposed)
            {
                if (!WinDivertRecv(_handle, _packetBuffer, _packetBuffer.Length, out var recvLen, ref _addr))
                {
                    if (_disposed) break;
                    continue;
                }
                if (recvLen <= 0) continue;

                Interlocked.Increment(ref _directPacketCount);

                // Detect protocol: byte 9 of IP header = 6 (TCP) or 17 (UDP)
                var protocol = _packetBuffer[9];

                if (protocol == 17 && recvLen > 40)
                {
                    // UDP packet — check for DNS response and spoof
                    HandleDnsPacket(recvLen);
                }
                else if (protocol == 6)
                {
                    // TCP packet — extract SNI for monitoring
                    var sni = TlsHelper.ExtractSni(new ReadOnlySpan<byte>(_packetBuffer, 0, recvLen));
                    var packet = new CapturedPacket
                    {
                        RawData = _packetBuffer[..recvLen],
                        SrcAddr = new IPAddress(BitConverter.GetBytes(_addr.SrcAddr)),
                        DstAddr = new IPAddress(BitConverter.GetBytes(_addr.DstAddr)),
                        SrcPort = _addr.SrcPort,
                        DstPort = _addr.DstPort,
                    };
                    OnPacketCaptured?.Invoke(packet);
                }
            }
        }
        catch (Exception ex)
        {
            if (!_disposed)
                Console.Error.WriteLine($"[WinDivert] Error: {ex.Message}");
        }
    }

    // ── DNS 劫持 ──────────────────────────────────────

    private static readonly HashSet<string> DnsSpoofDomains = new(StringComparer.OrdinalIgnoreCase)
    {
        "pay.qq.com.", "api.unipay.qq.com.", "pagedoo.pay.qq.com.",
        "pagedooapi.pay.qq.com.", "storeapi.pay.qq.com.",
        "wx.tenpay.com.", "tenpay.com.", "qpay.qq.com.",
    };

    private long _dnsSpoofedCount;
    public long DnsSpoofedCount => Interlocked.Read(ref _dnsSpoofedCount);

    private void HandleDnsPacket(int recvLen)
    {
        // IP header length
        var ipHdrLen = (_packetBuffer[0] & 0x0F) * 4;
        if (ipHdrLen < 20 || ipHdrLen + 8 > recvLen) return;

        // DNS message starts after UDP header (8 bytes)
        var dnsOff = ipHdrLen + 8;
        var dnsLen = recvLen - dnsOff;
        if (dnsLen < 12) return;

        // Check DNS flags: must be a response (QR=1) with no error
        var flags = (_packetBuffer[dnsOff + 2] << 8) | _packetBuffer[dnsOff + 3];
        if ((flags & 0x8000) == 0) return;  // Not a response
        if ((flags & 0x000F) != 0) return;  // Error

        var qdCount = (_packetBuffer[dnsOff + 4] << 8) | _packetBuffer[dnsOff + 5];
        var anCount = (_packetBuffer[dnsOff + 6] << 8) | _packetBuffer[dnsOff + 7];
        if (qdCount == 0 || anCount == 0) return;

        // Parse questions, find and spoof matching A records in answers
        if (TrySpoofDnsAnswer(dnsOff, dnsLen))
        {
            Interlocked.Increment(ref _dnsSpoofedCount);
        }
    }

    private bool TrySpoofDnsAnswer(int dnsOff, int dnsLen)
    {
        var pos = dnsOff + 12;  // After DNS header
        var end = dnsOff + dnsLen;

        // Skip questions
        for (int i = 0; i < (_packetBuffer[dnsOff + 4] << 8 | _packetBuffer[dnsOff + 5]); i++)
        {
            pos = SkipDnsName(pos, end);
            if (pos < 0) return false;
            pos += 4;
        }

        // Try to spoof answers
        var modified = false;
        var anCount = (_packetBuffer[dnsOff + 6] << 8) | _packetBuffer[dnsOff + 7];

        for (int i = 0; i < anCount; i++)
        {
            var name = ReadDnsName(ref pos, end, dnsOff);
            if (name == null) return modified;

            if (pos + 10 > end) return modified;
            var type = (_packetBuffer[pos] << 8) | _packetBuffer[pos + 1];
            var rdLen = (_packetBuffer[pos + 8] << 8) | _packetBuffer[pos + 9];
            pos += 10;

            if (type == 1 && rdLen == 4 && DnsSpoofDomains.Contains(name))
            {
                // Spoof! Replace with 127.0.0.1
                _packetBuffer[pos] = 127;
                _packetBuffer[pos + 1] = 0;
                _packetBuffer[pos + 2] = 0;
                _packetBuffer[pos + 3] = 1;
                modified = true;
            }
            pos += rdLen;
        }

        return modified;
    }

    private string? ReadDnsName(ref int pos, int end, int dnsOff)
    {
        var labels = new List<string>();
        var jumped = false;
        var startPos = pos;

        while (pos < end)
        {
            var len = _packetBuffer[pos];
            if ((len & 0xC0) == 0xC0)
            {
                if (pos + 1 >= end) return null;
                var ptr = ((len & 0x3F) << 8) | _packetBuffer[pos + 1];
                if (!jumped) startPos = pos + 2;
                pos = dnsOff + ptr;
                jumped = true;
                continue;
            }
            if (len == 0) break;
            pos++;
            if (pos + len > end) return null;
            labels.Add(System.Text.Encoding.ASCII.GetString(_packetBuffer, pos, len));
            pos += len;
        }
        if (!jumped) pos++;

        return string.Join(".", labels) + ".";
    }

    private int SkipDnsName(int pos, int end)
    {
        while (pos < end)
        {
            var len = _packetBuffer[pos];
            if ((len & 0xC0) == 0xC0) return pos + 2;
            if (len == 0) return pos + 1;
            pos += 1 + len;
        }
        return -1;
    }

    public void Dispose()
    {
        _disposed = true;
        Close();
    }
}
