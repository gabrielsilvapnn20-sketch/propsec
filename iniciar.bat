@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Primeira execucao: instalando...
  py -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install -r requirements.txt
  .venv\Scripts\python propsec.py semear
)
start "" http://localhost:8000
.venv\Scripts\python propsec.py servidor
