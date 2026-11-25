"""Controle de segurança da conta de prospecção.

O agente chama `python propsec.py liberar @perfil` ANTES de abrir cada perfil.
Este módulo decide se pode (e espera o tempo necessário) ou manda parar:
  - botão de parar no painel / pausa automática após alerta
  - horário permitido
  - limites por sessão, por hora e por dia
  - intervalo aleatório entre perfis + pausas longas periódicas
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timedelta

from . import db

PADRAO = {
    "intervalo_min": 30,          # segundos entre um perfil e outro (sorteado entre min e max)
    "intervalo_max": 90,
    "pausa_longa_a_cada": 8,      # a cada N perfis, uma pausa maior
    "pausa_longa_min": 180,
    "pausa_longa_max": 420,
    "perfis_por_sessao": 30,
    "perfis_por_hora": 25,
    "perfis_por_dia": 60,
    "horario_inicio": "08:00",
    "horario_fim": "22:00",
    "horas_pausa_apos_alerta": 24,
}
ESPERA_MAXIMA = 480  # nunca dorme mais que 8 min numa chamada (limite do terminal do agente)

SCHEMA = """
CREATE TABLE IF NOT EXISTS visitas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT, sessao_id INTEGER, em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_visitas_em ON visitas(em);
CREATE TABLE IF NOT EXISTS alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL, texto TEXT, em TEXT NOT NULL
);
"""


def conectar():
    con = db.conectar()
    con.executescript(SCHEMA)
    return con


def config(con):
    return {**PADRAO, **(db.get_config(con, "seguranca") or {})}


def estado(con):
    return db.get_config(con, "seguranca_estado") or {"pausado": False}


def _sessao_atual(con):
    r = con.execute("SELECT id FROM sessoes WHERE fim IS NULL ORDER BY id DESC LIMIT 1").fetchone()
    return r["id"] if r else None


def contagens(con):
    agora = datetime.now()
    um_h = (agora - timedelta(hours=1)).isoformat(timespec="seconds")
    hoje = agora.date().isoformat()
    sid = _sessao_atual(con)
    c = {
        "hora": con.execute("SELECT COUNT(*) FROM visitas WHERE em >= ?", (um_h,)).fetchone()[0],
        "dia": con.execute("SELECT COUNT(*) FROM visitas WHERE em LIKE ?", (hoje + "%",)).fetchone()[0],
        "sessao": con.execute("SELECT COUNT(*) FROM visitas WHERE sessao_id = ?", (sid,)).fetchone()[0] if sid else 0,
        "sessao_id": sid,
    }
    ult = con.execute("SELECT em FROM visitas ORDER BY id DESC LIMIT 1").fetchone()
    c["ultima"] = ult["em"] if ult else None
    return c


def pausar(con, motivo, horas=None, tipo="manual"):
    st = {"pausado": True, "motivo": motivo, "em": db.agora()}
    if horas:
        st["ate"] = (datetime.now() + timedelta(hours=horas)).isoformat(timespec="seconds")
    db.set_config(con, "seguranca_estado", st)
    con.execute("INSERT INTO alertas(tipo, texto, em) VALUES(?,?,?)", (tipo, motivo, db.agora()))
    con.commit()


def retomar(con):
    db.set_config(con, "seguranca_estado", {"pausado": False})
    con.execute("INSERT INTO alertas(tipo, texto, em) VALUES('retomado', 'liberado pelo usuário', ?)", (db.agora(),))
    con.commit()


def _no_horario(cfg, agora):
    hm = agora.strftime("%H:%M")
    return cfg["horario_inicio"] <= hm <= cfg["horario_fim"]


def verificar(con):
    """Retorna (pode, motivo, espera_segundos) sem registrar nada."""
    cfg, st, c = config(con), estado(con), contagens(con)
    agora = datetime.now()
    if st.get("pausado"):
        if st.get("ate") and agora.isoformat() >= st["ate"]:
            retomar(con)
        else:
            ate = f" até {st['ate'].replace('T', ' ')[:16]}" if st.get("ate") else ""
            return False, f"PAUSADO{ate}: {st.get('motivo', '')}", 0
    if not _no_horario(cfg, agora):
        return False, f"fora do horário permitido ({cfg['horario_inicio']}–{cfg['horario_fim']})", 0
    if c["dia"] >= cfg["perfis_por_dia"]:
        return False, f"limite diário atingido ({c['dia']}/{cfg['perfis_por_dia']})", 0
    if c["sessao_id"] and c["sessao"] >= cfg["perfis_por_sessao"]:
        return False, f"limite da sessão atingido ({c['sessao']}/{cfg['perfis_por_sessao']})", 0
    if c["hora"] >= cfg["perfis_por_hora"]:
        return False, f"limite por hora atingido ({c['hora']}/{cfg['perfis_por_hora']}) — tente mais tarde", 0

    espera = 0
    if c["ultima"]:
        desde = (agora - datetime.fromisoformat(c["ultima"])).total_seconds()
        alvo = random.uniform(cfg["intervalo_min"], cfg["intervalo_max"])
        if c["sessao"] and c["sessao"] % cfg["pausa_longa_a_cada"] == 0:
            alvo = random.uniform(cfg["pausa_longa_min"], cfg["pausa_longa_max"])
        espera = max(0, alvo - desde)
    return True, "ok", min(espera, ESPERA_MAXIMA)


def liberar(con, username, dormir=True):
    pode, motivo, espera = verificar(con)
    if not pode:
        return False, motivo
    if espera and dormir:
        time.sleep(espera)
        pode, motivo, _ = verificar(con)  # o usuário pode ter apertado PARAR durante a espera
        if not pode:
            return False, motivo
    con.execute("INSERT INTO visitas(username, sessao_id, em) VALUES(?,?,?)",
                (db.normalizar_username(username), _sessao_atual(con), db.agora()))
    con.commit()
    c = contagens(con)
    cfg = config(con)
    return True, (f"LIBERADO @{db.normalizar_username(username)} (esperou {round(espera)}s) — "
                  f"sessão {c['sessao']}/{cfg['perfis_por_sessao']}, hora {c['hora']}/{cfg['perfis_por_hora']}, "
                  f"dia {c['dia']}/{cfg['perfis_por_dia']}")


def risco(con):
    """0–100: quão perto dos limites a conta está agora."""
    cfg, c = config(con), contagens(con)
    return round(100 * max(c["hora"] / cfg["perfis_por_hora"], c["dia"] / cfg["perfis_por_dia"]))
