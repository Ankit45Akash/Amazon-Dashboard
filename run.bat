@echo off
cd /d "%~dp0"
if not exist venv (
  echo Creating virtual environment...
  python -m venv venv
)
call venv\Scripts\activate
pip install -q -r requirements.txt
if not exist .env copy .env.example .env >nul
start "" http://127.0.0.1:5000
python app.py
pause
