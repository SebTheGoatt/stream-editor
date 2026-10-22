# One-time setup on Windows. Run from the repo folder:
#   powershell -ExecutionPolicy Bypass -File setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

$installed = $false
if (-not (Have python)) {
    Write-Host "Installing Python 3.12..."
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    $installed = $true
}
if (-not (Have ffmpeg)) {
    Write-Host "Installing FFmpeg..."
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    $installed = $true
}
if ($installed) {
    # New programs only show up on PATH in a fresh terminal.
    Write-Host "Installed. Close and reopen this terminal, then run setup.ps1 again."
    exit 0
}

if (-not (Test-Path .venv)) { python -m venv .venv }
$py = ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install faster-whisper numpy auto-editor
$gpu = Have nvidia-smi
if ($gpu) {
    # CUDA build: much faster AI upscaling on NVIDIA cards.
    & $py -m pip install torch --index-url https://download.pytorch.org/whl/cu124
} else {
    & $py -m pip install torch --index-url https://download.pytorch.org/whl/cpu
}

& $py make_sfx.py sfx
if (Test-Path pack) { & $py tools\import_pack.py pack }

Write-Host ""
Write-Host "Ready. Put a stream recording in work\ and ask Claude to use the coryxkenshin-edit skill,"
Write-Host "or follow README.md step by step."
