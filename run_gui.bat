@echo off
cd /d "%~dp0"
py bilitv_gui.py
if errorlevel 1 pause
