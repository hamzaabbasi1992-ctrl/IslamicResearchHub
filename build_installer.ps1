# Build the desktop app into installation/IslamicResearchHub/.
#
# Requires the "build" and "gui" optional dependency groups:
#   pip install -e .[gui,build]
#
# Usage: .\build_installer.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Remove-Item -Recurse -Force "installation\IslamicResearchHub" -ErrorAction SilentlyContinue

# Real bug found on a fresh machine: with --workpath/--specpath both set to
# build_temp, this PyInstaller version (6.21.0) resolves a *relative*
# --add-data/--icon path against the spec's own directory (build_temp), not
# the project root - "assets;assets" silently failed to find
# build_temp\assets, and the script kept going and printed a false
# "Build complete" anyway, since $ErrorActionPreference = "Stop" doesn't
# catch a native .exe's non-zero exit the way it catches a PowerShell
# error. Absolute paths (anchored to $PSScriptRoot, not just cwd, so this
# still works if invoked from elsewhere) sidestep the ambiguity entirely,
# and the exit code is now checked explicitly.
pyinstaller `
    --name IslamicResearchHub `
    --windowed `
    --noconfirm `
    --icon "$PSScriptRoot\assets\app_icon.ico" `
    --add-data "$PSScriptRoot\assets;assets" `
    --distpath "$PSScriptRoot\installation" `
    --workpath "$PSScriptRoot\build_temp" `
    --specpath "$PSScriptRoot\build_temp" `
    "$PSScriptRoot\src\islamic_research_hub\interfaces\desktop_app\__main__.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build FAILED (pyinstaller exit code $LASTEXITCODE)." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Build complete: installation\IslamicResearchHub\IslamicResearchHub.exe"
Write-Host "Copy or link your data\books.db into installation\IslamicResearchHub\data\books.db before running it."
