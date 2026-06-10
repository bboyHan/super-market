# 神谕 (Oracle) 安装脚本
# 需要管理员权限

param(
    [string]$OraclePath = "$env:LOCALAPPDATA\Oracle"
)

$ErrorActionPreference = "Stop"

Write-Host "╔══════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  神谕 (Oracle) 安装               ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════╝" -ForegroundColor Cyan

# 1. 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal]`
    [Security.Principal.WindowsIdentity]::GetCurrent())`
    .IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin)
{
    Write-Host "❌ 需要管理员权限运行" -ForegroundColor Red
    Write-Host "请右键 PowerShell → 以管理员身份运行" -ForegroundColor Yellow
    exit 1
}

# 2. 创建目录
Write-Host "[1/4] 创建目录..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path "$OraclePath" -Force | Out-Null

# 3. 安装 WinDivert 驱动
Write-Host "[2/4] 安装 WinDivert 驱动..." -ForegroundColor Yellow
$divertPath = "$OraclePath\WinDivert64.sys"
if (Test-Path $divertPath)
{
    sc.exe create OracleDivert binPath=$divertPath type=kernel start=demand 2>$null
    sc.exe start OracleDivert 2>$null
    Write-Host "  ✅ WinDivert 驱动已安装" -ForegroundColor Green
}
else
{
    Write-Host "  ⚠️ WinDivert64.sys 未找到，请从 WinDivert 项目获取" -ForegroundColor Yellow
    Write-Host "  下载地址: https://github.com/basil00/WinDivert/releases" -ForegroundColor Yellow
}

# 4. 安装根证书
Write-Host "[3/4] 安装根证书..." -ForegroundColor Yellow
$caPath = "$OraclePath\oracle_ca.cer"
if (Test-Path $caPath)
{
    certutil -addstore -f "Root" $caPath
    Write-Host "  ✅ 根证书已安装到系统信任区" -ForegroundColor Green
}
else
{
    Write-Host "  ⚠️ 根证书文件未找到" -ForegroundColor Yellow
    Write-Host "  首次启动 Oracle 时会自动生成" -ForegroundColor Yellow
}

# 5. 注册服务
Write-Host "[4/4] 注册系统服务..." -ForegroundColor Yellow
$oracleExe = "$OraclePath\oracle.exe"
if (Test-Path $oracleExe)
{
    sc.exe create Oracle binPath=$oracleExe start=auto 2>$null
    Write-Host "  ✅ Oracle 服务已注册" -ForegroundColor Green
}

Write-Host "`n✅ 安装完成!" -ForegroundColor Green
