@echo off
rem Starts NaharDrop, opens the laptop dashboard in the default browser, and
rem keeps this window open so you can see the QR code, PIN and server logs.
rem Extra arguments are passed to run.py (e.g. start.bat --no-pin).
title NaharDrop
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo First run: creating virtual environment and installing dependencies...
    python -m venv venv
    call venv\Scripts\activate.bat
    python -m pip install -q --upgrade pip
    python -m pip install -q -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

rem Open the dashboard shortly after the server starts listening.
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:8000'"

python run.py %*

echo.
echo NaharDrop has stopped.
pause
