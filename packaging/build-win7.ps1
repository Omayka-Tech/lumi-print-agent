# Build portable onedir for Windows 7+.
#
# Prefer CPython 3.7.9 (Win7-safe ABI). Python 3.8+ frozen apps need
# Win7 updates KB2533623 / KB3063858 or _socket fails with
# "The parameter is incorrect".
#
# Local:
#   py -3.7 -m pip install -e ".[gui,packaging]"
#   powershell -File packaging/build-win7.ps1
#
# CI sets LUMI_PRINT_PYTHON=C:\Python37\python.exe

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Resolve-Python {
    if ($env:LUMI_PRINT_PYTHON -and (Test-Path $env:LUMI_PRINT_PYTHON)) {
        return $env:LUMI_PRINT_PYTHON
    }
    foreach ($candidate in @(
            "C:\Python37\python.exe",
            "${env:LocalAppData}\Programs\Python\Python37\python.exe"
        )) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    throw "No Python found. Install CPython 3.7.9 for Win7-compatible builds."
}

$py = Resolve-Python
Write-Host "Building LumiPrintAgent with $py"

$ver = & $py -c "import sys; print('{0}.{1}'.format(sys.version_info[0], sys.version_info[1]))"
Write-Host "Python version: $ver"
$majorMinor = [version]$ver
if ($majorMinor -ge [version]"3.8") {
    Write-Warning "Python $ver may require Win7 KB2533623/KB3063858 for _socket. Prefer 3.7.9."
}

& $py -m PyInstaller --noconfirm --clean packaging/lumi-print-agent.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$dist = Join-Path $Root "dist\LumiPrintAgent"
if (-not (Test-Path $dist)) {
    throw "dist/LumiPrintAgent not found"
}

Write-Host "OK: $dist"
Write-Host "Copy the folder to the cashier PC and run LumiPrintAgent.exe once."
Write-Host "The agent self-installs to %LOCALAPPDATA%\Lumi\print-agent\"
