"""Nota (0-100) de um perfil e estimativa de views nos stories.

Ninguém de fora vê as views dos stories, então a nota usa sinais públicos
que costumam andar junto com elas. Os pesos começam com valores padrão e são
recalibrados pelo módulo `aprendizado` conforme vocês registram resultados
(views reais informadas, fechamentos, notas manuais).
"""
from __future__ import annotations

import json

from . import db

# Modelo v2 ("volume"): o que mais pesa é o perfil ter o ESTILO das fechadas e estar numa
# faixa de seguidores boa. Reels/engajamento ajudam, mas não são obrigatórios — o nicho vive
# de volume e quase toda "blogueira" compatível é oportunidade.
MODELO_VERSAO = 3
PESOS_PADRAO = {
    "estilo": 4.0,            # compatível com o estilo das referências (avaliação do agente, 0–1)
    "faixa": 2.0,             # seguidores: ideal 3.500–15.000; acima de 30.000 não interessa
    "perfil_blogueira": 1.5,  # se apresenta como blogueira/criadora, aceita parceria, tem contato
    "stories_ativos": 1.0,    # posta stories
    "alcance_reels": 1.0,     # mediana de views dos reels ÷ seguidores (bônus, não obrigatório)
    "engajamento": 0.8,       # (curtidas + comentários) ÷ seguidores
    "comentarios": 0.8,       # comentários de gente real
    "regiao": 0.5,            # região prioritária
    "constancia": 0.2,        # posts por semana (quase não importa)
}

NOMES = {
    "estilo": "Estilo das fechadas",
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
    "faixa_min": 1000,            # abaixo disso: fora
    "faixa_ideal_min": 3500,      # de faixa_ideal_min a faixa_max: nota cheia
    "faixa_max": 15000,
    "faixa_especial_max": 30000,  # de faixa_max até aqui vale menos; acima: o usuário não fecha
    "ufs_prioritarias": ["MA"],
    "valor_desconhecido": 0.5,    # sinal não medido conta como neutro (modo volume)
    "taxa_stories_base": 0.10,    # calibrada pelo aprendizado
    "penalidade_fora_faixa": 0.3, # abaixo de faixa_min ou acima de faixa_especial_max
    "penalidade_comercial": 0.5,  # perfil 100% comercial perde metade da nota
}


def _num(v):
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def carregar(con):
    versao = db.get_config(con, "modelo_versao")
    if versao != MODELO_VERSAO:
        # modelo mudou: faixas voltam ao padrão novo; mantém o aprendido de stories e UFs.
        antigos = db.get_config(con, "parametros") or {}
        manter = {k: antigos[k] for k in ("taxa_stories_base", "ufs_prioritarias") if k in antigos}
        db.set_config(con, "parametros", manter)
        if not versao or versao < 2:  # pesos do modelo v1 não servem; de v2 em diante são mantidos
            db.set_config(con, "pesos", dict(PESOS_PADRAO))
        db.set_config(con, "modelo_versao", MODELO_VERSAO)
    pesos = {**PESOS_PADRAO, **(db.get_config(con, "pesos") or {})}
    pesos = {k: v for k, v in pesos.items() if k in PESOS_PADRAO}
    cfg = {**CONFIG_PADRAO, **(db.get_config(con, "parametros") or {})}
    return pesos, cfg


def componentes(p, cfg) -> dict[str, float | None]:
    """Cada componente vai de 0 a 1; None = não medido."""
    seg = _num(p["seguidores"])
    c: dict[str, float | None] = {k: None for k in PESOS_PADRAO}

    est = _num(p["estilo_blogueira"])
    if est is not None:
        c["estilo"] = max(0.0, min(1.0, est))

    if seg:
        lo, ideal, hi, esp = cfg["faixa_min"], cfg["faixa_ideal_min"], cfg["faixa_max"], cfg["faixa_especial_max"]
        if seg < lo:
            c["faixa"] = 0.0
        elif seg < ideal:  # sobe de 0.5 (no mínimo) até 1.0 (no ideal)
            c["faixa"] = 0.5 + 0.5 * (seg - lo) / max(ideal - lo, 1)
        elif seg <= hi:
            c["faixa"] = 1.0
        elif seg <= esp:  # cai de 0.7 até 0.3 entre faixa_max e faixa_especial_max
            c["faixa"] = 0.7 - 0.4 * (seg - hi) / max(esp - hi, 1)
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
    texto = " ".join(str(p[k] or "") for k in ("bio", "tipo_conteudo")).lower()
    if any(t in texto for t in ("blogueir", "criador de conte", "influenc", "parceria", "publi")):
        sinais.append(1.0)
    # "faz publi" e "marca lojas" NÃO somam: perfil cheio de marcas costuma não fechar
    # (o excesso entra como penalidade de perfil comercial em calcular()).
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
        mult *= cfg["penalidade_fora_faixa"]
        motivos.append(f"⚠ fora da faixa ({int(seg):,} seguidores)".replace(",", "."))
    com = _num(p["perfil_comercial"])
    if com is not None and com > 0:
        mult *= 1 - cfg["penalidade_comercial"] * min(com, 1.0)
        if com >= 0.5:
            motivos.append("⚠ perfil comercial (muitas marcas ou dona de negócio)")

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
