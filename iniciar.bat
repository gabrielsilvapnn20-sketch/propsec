@echo off
chcp 65001 >nul
cd /d "%~dp0"
title PropSec - painel
echo ============================================
echo  PropSec - iniciando o painel
echo  Pasta: %CD%
echo ============================================

rem 1) Fecha um painel antigo que ainda esteja aberto na porta 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r /c:":8000 .*LISTENING"') do taskkill /F /PID %%a >nul 2>&1

rem 2) Python
set PY=
where py >nul 2>&1 && set PY=py
if not defined PY where python >nul 2>&1 && set PY=python
if not defined PY (
  echo.
  echo ERRO: Python nao encontrado. Instale em python.org marcando "Add Python to PATH".
  goto erro
)

rem 3) Ambiente do PropSec (.venv)
if not exist .venv\Scripts\python.exe (
  echo Primeira execucao: criando o ambiente...
  %PY% -m venv .venv || goto erro
)
echo Conferindo as bibliotecas...
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 echo AVISO: nao consegui atualizar as bibliotecas (sem internet?). Tentando abrir assim mesmo.

rem 4) Banco de dados e referencias
.venv\Scripts\python propsec.py semear || goto erro

rem 5) Painel (abre o navegador sozinho quando estiver pronto)
.venv\Scripts\python propsec.py servidor
if errorlevel 1 goto erro
goto fim

:erro
echo.
echo ============================================
echo  O painel NAO abriu. Tire um print desta janela
echo  e mande para o Claude.
echo ============================================
pause
:fim
