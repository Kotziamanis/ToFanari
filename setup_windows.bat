@echo off
REM One-time setup: venv + pip install (run from repo root on Windows)
cd /d "%~dp0"
echo Creating virtual environment .venv ...
py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv 2>nul || py -3.10 -m venv .venv 2>nul || python -m venv .venv
if not exist ".venv\Scripts\activate.bat" (
  echo ERROR: Could not create venv. Install Python 3.10+ from python.org and enable "Add to PATH".
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Done.
echo   To work: double-click this folder in Explorer, Shift+Right-click -^> "Open in Terminal", then:
echo     .venv\Scripts\activate.bat
echo     python main.py
echo.
pause
