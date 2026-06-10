# 神谕 (Oracle) 依赖安装脚本
param([string]$InstallDir = "$env:LOCALAPPDATA\Oracle")

$ErrorActionPreference = "Stop"

Write-Host "=== 神谕 依赖安装 ===" -ForegroundColor Cyan

# 1. 创建目录
New-Item -ItemType Directory -Path "$InstallDir" -Force | Out-Null

# 2. 下载 WinDivert
$divertUrl = "https://github.com/basil00/WinDivert/releases/download/v2.2.0/WinDivert-2.2.0.zip"
$zipPath = "$env:TEMP\WinDivert.zip"
$unzipPath = "$env:TEMP\WinDivert"

Write-Host "[1/3] 下载 WinDivert..." -ForegroundColor Yellow
if (!(Test-Path $zipPath)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $divertUrl -OutFile $zipPath
}
else {
    Write-Host "  已下载，跳过"
}

# 3. 解压
Write-Host "[2/3] 解压 WinDivert..." -ForegroundColor Yellow
if (Test-Path $unzipPath) { Remove-Item -Recurse -Force $unzipPath }
Expand-Archive -Path $zipPath -DestinationPath $unzipPath

# 4. 复制文件
Write-Host "[3/3] 复制文件..." -ForegroundColor Yellow
$arch = if ([Environment]::Is64BitOperatingSystem) { "x64" } else { "x86" }
Copy-Item "$unzipPath\WinDivert-$arch\WinDivert64.sys" "$InstallDir\" -Force
Copy-Item "$unzipPath\WinDivert-$arch\WinDivert.dll" "$InstallDir\" -Force

Write-Host "`n✅ WinDivert 已安装到 $InstallDir" -ForegroundColor Green
Write-Host "   接下来需要以管理员身份运行: install.ps1 来安装驱动" -ForegroundColor Yellow
