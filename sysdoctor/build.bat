@echo off
setlocal
where python >nul 2>nul
if errorlevel 1 (
    echo Python 3.9+ not found in PATH. Install it from https://www.python.org/downloads/
    exit /b 1
)
python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo Failed to install PyInstaller.
    exit /b 1
)
python -m PyInstaller --onefile --console --clean --name sysdoctor sysdoctor.py
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)
echo.
echo Done: dist\sysdoctor.exe
echo Try:  dist\sysdoctor.exe info
