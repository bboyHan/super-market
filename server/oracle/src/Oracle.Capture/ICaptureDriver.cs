using System.Net;

namespace Oracle.Capture;

/// <summary>
/// Abstraction over the WinDivert kernel driver.
/// In production, implemented by WinDivert P/Invoke.
/// In development, implemented by a mock/pcap file reader.
/// </summary>
public interface ICaptureDriver : IDisposable
{
    void Open(int queueLen = 8192);
    void Close();
    bool Read(out CapturedPacket packet);
    void Send(CapturedPacket packet);
    event Action<CapturedPacket>? OnPacketCaptured;
}

/// <summary>
/// A captured network packet from WinDivert.
/// Contains both raw data and parsed metadata.
/// </summary>
public class CapturedPacket
{
    public byte[] RawData { get; set; } = Array.Empty<byte>();
    public IPAddress SrcAddr { get; set; } = IPAddress.Any;
    public IPAddress DstAddr { get; set; } = IPAddress.Any;
    public ushort SrcPort { get; set; }
    public ushort DstPort { get; set; }
    public bool IsOutbound { get; set; } = true;

    /// <summary>
    /// Extract TLS SNI from ClientHello (first packet only).
    /// Returns null for non-TLS or non-handshake packets.
    /// </summary>
    public string? ExtractSni()
    {
        return TlsHelper.ExtractSni(RawData.AsSpan());
    }

    public ConnectionKey GetConnectionKey()
    {
        return new ConnectionKey(
            BitConverter.ToUInt32(SrcAddr.GetAddressBytes()),
            SrcPort,
            BitConverter.ToUInt32(DstAddr.GetAddressBytes()),
            DstPort
        );
    }
}
