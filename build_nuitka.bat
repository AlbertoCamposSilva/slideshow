@echo off
chcp 65001 > nul
echo ========================================================
echo   Compilando Slideshow com Nuitka (via uv)
echo ========================================================
uv run --python 3.12 --with nuitka --with zstandard python build.py --nuitka
echo.
pause
