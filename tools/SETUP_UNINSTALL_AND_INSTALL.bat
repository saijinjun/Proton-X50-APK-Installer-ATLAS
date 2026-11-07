@echo off
cd /d "%~dp0"
echo Preparing X50 USB steps: uninstall old SmartTube/NewPipe, install new ones...
python x50_setup_usb.py --out X50_USB_STEPS
echo.
echo Open X50_USB_STEPS\HOW_TO_USE.txt for the steps.
pause
