@echo off
cd /d "%~dp0"
set PYTHONPATH=src
echo Starting Islamic Research Hub...
python -m islamic_research_hub.interfaces.web_app_cli
pause
