using System.Net;
using System.Runtime.InteropServices;

namespace Oracle.Capture;

/// <summary>
/// WinDivert kernel driver — DIVERT mode.
/// ALL outbound TCP/443 traffic → redirected to TLS proxy.
/// The proxy decides: payment → MITM, non-payment → transparent relay.
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
    private const uint FLAG_IMPOSTOR = 0x80000;  // Bit 19

    [StructLayout(LayoutKind.Sequential)]
    private struct WinDivertAddress
    {
        public long Timestamp;
        public uint LayerEvent;
        public uint IfIdx;
        public uint SubIfIdx;
        public uint DstAddr;
        public uint SrcAddr;
        public ushort DstPort;
        public ushort SrcPort;
    }

    public void Open(int queueLen = 8192)
    {
        // SNIFF mode: monitor only, no interception.
        var filter = "outbound and tcp.DstPort == 443 and tcp.PayloadLength > 0";
        _handle = WinDivertOpen(filter, WINDIVERT_LAYER_NETWORK, 0, 0x0001); /* SNIFF */

        if (_handle == nint.Zero || _handle == (nint)(-1))
        {
            var error = Marshal.GetLastWin32Error();
            throw new InvalidOperationException(
                $"WinDivert open failed (error {error}). Requires Administrator.");
        }
        WinDivertSetParam(_handle, WINDIVERT_PARAM_QUEUE_LEN, 8192);

        var t = new Thread(CaptureThread) { Name = "WinDivert", IsBackground = true };
        t.Start();
        Console.WriteLine("[WinDivert] SNIFF mode active — monitoring TCP/443");
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

                // SNIFF mode: just monitor, no modification.
                var sni = TlsHelper.ExtractSni(new ReadOnlySpan<byte>(_packetBuffer, 0, recvLen));
                if (sni != null)
                    Console.WriteLine($"[SNI] {sni}");

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
        catch (Exception ex)
        {
            if (!_disposed)
                Console.Error.WriteLine($"[WinDivert] Error: {ex.Message}");
        }
    }

    public void Dispose()
    {
        _disposed = true;
        Close();
    }
}
