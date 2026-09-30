@echo off
chcp 65001 > nul
echo ========================================================
echo   Compilando Slideshow com PyInstaller (via uv)
echo ========================================================
uv run --isolated --python 3.12 --with pyinstaller python build.py --pyinstaller
echo.
pause
