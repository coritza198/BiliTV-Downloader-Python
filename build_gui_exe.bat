@echo off
setlocal
cd /d "%~dp0"
py -m pip install -r requirements-build.txt || exit /b 1
py -m PyInstaller --noconfirm --clean --onefile --windowed --name BiliTV-Downloader-GUI bilitv_gui.py || exit /b 1
echo.
echo Build successful: dist\BiliTV-Downloader-GUI.exe
pause
