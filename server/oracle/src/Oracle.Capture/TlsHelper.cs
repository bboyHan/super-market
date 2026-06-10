using System.Text;

namespace Oracle.Capture;

/// <summary>
/// TLS ClientHello SNI extractor.
/// Parses the minimum TLS handshake bytes to extract the SNI extension field.
/// Reference: RFC 6066 Section 3 - Server Name Indication
/// </summary>
public static class TlsHelper
{
    /// <summary>
    /// Extract the SNI (Server Name Indication) from a TLS ClientHello.
    /// Handles both raw TLS records (from SslStream) and IP-encapsulated
    /// TLS (from WinDivert kernel capture).
    /// Returns null if the data is not a valid ClientHello or SNI is not present.
    /// </summary>
    public static string? ExtractSni(ReadOnlySpan<byte> data)
    {
        if (data.Length < 50) return null;

        // Find TLS record type 0x16 (Handshake) in the data.
        // WinDivert provides full IP packets (starting with IP header),
        // while direct TLS streams start with the TLS record.
        int start = 0;
        if (data[0] != 0x16)
        {
            // Search for TLS handshake record within first 200 bytes
            for (int i = 0; i < Math.Min(data.Length - 5, 200); i++)
            {
                if (data[i] == 0x16 && data[i + 1] == 0x03)
                {
                    start = i;
                    break;
                }
            }
            if (start == 0 && data[0] != 0x16) return null;
        }

        // TLS record type check (already matched at start)
        // TLS record version (major/minor) - skip 2 bytes (start+1, start+2)
        // Skip TLS record length (2 bytes) - positions start+3, start+4
        // Check handshake type: 0x01 = ClientHello at position start+5
        if (data[start + 5] != 0x01) return null;

        // Skip: handshake length (3 bytes at start+6..8), version (2 bytes at start+9..10)
        // Random (32 bytes starting at start+11)
        // Total fixed header: 5 + 4 + 2 + 32 = 43 bytes to session ID
        int pos = start + 43;

        // --- Session ID ---
        if (pos >= data.Length) return null;
        int sessionIdLen = data[pos++];
        if (pos + sessionIdLen > data.Length) return null;
        pos += sessionIdLen;

        // --- Cipher Suites ---
        if (pos + 1 >= data.Length) return null;
        int cipherLen = (data[pos] << 8) | data[pos + 1];
        pos += 2 + cipherLen;
        if (pos > data.Length) return null;

        // --- Compression Methods ---
        if (pos >= data.Length) return null;
        int compLen = data[pos++];
        pos += compLen;
        if (pos > data.Length) return null;

        // --- Extensions ---
        if (pos + 1 >= data.Length) return null;
        int extLen = (data[pos] << 8) | data[pos + 1];
        pos += 2;
        int extEnd = pos + extLen;
        if (extEnd > data.Length) extEnd = data.Length;

        // Walk through extensions looking for SNI (type 0x0000)
        while (pos + 4 <= extEnd)
        {
            int extType = (data[pos] << 8) | data[pos + 1];
            int extDataLen = (data[pos + 2] << 8) | data[pos + 3];
            pos += 4;

            if (extType == 0x0000) // SNI extension
            {
                // Skip SNI list length (2 bytes)
                if (pos + 2 > data.Length) return null;
                pos += 2;

                // SNI entry type (1 byte): 0x00 = host_name
                if (pos >= data.Length) return null;
                int nameType = data[pos++];
                if (nameType != 0x00) return null;

                // SNI name length (2 bytes)
                if (pos + 1 >= data.Length) return null;
                int nameLen = (data[pos] << 8) | data[pos + 1];
                pos += 2;

                if (pos + nameLen > data.Length) return null;
                return Encoding.ASCII.GetString(data.Slice(pos, nameLen));
            }

            pos += extDataLen;
        }

        return null;
    }
}
