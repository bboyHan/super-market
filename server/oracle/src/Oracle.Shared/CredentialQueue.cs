using System.Collections.Concurrent;
using System.Text;
using System.Text;
using System.Text.Json;

namespace Oracle.Shared;

/// <summary>
/// Thread-safe credential queue with batching.
/// Accumulates credentials and sends them in batches to the Python backend.
/// </summary>
public class CredentialQueue : IDisposable
{
    private readonly ConcurrentQueue<Credential> _queue = new();
    private readonly OracleConfig _config;
    private readonly HttpClient _http;
    private readonly Timer _flushTimer;
    private long _totalEnqueued;
    private long _totalSent;
    private long _totalFailed;

    public CredentialQueue(OracleConfig config)
    {
        _config = config;
        _http = new HttpClient { Timeout = TimeSpan.FromSeconds(config.HttpTimeoutSec) };
        _flushTimer = new Timer(
            _ => Flush(),
            null,
            TimeSpan.FromMilliseconds(config.BatchIntervalMs),
            TimeSpan.FromMilliseconds(config.BatchIntervalMs));
    }

    public long TotalEnqueued => Interlocked.Read(ref _totalEnqueued);
    public long TotalSent => Interlocked.Read(ref _totalSent);
    public long TotalFailed => Interlocked.Read(ref _totalFailed);
    public int PendingCount => _queue.Count;

    public async Task EnqueueAsync(Credential credential)
    {
        _queue.Enqueue(credential);
        Interlocked.Increment(ref _totalEnqueued);

        if (_queue.Count >= _config.BatchSize)
            await FlushAsync();
    }

    private void Flush()
    {
        if (_queue.IsEmpty) return;
        _ = FlushAsync();
    }

    private async Task FlushAsync()
    {
        var batch = new List<Credential>(_config.BatchSize);
        while (_queue.TryDequeue(out var cred) && batch.Count < _config.BatchSize)
            batch.Add(cred);

        if (batch.Count == 0) return;

        try
        {
            // Send each credential individually (Python endpoint expects single objects)
            foreach (var cred in batch)
            {
                try
                {
                    var json = JsonSerializer.Serialize(cred.ToIngestPayload());
                    var content = new StringContent(json, Encoding.UTF8, "application/json");
                    var response = await _http.PostAsync($"{_config.BackendUrl}{_config.IngestEndpoint}", content);

                    if (response.IsSuccessStatusCode)
                    {
                        Interlocked.Increment(ref _totalSent);
                    }
                    else
                    {
                        Interlocked.Increment(ref _totalFailed);
                    }
                }
                catch
                {
                    Interlocked.Increment(ref _totalFailed);
                }
            }


            return;
        }
        catch
        {
            foreach (var cred in batch)
                _queue.Enqueue(cred);
        }
    }

    public void Dispose()
    {
        Flush();
        _flushTimer.Dispose();
        _http.Dispose();
    }
}
