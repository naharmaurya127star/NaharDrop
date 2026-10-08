@echo off
rem Convenience launcher for Windows: creates the venv on first run,
rem installs/updates dependencies, then starts the server. Any arguments are
rem passed straight through to run.py (e.g. run.bat --https --dest D:\Incoming).
cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat
pip install -q --upgrade pip
pip install -q -r requirements.txt
python run.py %*
