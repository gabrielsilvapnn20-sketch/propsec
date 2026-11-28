#!/usr/bin/env bash
cd "$(dirname "$0")"
command -v lsof >/dev/null && lsof -ti tcp:8000 -sTCP:LISTEN | xargs -r kill 2>/dev/null
[ -x .venv/bin/python ] || { echo "Primeira execução: criando o ambiente..."; python3 -m venv .venv || exit 1; }
.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt || echo "AVISO: não consegui atualizar as bibliotecas."
.venv/bin/python propsec.py semear && .venv/bin/python propsec.py servidor
