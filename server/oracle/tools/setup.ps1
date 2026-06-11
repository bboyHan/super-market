# Oracle Setup Script
# Run as Administrator: powershell -ExecutionPolicy Bypass -File setup.ps1

param(
    [string]$SourceDir = "",
    [string]$InstallDir = "$env:ProgramFiles\Oracle",
    [switch]$NoService = $false,
    [switch]$Force = $false
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Auto-detect source directory
if (-not $SourceDir) {
    # Prefer publish_final over publish_new over publish
    $candidate = Join-Path $scriptDir "..\publish_final"
    if (Test-Path "$candidate\Oracle.Api.exe") { $SourceDir = (Resolve-Path $candidate).Path }
    else {
        $candidate = Join-Path $scriptDir "..\publish_new"
        if (Test-Path "$candidate\Oracle.Api.exe") { $SourceDir = (Resolve-Path $candidate).Path }
        else {
            $candidate = Join-Path $scriptDir "..\publish"
            if (Test-Path "$candidate\Oracle.Api.exe") { $SourceDir = (Resolve-Path $candidate).Path }
            else {
                $candidate = Join-Path $scriptDir "..\src\Oracle.Api\bin\Debug\net8.0\win-x64"
                if (Test-Path "$candidate\Oracle.Api.exe") { $SourceDir = (Resolve-Path $candidate).Path }
            }
        }
    }
}

function Write-OK($text) { Write-Host "[OK] $text" -ForegroundColor Green }
function Write-ER($text) { Write-Host "[ER] $text" -ForegroundColor Red }
function Write-WN($text) { Write-Host "[!!] $text" -ForegroundColor Yellow }
function Write-Info($text) { Write-Host "[..] $text" -ForegroundColor Cyan }

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($id)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Oracle Universal Data Collector Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Check admin
if (-not (Test-Admin)) {
    Write-WN "Administrator privileges required. Requesting elevation..."
    Start-Process powershell -Verb RunAs -ArgumentList @(
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`"",
        "-SourceDir", "`"$SourceDir`"",
        "-InstallDir", "`"$InstallDir`""
    )
    exit
}

# Validate source
if (-not $SourceDir -or -not (Test-Path "$SourceDir\Oracle.Api.exe")) {
    Write-ER "Oracle.Api.exe not found at $SourceDir"
    exit 1
}

$SourceDir = (Resolve-Path $SourceDir).Path
Write-Info "Source: $SourceDir"
Write-Info "Target: $InstallDir"

# Step 1: Create directories
Write-Host "[1/6] Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path "$InstallDir" -Force | Out-Null
New-Item -ItemType Directory -Path "$InstallDir\logs" -Force | Out-Null
New-Item -ItemType Directory -Path "$InstallDir\platforms" -Force | Out-Null
New-Item -ItemType Directory -Path "$InstallDir\wwwroot" -Force | Out-Null
Write-OK "Directories created"

# Step 2: Copy files
Write-Host "[2/6] Copying files..." -ForegroundColor Yellow
Get-ChildItem "$SourceDir\*.exe" | Copy-Item -Destination $InstallDir -Force
Get-ChildItem "$SourceDir\*.dll" | Copy-Item -Destination $InstallDir -Force
Get-ChildItem "$SourceDir\*.json" | Copy-Item -Destination $InstallDir -Force
if (Test-Path "$SourceDir\WinDivert.dll") { Copy-Item "$SourceDir\WinDivert.dll" "$InstallDir\" -Force }
if (Test-Path "$SourceDir\WinDivert64.sys") { Copy-Item "$SourceDir\WinDivert64.sys" "$InstallDir\" -Force }
if (Test-Path "$SourceDir\platforms\*.json") { Copy-Item "$SourceDir\platforms\*.json" "$InstallDir\platforms\" -Force }
if (Test-Path "$SourceDir\wwwroot") { Copy-Item "$SourceDir\wwwroot\*" "$InstallDir\wwwroot\" -Force }
Write-OK "Files copied"

# Step 3: Install WinDivert driver
Write-Host "[3/6] Installing WinDivert driver..." -ForegroundColor Yellow
$sysPath = "$InstallDir\WinDivert64.sys"
if (Test-Path $sysPath) {
    sc.exe stop OracleDivert 2>$null
    sc.exe delete OracleDivert 2>$null
    Start-Sleep -Milliseconds 500

    sc.exe create OracleDivert binPath= "$sysPath" type= kernel start= demand 2>$null
    if ($LASTEXITCODE -eq 0) {
        sc.exe start OracleDivert 2>$null
        Write-OK "WinDivert driver installed and started"
    } else {
        Write-WN "WinDivert driver registration failed (may already exist)"
    }
} else {
    Write-WN "WinDivert64.sys not found (CONNECT proxy mode still works)"
}

# Copy WinDivert.dll to system32
$winDivertDll = "$InstallDir\WinDivert.dll"
if (Test-Path $winDivertDll) {
    Copy-Item $winDivertDll "$env:SystemRoot\System32\WinDivert.dll" -Force -ErrorAction SilentlyContinue
}

# Step 4: Install root CA certificate
Write-Host "[4/6] Installing root CA certificate..." -ForegroundColor Yellow
$exePath = "$InstallDir\Oracle.Api.exe"
if (Test-Path $exePath) {
    Write-Info "Generating and installing root CA certificate..."
    try {
        $output = & $exePath --install-cert 2>&1 | Out-String
        Write-Info $output
    } catch {
        Write-WN "Cert generation failed: $_"
    }

    Start-Sleep -Seconds 2
    $certCheck = certutil -store Root Oracle 2>&1 | Select-String "Oracle"
    if ($certCheck) {
        Write-OK "Root CA certificate installed"
    } else {
        Write-WN "Manual cert install required. Run this as Administrator:"
        Write-WN "  $exePath --install-cert"
    }
}

# Step 5: Register Windows service
if (-not $NoService) {
    Write-Host "[5/6] Registering Windows service..." -ForegroundColor Yellow
    sc.exe stop OracleService 2>$null
    sc.exe delete OracleService 2>$null
    Start-Sleep -Milliseconds 500

    $binPath = "`"$InstallDir\Oracle.Api.exe`" --api-port 18801 --tls-port 18802"
    sc.exe create OracleService binPath= "$binPath" start= auto displayName= "Oracle Data Collector"
    sc.exe description OracleService "Oracle - Universal Data Collection Engine"
    if ($LASTEXITCODE -eq 0) {
        Write-OK "Windows service registered"
        sc.exe start OracleService
        Write-OK "Service started"
    } else {
        Write-WN "Service registration failed"
    }
} else {
    Write-Info "Skipping service registration"
}

# Step 6: Create desktop shortcuts
Write-Host "[6/6] Creating shortcuts..." -ForegroundColor Yellow
try {
    $wsh = New-Object -ComObject WScript.Shell
    $sc = $wsh.CreateShortcut("$env:USERPROFILE\Desktop\Oracle Dashboard.lnk")
    $sc.TargetPath = "http://localhost:18801"
    $sc.Description = "Oracle Data Collector Dashboard"
    $sc.Save()

    $sc2 = $wsh.CreateShortcut("$env:USERPROFILE\Desktop\Oracle Start.lnk")
    $sc2.TargetPath = "$InstallDir\Oracle.Api.exe"
    $sc2.Arguments = "--api-port 18801 --tls-port 18802"
    $sc2.WorkingDirectory = "$InstallDir"
    $sc2.Description = "Start Oracle Engine"
    $sc2.Save()
    Write-OK "Shortcuts created"
} catch {
    Write-WN "Shortcut creation failed: $_"
}

Write-Host "============================================" -ForegroundColor Green
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "" -ForegroundColor Green
Write-Host "  Dashboard: http://localhost:18801" -ForegroundColor Cyan
Write-Host "  Proxy:     127.0.0.1:18802" -ForegroundColor Cyan
Write-Host "" -ForegroundColor Green
Write-Host "  Quick Start:" -ForegroundColor Green
Write-Host "  1. Set Chrome proxy to 127.0.0.1:18802" -ForegroundColor Green
Write-Host "  2. Visit your target website" -ForegroundColor Green
Write-Host "  3. Open http://localhost:18801 to view data" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
