@echo off
cd /d "%~dp0"
echo Downloading SmartTube and NewPipe from their official sources...
python x50_get_apps.py --out "Custom App\install\app" smarttube newpipe
if errorlevel 1 (
  echo.
  echo Something went wrong. Make sure Python 3 is installed with "Add python.exe to PATH" ticked.
) else (
  echo.
  echo Done. Copy everything INSIDE "Custom App\install" to the root of a FAT32 USB ^(32GB or smaller^).
)
pause
