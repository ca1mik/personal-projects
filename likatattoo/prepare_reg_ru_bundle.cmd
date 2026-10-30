@echo off
setlocal
cd /d "%~dp0"
python site\scripts\prepare_reg_ru_with_backend.py
