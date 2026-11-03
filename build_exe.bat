@echo off
setlocal
python -m pip install -r requirements-build.txt || exit /b 1
python -m PyInstaller --onefile --console --name BiliTV-Downloader bilitv_downloader.py || exit /b 1
echo EXE created: dist\BiliTV-Downloader.exe
