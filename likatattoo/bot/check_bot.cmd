@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found. Creating...
  python -m venv .venv
  call ".venv\Scripts\activate"
  pip install -r requirements.txt
) else (
  call ".venv\Scripts\activate"
)
python main.py --check
