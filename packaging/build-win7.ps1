# Build portable onedir for Windows 7+ (CPython 3.8).
# Run on a Win7 32/64 VM or a machine with Python 3.8:
#   py -3.8 -m pip install -e ".[gui,packaging]"
#   powershell -File packaging/build-win7.ps1
#
# GitHub-hosted runners are not Windows 7. Produce the Win7 artifact locally
# or on a self-hosted runner with Python 3.8.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$py = $env:LUMI_PRINT_PYTHON
if (-not $py) {
    $py = "py -3.8"
}

Write-Host "Building LumiPrintAgent with $py"
Invoke-Expression "$py -m PyInstaller --noconfirm --clean packaging/lumi-print-agent.spec"

$dist = Join-Path $Root "dist\LumiPrintAgent"
if (-not (Test-Path $dist)) {
    throw "dist/LumiPrintAgent not found"
}

Write-Host "OK: $dist"
Write-Host "Copy the folder to the cashier PC and run LumiPrintAgent.exe once."
Write-Host "The agent self-installs to %LOCALAPPDATA%\Lumi\print-agent\"
