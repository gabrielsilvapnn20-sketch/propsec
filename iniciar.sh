#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Primeira execução: instalando..."
  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python propsec.py semear
fi
( sleep 2; open http://localhost:8000 2>/dev/null || xdg-open http://localhost:8000 2>/dev/null ) &
.venv/bin/python propsec.py servidor
