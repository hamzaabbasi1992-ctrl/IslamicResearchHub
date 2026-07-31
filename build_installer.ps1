# Build the desktop app into installation/IslamicResearchHub/.
#
# Requires the "build" and "gui" optional dependency groups:
#   pip install -e .[gui,build]
#
# Usage: .\build_installer.ps1

$ErrorActionPreference = "Stop"

Remove-Item -Recurse -Force "installation\IslamicResearchHub" -ErrorAction SilentlyContinue

pyinstaller `
    --name IslamicResearchHub `
    --windowed `
    --noconfirm `
    --icon "assets\app_icon.ico" `
    --add-data "assets;assets" `
    --distpath installation `
    --workpath build_temp `
    --specpath build_temp `
    "src\islamic_research_hub\interfaces\desktop_app\__main__.py"

Write-Host ""
Write-Host "Build complete: installation\IslamicResearchHub\IslamicResearchHub.exe"
Write-Host "Copy or link your data\books.db into installation\IslamicResearchHub\data\books.db before running it."
