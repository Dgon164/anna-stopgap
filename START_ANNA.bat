@echo off
rem ANNA - double-click me. A page opens in your browser; drop a
rem file on it. Runs on this computer only. Close this window to
rem stop anna.
cd /d "%~dp0"
python anna_ui.py
if errorlevel 1 pause
