"""Banco de dados SQLite do PropSec (um arquivo local em dados/propsec.db)."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_DB = Path(os.environ.get("PROPSEC_DB", RAIZ / "dados" / "propsec.db"))

# Funil de status de um perfil, na ordem da operação.
STATUS = {
    "novo": "Novo (agente achou)",
    "aprovado": "Aprovado p/ contato",
    "descartado": "Descartado (por vocês)",
    "ignorado": "Ignorado pelo agente",
    "contatado": "Mensagem enviada",
    "respondeu": "Respondeu",
    "negociando": "Negociando",
    "fechado": "Fechou parceria",
    "recusou": "Recusou",
    "sem_resposta": "Sem resposta",
}
STATUS_CONTATADOS = ("contatado", "respondeu", "negociando", "fechado", "recusou", "sem_resposta")
STATUS_RESPONDERAM = ("respondeu", "negociando", "fechado", "recusou")

# Campos numéricos/textuais que o agente (ou você) pode enviar para um perfil.
CAMPOS_PERFIL = [
    "nome", "bio", "cidade", "uf", "regiao",
    "seguidores", "seguindo", "posts",
    "media_views_reels", "media_curtidas", "media_comentarios",
    "comentarios_reais", "posts_por_semana", "stories_ativos",
    "faz_publi", "marca_lojas", "contato", "link_bio",
    "publicos", "hashtags", "tipo_conteudo", "suspeita_compra",
    "observacoes", "origem", "origem_detalhe",
    "story_views_real", "story_views_informado_em", "valor_parceria",
    "qualidade_manual", "referencia", "lucro_dia", "resultado_nivel", "estilo_blogueira", "perfil_comercial",
    "stories_qtd", "stories_publi",
]

# Colunas adicionadas depois da primeira versão (migração automática)
COLUNAS_NOVAS = {"lucro_dia": "REAL", "resultado_nivel": "TEXT", "estilo_blogueira": "REAL",
                 "perfil_comercial": "REAL", "stories_qtd": "INTEGER", "stories_publi": "REAL"}
NIVEIS_RESULTADO = {"alto": "Alto (R$ 1.000+/dia)", "medio": "Médio (R$ 200–500/dia)", "baixo": "Baixo"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS perfis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    nome TEXT, bio TEXT, cidade TEXT, uf TEXT, regiao TEXT,
    seguidores INTEGER, seguindo INTEGER, posts INTEGER,
    media_views_reels REAL, media_curtidas REAL, media_comentarios REAL,
    comentarios_reais REAL,          -- 0 a 1: fração de comentários de gente real
    posts_por_semana REAL,
    stories_ativos INTEGER,          -- 1 = posta stories com frequência
    faz_publi INTEGER,               -- 1 = já faz publi/permuta
    marca_lojas INTEGER,             -- 1 = marca lojas/negócios locais
    contato TEXT, link_bio TEXT,
    publicos TEXT,                   -- etiquetas separadas por vírgula
    hashtags TEXT, tipo_conteudo TEXT,
    suspeita_compra INTEGER,         -- 1 = parece ter seguidores comprados
    observacoes TEXT,
    origem TEXT, origem_detalhe TEXT,
    score REAL, score_motivos TEXT, story_views_estimado REAL,
    status TEXT NOT NULL DEFAULT 'novo',
    story_views_real REAL, story_views_informado_em TEXT,
    valor_parceria REAL,
    qualidade_manual INTEGER,        -- 1..5: sua nota do perfil (independe de fechar)
    referencia TEXT,                 -- fechado / gostamos / NULL
    lucro_dia REAL,                  -- lucro em R$ no dia da parceria
    resultado_nivel TEXT,            -- alto / medio / baixo
    estilo_blogueira REAL,           -- 0 a 1: quanto lembra o estilo das fechadas (avaliação do agente)
    perfil_comercial REAL,           -- 0 a 1: quanto o perfil é vitrine de marcas / dona de negócio
    stories_qtd INTEGER,             -- quantos stories ela tinha no ar quando o agente viu (24 h)
    stories_publi REAL,              -- 0 a 1: fração desses stories que era divulgação de loja/marca
    criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL, verificado_em TEXT
);
CREATE INDEX IF NOT EXISTS idx_perfis_status ON perfis(status);
CREATE INDEX IF NOT EXISTS idx_perfis_score ON perfis(score);

CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    perfil_id INTEGER NOT NULL REFERENCES perfis(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL, de TEXT, para TEXT, nota TEXT,
    criado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_eventos_perfil ON eventos(perfil_id);

CREATE TABLE IF NOT EXISTS fontes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,              -- hashtag / local / similar / busca / comentarios
    valor TEXT NOT NULL,
    ativa INTEGER NOT NULL DEFAULT 1,
    vezes_explorada INTEGER NOT NULL DEFAULT 0,
    perfis_vistos INTEGER NOT NULL DEFAULT 0,
    ultima_vez TEXT,
    nota TEXT,
    UNIQUE(tipo, valor)
);

CREATE TABLE IF NOT EXISTS sessoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inicio TEXT NOT NULL, fim TEXT,
    perfis_visitados INTEGER DEFAULT 0, perfis_salvos INTEGER DEFAULT 0,
    nota TEXT
);

CREATE TABLE IF NOT EXISTS config (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def conectar() -> sqlite3.Connection:
    CAMINHO_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(CAMINHO_DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    existentes = {r["name"] for r in con.execute("PRAGMA table_info(perfis)")}
    for col, tipo in COLUNAS_NOVAS.items():
        if col not in existentes:
            con.execute(f"ALTER TABLE perfis ADD COLUMN {col} {tipo}")
    return con


def normalizar_username(u: str) -> str:
    u = (u or "").strip()
    for p in ("https://", "http://", "www.", "instagram.com/"):
        if u.lower().startswith(p):
            u = u[len(p):]
    u = u.split("?")[0].strip("/").lstrip("@").lower()
    return u


def get_config(con, chave, padrao=None):
    row = con.execute("SELECT valor FROM config WHERE chave=?", (chave,)).fetchone()
    return json.loads(row["valor"]) if row else padrao


def set_config(con, chave, valor):
    con.execute(
        "INSERT INTO config(chave, valor) VALUES(?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
        (chave, json.dumps(valor, ensure_ascii=False)),
    )
    con.commit()


def buscar_perfil(con, username):
    return con.execute(
        "SELECT * FROM perfis WHERE username=?", (normalizar_username(username),)
    ).fetchone()


def registrar_evento(con, perfil_id, tipo, de=None, para=None, nota=None):
    con.execute(
        "INSERT INTO eventos(perfil_id, tipo, de, para, nota, criado_em) VALUES(?,?,?,?,?,?)",
        (perfil_id, tipo, de, para, nota, agora()),
    )


def _limpar(dados: dict) -> dict:
    limpo = {}
    for k in CAMPOS_PERFIL:
        if k not in dados:
            continue
        v = dados[k]
        if isinstance(v, bool):
            v = int(v)
        if isinstance(v, (list, tuple)):
            v = ", ".join(str(x).strip() for x in v if str(x).strip())
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                v = None
        limpo[k] = v
    if limpo.get("uf"):
        limpo["uf"] = limpo["uf"].upper()[:2]
    if limpo.get("origem_detalhe") and limpo.get("origem") in TIPOS_FONTE_PERFIL:
        limpo["origem_detalhe"] = normalizar_username(limpo["origem_detalhe"])
    return limpo


def salvar_perfil(con, dados: dict, status: str | None = None) -> tuple[int, bool]:
    """Cria ou atualiza um perfil pelo username. Retorna (id, criado?).

    Campos ausentes/vazios não apagam dados já existentes.
    """
    from . import scoring  # import tardio para evitar ciclo

    username = normalizar_username(dados.get("username", ""))
    if not username:
        raise ValueError("username obrigatório")
    campos = _limpar(dados)
    existente = buscar_perfil(con, username)
    ts = agora()

    if existente:
        campos = {k: v for k, v in campos.items() if v is not None}
        if campos:
            sets = ", ".join(f"{k}=?" for k in campos)
            con.execute(
                f"UPDATE perfis SET {sets}, atualizado_em=?, verificado_em=? WHERE id=?",
                (*campos.values(), ts, ts, existente["id"]),
            )
        pid, criado = existente["id"], False
        if status and status != existente["status"]:
            mudar_status(con, pid, status, nota="via cadastro")
    else:
        campos["username"] = username
        campos["status"] = status if status in STATUS else "novo"
        campos["criado_em"] = campos["atualizado_em"] = campos["verificado_em"] = ts
        cols = ", ".join(campos)
        qs = ", ".join("?" for _ in campos)
        cur = con.execute(f"INSERT INTO perfis({cols}) VALUES({qs})", tuple(campos.values()))
        pid, criado = cur.lastrowid, True
        registrar_evento(con, pid, "criado", para=campos["status"],
                         nota=f"origem: {campos.get('origem') or '-'} {campos.get('origem_detalhe') or ''}".strip())

    scoring.rescore_perfil(con, pid)
    con.commit()
    return pid, criado


def mudar_status(con, perfil_id, novo, nota=None):
    if novo not in STATUS:
        raise ValueError(f"status inválido: {novo}")
    atual = con.execute("SELECT status FROM perfis WHERE id=?", (perfil_id,)).fetchone()
    if not atual or atual["status"] == novo:
        return
    con.execute("UPDATE perfis SET status=?, atualizado_em=? WHERE id=?", (novo, agora(), perfil_id))
    registrar_evento(con, perfil_id, "status", de=atual["status"], para=novo, nota=nota)
    con.commit()


TIPOS_FONTE_PERFIL = ("sugestoes", "similar", "achado", "pagina_local", "agencia")


def normalizar_fonte(tipo, valor):
    """Fontes que são perfis guardam o @ sem '@' e em minúsculas (igual aos perfis)."""
    valor = (valor or "").strip()
    return normalizar_username(valor) if tipo in TIPOS_FONTE_PERFIL else valor


def corrigir_fontes(con):
    """Junta fontes gravadas como '@perfil' e 'perfil' (versões antigas)."""
    for r in con.execute("SELECT * FROM fontes").fetchall():
        certo = normalizar_fonte(r["tipo"], r["valor"])
        if certo == r["valor"]:
            continue
        alvo = con.execute("SELECT * FROM fontes WHERE tipo=? AND valor=?", (r["tipo"], certo)).fetchone()
        if alvo:
            con.execute("UPDATE fontes SET vezes_explorada=vezes_explorada+?, perfis_vistos=perfis_vistos+?, "
                        "ultima_vez=MAX(COALESCE(ultima_vez,''), COALESCE(?,'')) WHERE id=?",
                        (r["vezes_explorada"], r["perfis_vistos"], r["ultima_vez"], alvo["id"]))
            con.execute("DELETE FROM fontes WHERE id=?", (r["id"],))
        else:
            con.execute("UPDATE fontes SET valor=? WHERE id=?", (certo, r["id"]))
    # o mesmo nos perfis salvos: origem_detalhe '@semente' -> 'semente'
    con.execute("UPDATE perfis SET origem_detalhe=lower(substr(origem_detalhe, 2)) "
                "WHERE origem IN ('sugestoes','similar','achado','pagina_local') AND origem_detalhe LIKE '@%'")
    con.commit()


def registrar_fonte(con, tipo, valor, perfis_vistos=0, nota=None):
    valor = normalizar_fonte(tipo, valor)
    con.execute(
        "INSERT INTO fontes(tipo, valor) VALUES(?, ?) ON CONFLICT(tipo, valor) DO NOTHING",
        (tipo, valor),
    )
    con.execute(
        "UPDATE fontes SET vezes_explorada=vezes_explorada+1, perfis_vistos=perfis_vistos+?, "
        "ultima_vez=?, nota=COALESCE(?, nota) WHERE tipo=? AND valor=?",
        (perfis_vistos, agora(), nota, tipo, valor),
    )
    con.commit()


def backup() -> Path | None:
    if not CAMINHO_DB.exists():
        return None
    destino = CAMINHO_DB.parent / "backups" / f"propsec-{datetime.now():%Y%m%d-%H%M%S}.db"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CAMINHO_DB, destino)
    return destino
