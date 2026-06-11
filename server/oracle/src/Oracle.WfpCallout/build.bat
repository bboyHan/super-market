@echo off
REM Oracle WFP Callout — QUIC Block Driver Build Script
REM Requirements: Visual Studio 2022 + WDK (Windows Driver Kit)
REM
REM Usage:
REM   1. Open "Developer Command Prompt for VS 2022"
REM   2. cd to this directory
REM   3. run build.bat

setlocal

if "%WDKContentRoot%"=="" (
    echo [ERROR] WDK not detected. Please install WDK first.
    echo         https://learn.microsoft.com/en-us/windows-hardware/drivers/download-the-wdk
    exit /b 1
)

set BUILD_DIR=build
if not exist %BUILD_DIR% mkdir %BUILD_DIR%

cl.exe ^
    /nologo ^
    /W4 ^
    /WX ^
    /kernel ^
    /O2 ^
    /Fo%BUILD_DIR%\ ^
    /Fe%BUILD_DIR%\OracleQuicBlock.sys ^
    quic_block.c ^
    /link ^
    /subsystem:native ^
    /driver ^
    /base:0x10000 ^
    /entry:DriverEntry ^
    fwpkclnt.lib ^
    ntoskrnl.lib

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Build successful: %BUILD_DIR%\OracleQuicBlock.sys
    echo.
    echo To install:
    echo   sc create OracleQuicBlock type=kernel binPath=%~dp0%BUILD_DIR%\OracleQuicBlock.sys
    echo   sc start OracleQuicBlock
    echo.
    echo To uninstall:
    echo   sc stop OracleQuicBlock
    echo   sc delete OracleQuicBlock
) else (
    echo.
    echo [ERROR] Build failed.
)
