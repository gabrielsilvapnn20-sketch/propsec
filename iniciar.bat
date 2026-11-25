@echo off
cd /d "%~dp0"
rem Fecha um painel antigo que ainda esteja rodando na porta 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
if not exist .venv (
  echo Primeira execucao: instalando...
  py -m venv .venv || python -m venv .venv
)
.venv\Scripts\python -m pip install -q -r requirements.txt
.venv\Scripts\python propsec.py semear
start "" http://localhost:8000
.venv\Scripts\python propsec.py servidor
