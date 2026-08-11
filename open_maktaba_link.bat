@echo off
rem Registered as the maktaba:// protocol handler (see interfaces/desktop_app/__main__.py
rem and shared/maktaba_link.py). Windows invokes this with the clicked link as %1.
rem cd's into the project folder first, same as the desktop shortcut's "Start in" folder -
rem a registry-triggered launch doesn't get a "Start in" of its own, and the app's
rem default database/log paths are resolved relative to the working directory in dev mode.
cd /d "%~dp0"
start "" "C:\Users\MY\AppData\Local\Programs\Python\Python311\pythonw.exe" -m islamic_research_hub.interfaces.desktop_app %1
