# Build portable onedir for Windows 7+ .
#
# Prefer CPython 3.7.9 on the build machine (Win7-safe ABI). Python 3.8+
# frozen apps need Win7 security updates (KB2533623 / KB3063858) or they
# fail importing _socket with "The parameter is incorrect".
#
# Local (recommended for Win7 target):
#   py -3.7 -m pip install -e ".[gui,packaging]"
#   powershell -File packaging/build-win7.ps1
#
# CI: release.yml installs Python 3.7.9 into C:\Python37 and sets
# LUMI_PRINT_PYTHON before calling this script.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$py = $env:LUMI_PRINT_PYTHON
if (-not $py) {
    foreach ($candidate in @("py -3.7", "py -3.8", "python")) {
        try {
            $null = Invoke-Expression "$candidate -c \"import sys; print(sys.version)\""
            $py = $candidate
            break
        } catch {
        }
    }
}

if (-not $py) {
    throw "No Python found. Install CPython 3.7.9 for Win7-compatible builds."
}

Write-Host "Building LumiPrintAgent with $py"
$ver = Invoke-Expression "$py -c \"import sys; print('%d.%d' % sys.version_info[:2])\""
Write-Host "Python version: $ver"
if ($ver -and ([version]$ver -ge [version]"3.8")) {
    Write-Warning "Python $ver: frozen EXE may require Win7 KB2533623/KB3063858 for _socket. Prefer 3.7.9."
}

Invoke-Expression "$py -m PyInstaller --noconfirm --clean packaging/lumi-print-agent.spec"

$dist = Join-Path $Root "dist\LumiPrintAgent"
if (-not (Test-Path $dist)) {
    throw "dist/LumiPrintAgent not found"
}

Write-Host "OK: $dist"
Write-Host "Copy the folder to the cashier PC and run LumiPrintAgent.exe once."
Write-Host "The agent self-installs to %LOCALAPPDATA%\Lumi\print-agent\"
