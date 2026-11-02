@echo off
cd /d "%~dp0"
echo Installing requirements (first run only takes a minute)...
pip install -r requirements.txt
echo.
python app.py
pause
