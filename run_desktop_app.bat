@echo off
REM Launches the desktop app from source (no build/packaging step) - always
REM runs whatever is currently on disk, so a code change takes effect on the
REM very next launch with no rebuild needed.
cd /d "%~dp0"
python -m islamic_research_hub.interfaces.desktop_app
if errorlevel 1 (
    echo.
    echo The app exited with an error - see above.
    pause
)
