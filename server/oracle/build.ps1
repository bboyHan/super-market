# 神谕 (Oracle) 编译脚本
# 用法: .\build.ps1 [--release|--debug]

param(
    [Switch]$Release = $false
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$config = if ($Release) { "Release" } else { "Debug" }

Write-Host "╔══════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  神谕 (Oracle) 编译              ║" -ForegroundColor Cyan
Write-Host "║  配置: $config                 ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════╝" -ForegroundColor Cyan

# 1. Restore
Write-Host "[1/3] Restoring packages..." -ForegroundColor Yellow
dotnet restore "$root\Oracle.sln"
if ($LASTEXITCODE -ne 0) { throw "Restore failed" }

# 2. Build
Write-Host "[2/3] Building..." -ForegroundColor Yellow
dotnet build "$root\Oracle.sln" -c $config --no-restore
if ($LASTEXITCODE -ne 0) { throw "Build failed" }

# 3. Publish (single file, self-contained)
Write-Host "[3/3] Publishing..." -ForegroundColor Yellow
$publishDir = "$root\publish\$config"
dotnet publish "$root\src\Oracle.Api\Oracle.Api.csproj" `
    -c $config `
    --no-build `
    -r win-x64 `
    --self-contained true `
    -o "$publishDir" `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true

if ($LASTEXITCODE -ne 0) { throw "Publish failed" }

Write-Host "`n✅ 编译完成!" -ForegroundColor Green
Write-Host "   输出: $publishDir\Oracle.Api.exe" -ForegroundColor Green
Write-Host "   大小: $((Get-Item "$publishDir\Oracle.Api.exe").Length / 1MB) MB" -ForegroundColor Green
