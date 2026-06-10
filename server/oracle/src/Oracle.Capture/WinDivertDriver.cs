using System.Net;
using System.Runtime.InteropServices;

namespace Oracle.Capture;

/// <summary>
/// WinDivert kernel driver wrapper via P/Invoke.
///
/// ALL packets received by the driver MUST be re-injected via WinDivertSend,
/// otherwise they are silently dropped by the kernel driver, causing network outage.
/// </summary>
public class WinDivertDriver : ICaptureDriver
{
    private const string DllName = "WinDivert.dll";
    private nint _handle;
    private bool _disposed;
    private byte[] _packetBuffer = new byte[65535];
    private WinDivertAddress _addr;

    // Event fires for each packet; handler returns true to consume (redirect),
    // false to re-inject unchanged
    public long DirectPacketCount { get; private set; }
    public event Action<CapturedPacket>? OnPacketCaptured;

    // ── P/Invoke ─────────────────────────────────────

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
    public long Timestamp;   // 0-7: 8字节
    public uint LayerEvent;  // 8-11: Layer(8bit) + Event(8bit) + Sniff(1bit) + Reserved(15bit)
    public uint IfIdx;       // 12-15
    public uint SubIfIdx;    // 16-19
    public uint DstAddr;     // 20-23
    public uint SrcAddr;     // 24-27
    public ushort DstPort;   // 28-29
    public ushort SrcPort;   // 30-31
    // 共 32 字节，和 WinDivert v2.2.2 完全对齐
    }


    public void Open(int queueLen = 8192)
    {
        // CRITICAL: WinDivert in DIVERT mode (not SNIFF) consumes packets.
        // Every packet received MUST be re-injected via WinDivertSend.
        // The filter is broad (all HTTPS), but we selectively redirect only payment traffic.
        var filter = "outbound and tcp.DstPort == 443";
        var flags = 0x0001; /* WINDIVERT_FLAG_SNIFF */

        _handle = WinDivertOpen(filter, WINDIVERT_LAYER_NETWORK, 0, flags);

        if (_handle == nint.Zero || _handle == (nint)(-1))
        {
            var error = Marshal.GetLastWin32Error();
            throw new InvalidOperationException(
                $"WinDivert open failed (error {error}). Requires Administrator privileges.");
        }

        WinDivertSetParam(_handle, WINDIVERT_PARAM_QUEUE_LEN, queueLen);

        var t = new Thread(CaptureThread) { Name = "WinDivert", IsBackground = true };
        t.Start();
    }

    public void Close()
    {
        if (_handle != nint.Zero && _handle != (nint)(-1))
        {
            WinDivertClose(_handle);
            _handle = nint.Zero;
        }
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

                var data = new byte[recvLen];
                Array.Copy(_packetBuffer, data, recvLen);

                var sni = TlsHelper.ExtractSni(data.AsSpan());

                // Fire event for ALL captured packets (CaptureService handles filtering)
                var packet = new CapturedPacket
                {
                    RawData = data,
                    SrcAddr = new IPAddress(_addr.SrcAddr),
                    DstAddr = new IPAddress(_addr.DstAddr),
                    SrcPort = _addr.SrcPort,
                    DstPort = _addr.DstPort,
                };

                DirectPacketCount++;
                OnPacketCaptured?.Invoke(packet);

                // SNIFF mode still requires sending the packet to release the driver queue
                WinDivertSend(_handle, _packetBuffer, recvLen, out _, ref _addr);
            }
        }
        catch (Exception ex)
        {
            if (!_disposed)
                Console.Error.WriteLine($"[WinDivert] Error: {ex.Message}");
        }
    }

    private static readonly string[] PayDomains = {
        "api.unipay.qq.com", "pay.qq.com", "pagedoo.pay.qq.com",
        "storeapi.pay.qq.com", "wx.tenpay.com", "tenpay.com",
        "api.mch.weixin.qq.com", "pay.weixin.qq.com", "qpay.qq.com",
    };

    private static bool IsPayDomain(ReadOnlySpan<char> sni)
    {
        foreach (var d in PayDomains)
            if (sni.SequenceEqual(d.AsSpan()) ||
                (sni.Length > d.Length && sni[sni.Length - d.Length - 1] == '.' &&
                 sni.Slice(sni.Length - d.Length).SequenceEqual(d.AsSpan())))
                return true;
        return false;
    }

    public void Dispose()
    {
        _disposed = true;
        Close();
    }
}
