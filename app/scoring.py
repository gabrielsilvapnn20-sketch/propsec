"""Nota (0-100) de um perfil e estimativa de views nos stories.

Ninguém de fora vê as views dos stories, então a nota usa sinais públicos
que costumam andar junto com elas. Os pesos começam com valores padrão e são
recalibrados pelo módulo `aprendizado` conforme vocês registram resultados
(views reais informadas, fechamentos, notas manuais).
"""
from __future__ import annotations

import json

from . import db

PESOS_PADRAO = {
    "faixa": 1.0,             # está na faixa de seguidores que vocês buscam
    "alcance_reels": 3.0,     # views médias dos reels ÷ seguidores (melhor proxy de stories)
    "engajamento": 2.0,       # (curtidas + comentários) ÷ seguidores
    "comentarios": 1.5,       # volume e autenticidade dos comentários
    "stories_ativos": 1.5,    # posta stories com frequência
    "constancia": 1.0,        # posts por semana
    "perfil_blogueira": 1.0,  # já faz publi, marca lojas, tem contato na bio
    "regiao": 0.5,            # está numa região prioritária
}

NOMES = {
    "faixa": "Faixa de seguidores",
    "alcance_reels": "Alcance dos reels",
    "engajamento": "Engajamento",
    "comentarios": "Comentários reais",
    "stories_ativos": "Stories ativos",
    "constancia": "Constância",
    "perfil_blogueira": "Perfil de blogueira",
    "regiao": "Região prioritária",
}

CONFIG_PADRAO = {
    "faixa_min": 1500,
    "faixa_max": 10000,
    "faixa_especial_max": 20000,
    "ufs_prioritarias": ["MA"],
    "valor_desconhecido": 0.4,   # quanto vale um sinal que o agente não conseguiu medir
    "taxa_stories_base": 0.10,   # calibrada pelo aprendizado
}


def _num(v):
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def carregar(con):
    pesos = {**PESOS_PADRAO, **(db.get_config(con, "pesos") or {})}
    cfg = {**CONFIG_PADRAO, **(db.get_config(con, "parametros") or {})}
    return pesos, cfg


def componentes(p, cfg) -> dict[str, float | None]:
    """Cada componente vai de 0 a 1; None = não medido."""
    seg = _num(p["seguidores"])
    c: dict[str, float | None] = {k: None for k in PESOS_PADRAO}

    if seg:
        lo, hi, esp = cfg["faixa_min"], cfg["faixa_max"], cfg["faixa_especial_max"]
        if lo <= seg <= hi:
            c["faixa"] = 1.0
        elif hi < seg <= (hi + esp) / 2:
            c["faixa"] = 0.7
        elif seg <= esp and seg > hi:
            c["faixa"] = 0.45
        elif lo * 0.66 <= seg < lo:
            c["faixa"] = 0.5
        else:
            c["faixa"] = 0.0

        views = _num(p["media_views_reels"])
        if views is not None:
            c["alcance_reels"] = min(1.0, (views / seg) / 0.8)

        curt, com = _num(p["media_curtidas"]), _num(p["media_comentarios"])
        if curt is not None or com is not None:
            c["engajamento"] = min(1.0, (((curt or 0) + (com or 0)) / seg) / 0.08)

        reais = _num(p["comentarios_reais"])
        partes = []
        if com is not None:
            partes.append(min(1.0, (com / seg) / 0.006))
        if reais is not None:
            partes.append(max(0.0, min(1.0, reais)))
        if partes:
            c["comentarios"] = sum(partes) / len(partes)

    if p["stories_ativos"] is not None:
        c["stories_ativos"] = 1.0 if int(p["stories_ativos"]) else 0.0

    ppw = _num(p["posts_por_semana"])
    if ppw is not None:
        c["constancia"] = min(1.0, ppw / 4)

    sinais = []
    if p["faz_publi"] is not None:
        sinais.append(float(int(p["faz_publi"])))
    if p["marca_lojas"] is not None:
        sinais.append(float(int(p["marca_lojas"])))
    if p["contato"] or p["link_bio"]:
        sinais.append(1.0)
    if sinais:
        c["perfil_blogueira"] = sum(sinais) / len(sinais)

    if p["uf"]:
        c["regiao"] = 1.0 if p["uf"].upper() in [u.upper() for u in cfg["ufs_prioritarias"]] else 0.5
    return c


def calcular(p, pesos, cfg):
    comp = componentes(p, cfg)
    desconhecido = cfg["valor_desconhecido"]
    total_w = sum(pesos.values()) or 1.0
    soma = 0.0
    medido_w = 0.0
    for k, w in pesos.items():
        v = comp.get(k)
        if v is None:
            soma += w * desconhecido
        else:
            soma += w * v
            medido_w += w
    base = soma / total_w

    motivos = []
    mult = 1.0
    seg = _num(p["seguidores"])
    if p["suspeita_compra"] and int(p["suspeita_compra"]):
        mult *= 0.4
        motivos.append("⚠ suspeita de seguidores comprados")
    if seg is not None and comp["faixa"] == 0.0:
        mult *= 0.3
        motivos.append(f"⚠ fora da faixa ({int(seg):,} seguidores)".replace(",", "."))

    score = round(100 * base * mult, 1)

    fortes = sorted(((k, v) for k, v in comp.items() if v is not None and v >= 0.7),
                    key=lambda kv: -pesos[kv[0]] * kv[1])
    fracos = sorted(((k, v) for k, v in comp.items() if v is not None and v < 0.35),
                    key=lambda kv: -pesos[kv[0]])
    faltando = [k for k, v in comp.items() if v is None and pesos[k] >= 1.0]
    if fortes:
        motivos.append("✓ " + ", ".join(NOMES[k] for k, _ in fortes[:4]))
    if fracos:
        motivos.append("✗ " + ", ".join(NOMES[k] for k, _ in fracos[:3]))
    if faltando:
        motivos.append("? sem dado: " + ", ".join(NOMES[k] for k in faltando))

    confianca = medido_w / total_w
    return score, motivos, comp, confianca


def estimar_stories(p, comp, cfg):
    seg = _num(p["seguidores"])
    if not seg:
        return None
    sinais = [comp[k] for k in ("alcance_reels", "engajamento", "stories_ativos", "comentarios")
              if comp.get(k) is not None]
    qualidade = sum(sinais) / len(sinais) if sinais else 0.4
    return round(seg * cfg["taxa_stories_base"] * (0.5 + qualidade))


def rescore_perfil(con, perfil_id, pesos=None, cfg=None):
    if pesos is None or cfg is None:
        pesos, cfg = carregar(con)
    p = con.execute("SELECT * FROM perfis WHERE id=?", (perfil_id,)).fetchone()
    if not p:
        return
    score, motivos, comp, conf = calcular(p, pesos, cfg)
    est = estimar_stories(p, comp, cfg)
    motivos.append(f"dados medidos: {round(conf * 100)}%")
    con.execute(
        "UPDATE perfis SET score=?, score_motivos=?, story_views_estimado=? WHERE id=?",
        (score, json.dumps(motivos, ensure_ascii=False), est, perfil_id),
    )


def rescore_todos(con):
    pesos, cfg = carregar(con)
    ids = [r["id"] for r in con.execute("SELECT id FROM perfis")]
    for pid in ids:
        rescore_perfil(con, pid, pesos, cfg)
    con.commit()
    return len(ids)
