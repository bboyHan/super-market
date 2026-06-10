# 神谕 (Oracle) 一键编译运行脚本
# 用法: .\build-and-run.ps1

$ErrorActionPreference = "Continue"

Write-Host "=== 神谕 (Oracle) 编译运行 ===" -ForegroundColor Cyan

# 1. 配置 .NET 路径
$env:Path = "$env:USERPROFILE\.dotnet;$env:Path"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# 2. 编译
Write-Host "[1/4] 编译..." -ForegroundColor Yellow
dotnet build Oracle.sln -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "编译失败，错误码: $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

# 3. 发布
Write-Host "[2/4] 发布..." -ForegroundColor Yellow
dotnet publish src\Oracle.Api\Oracle.Api.csproj `
    -c Release -r win-x64 --self-contained true -o publish -q 2>$null
Copy-Item "$env:LOCALAPPDATA\Oracle\WinDivert.dll" publish\ -Force -ErrorAction SilentlyContinue

# 4. 杀掉旧进程
Write-Host "[3/4] 停止旧进程..." -ForegroundColor Yellow
taskkill /F /IM Oracle.Api.exe 2>$null
Start-Sleep -Seconds 2

# 5. 启动
Write-Host "[4/4] 启动..." -ForegroundColor Green
Set-Location publish
Start-Process -FilePath ".\Oracle.Api.exe" -WindowStyle Normal
Write-Host "Oracle 已启动 (PID: 请查看新窗口)" -ForegroundColor Green
Write-Host ""
Write-Host "管理 API: http://127.0.0.1:18801" -ForegroundColor Cyan
Write-Host "TLS 代理: 127.0.0.1:18802" -ForegroundColor Cyan
