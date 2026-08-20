# Build portable onedir for Windows 7+ (CPython 3.8).
# Local:
#   py -3.8 -m pip install -e ".[gui,packaging]"
#   powershell -File packaging/build-win7.ps1
#
# CI (GitHub-hosted windows-* + setup-python 3.8): uses `python` from PATH.
# The runner OS is not Windows 7; CPython 3.8 produces a portable Win7+ onedir.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$py = $env:LUMI_PRINT_PYTHON
if (-not $py) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        $py = "python"
    } else {
        $py = "py -3.8"
    }
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
