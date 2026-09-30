@echo off
chcp 65001 > nul
echo ========================================================
echo   Compilando Slideshow com PyInstaller (via uv)
echo ========================================================
uv run --with pyinstaller python build.py --pyinstaller
echo.
pause
