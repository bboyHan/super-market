namespace Oracle.Capture;

/// <summary>
/// Fast SNI-based packet filter using domain suffix matching.
/// </summary>
public class PacketFilter
{
    private readonly string[] _payDomains;

    public PacketFilter(string[] payDomains)
    {
        _payDomains = payDomains ?? throw new ArgumentNullException(nameof(payDomains));
    }

    /// <summary>
    /// Check if the SNI belongs to a payment domain.
    /// Uses ReadOnlySpan for zero-allocation comparison.
    /// </summary>
    public bool IsPayDomain(ReadOnlySpan<char> sni)
    {
        if (sni.IsEmpty) return false;

        foreach (var domain in _payDomains)
        {
            // Exact match
            if (sni.SequenceEqual(domain.AsSpan()))
                return true;

            // Suffix match: .domain.com matches subdomain.domain.com
            if (sni.Length > domain.Length &&
                sni[sni.Length - domain.Length - 1] == '.' &&
                sni.Slice(sni.Length - domain.Length).SequenceEqual(domain.AsSpan()))
                return true;
        }

        return false;
    }
}
