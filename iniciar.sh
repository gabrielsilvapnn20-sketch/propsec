#!/usr/bin/env bash
cd "$(dirname "$0")"
# Fecha um painel antigo que ainda esteja rodando na porta 8000
command -v lsof >/dev/null && lsof -ti tcp:8000 -sTCP:LISTEN | xargs -r kill 2>/dev/null
[ -d .venv ] || { echo "Primeira execução: instalando..."; python3 -m venv .venv; }
.venv/bin/pip install -q -r requirements.txt && .venv/bin/python propsec.py semear
( sleep 2; open http://localhost:8000 2>/dev/null || xdg-open http://localhost:8000 2>/dev/null ) &
.venv/bin/python propsec.py servidor
