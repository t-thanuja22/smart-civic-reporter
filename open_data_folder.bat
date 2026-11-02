@echo off
cd /d "%~dp0"
python manage_data.py where
echo.
echo Opening the data folder...
start "" "%LOCALAPPDATA%\SmartCivicReporter"
pause
