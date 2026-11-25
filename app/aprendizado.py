"""Aprendizado: ajusta pesos e a estimativa de stories com base nos resultados reais.

Sinais usados como "verdade" (do mais forte para o mais fraco):
  1. lucro do dia da parceria (R$) ou nível do resultado (alto/médio/baixo)
  2. views reais de stories informadas pela influenciadora (÷ seguidores)
  3. sua nota manual de qualidade do perfil (1 a 5)
  4. referência: perfil que vocês fecharam ou gostaram = bom
  5. status: fechado/negociando = bom, descartado por você = ruim

Importante: "não respondeu" e "recusou" NÃO contam como perfil ruim — o perfil
pode ser ótimo e só não ter aceitado. Isso entra só nas taxas de resposta.
"""
from __future__ import annotations

import statistics

from . import db, scoring

MIN_AMOSTRAS = 6


NIVEL_VALOR = {"alto": 1.0, "medio": 0.65, "baixo": 0.25}


def _rotulo(p):
    seg = p["seguidores"] or 0
    if p["lucro_dia"]:
        return ("lucro", p["lucro_dia"])
    if p["resultado_nivel"] in NIVEL_VALOR:
        return ("nivel", NIVEL_VALOR[p["resultado_nivel"]])
    if p["story_views_real"] and seg:
        return ("stories", p["story_views_real"] / seg)
    if p["qualidade_manual"]:
        return ("manual", (p["qualidade_manual"] - 1) / 4)
    if p["referencia"] in ("fechado", "gostamos"):
        return ("referencia", 1.0)
    if p["status"] in ("fechado", "negociando"):
        return ("status", 0.9)
    # Tudo que passou pela sua aprovação continua sendo "perfil bom", mesmo que depois
    # não tenha respondido ou recusado (recusar não torna o perfil ruim).
    if p["status"] in ("aprovado", "contatado", "respondeu", "recusou", "sem_resposta"):
        return ("status", 0.7)
    if p["status"] == "descartado":
        return ("status", 0.1)
    return None


def _pearson(xs, ys):
    if len(xs) < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def _normalizar_stories(rotulados):
    """Converte lucro (R$) e taxa de stories (views÷seguidores) em 0..1 pela posição (rank)."""
    for tipo in ("stories", "lucro"):
        vals = sorted(v for fonte, v, _ in rotulados if fonte == tipo)
        out = []
        for fonte, v, p in rotulados:
            if fonte == tipo:
                rank = sum(1 for x in vals if x <= v) / len(vals) if len(vals) > 1 else 0.8
                out.append((fonte, rank, p))
            else:
                out.append((fonte, v, p))
        rotulados = out
    return rotulados


def recalibrar(con, aplicar=True):
    pesos, cfg = scoring.carregar(con)
    perfis = con.execute("SELECT * FROM perfis").fetchall()

    rotulados = []
    for p in perfis:
        r = _rotulo(p)
        if r:
            rotulados.append((r[0], r[1], p))
    rotulados = _normalizar_stories(rotulados)

    relatorio = {"amostras": len(rotulados), "componentes": {}, "mudou": False}

    # 1) pesos: correlação de cada componente com o rótulo
    novos = dict(pesos)
    tem_contraste = len({round(v, 2) for _, v, _ in rotulados}) > 1
    for k in scoring.PESOS_PADRAO:
        xs, ys = [], []
        for _, y, p in rotulados:
            comp = scoring.componentes(p, cfg)
            if comp[k] is not None:
                xs.append(comp[k])
                ys.append(y)
        corr = _pearson(xs, ys) if tem_contraste else None
        info = {"n": len(xs), "correlacao": None if corr is None else round(corr, 2),
                "peso_antes": round(pesos[k], 2), "peso_depois": round(pesos[k], 2)}
        if corr is not None and len(xs) >= MIN_AMOSTRAS:
            alvo = scoring.PESOS_PADRAO[k] * (1 + 2 * max(-0.45, min(0.8, corr)))
            novo = round(max(0.1, 0.7 * pesos[k] + 0.3 * alvo), 3)
            novos[k] = novo
            info["peso_depois"] = round(novo, 2)
        relatorio["componentes"][k] = info

    # Médias de referência: como são, em média, os perfis bons conhecidos
    bons = [p for f, y, p in rotulados if y >= 0.7]
    if bons:
        def med(campo):
            vals = [p[campo] for p in bons if p[campo] is not None]
            return round(statistics.median(vals), 1) if vals else None
        relatorio["perfil_tipico_bom"] = {
            "n": len(bons), "seguidores": med("seguidores"),
            "media_views_reels": med("media_views_reels"),
            "media_curtidas": med("media_curtidas"),
            "media_comentarios": med("media_comentarios"),
            "posts_por_semana": med("posts_por_semana"),
        }

    # 2) estimativa de stories: calibra a taxa base com as views reais
    fatores = []
    for p in perfis:
        if p["story_views_real"] and p["seguidores"]:
            comp = scoring.componentes(p, cfg)
            sinais = [comp[k] for k in ("alcance_reels", "engajamento", "stories_ativos", "comentarios")
                      if comp.get(k) is not None]
            q = sum(sinais) / len(sinais) if sinais else 0.4
            fatores.append(p["story_views_real"] / (p["seguidores"] * (0.5 + q)))
    novo_cfg = dict(cfg)
    if len(fatores) >= 3:
        novo_cfg["taxa_stories_base"] = round(statistics.median(fatores), 4)
    relatorio["stories"] = {"amostras": len(fatores), "taxa_antes": cfg["taxa_stories_base"],
                            "taxa_depois": novo_cfg["taxa_stories_base"]}

    relatorio["mudou"] = novos != pesos or novo_cfg != cfg
    if aplicar and relatorio["mudou"]:
        historico = db.get_config(con, "historico_pesos", [])
        historico.append({"em": db.agora(), "pesos": pesos, "taxa_stories_base": cfg["taxa_stories_base"]})
        db.set_config(con, "historico_pesos", historico[-30:])
        db.set_config(con, "pesos", novos)
        db.set_config(con, "modelo_versao", scoring.MODELO_VERSAO)
        params = db.get_config(con, "parametros", {}) or {}
        params["taxa_stories_base"] = novo_cfg["taxa_stories_base"]
        db.set_config(con, "parametros", params)
        scoring.rescore_todos(con)
    return relatorio


def desempenho_fontes(con):
    """Rendimento de cada origem (hashtag, cidade, similar de @x...)."""
    rows = con.execute(
        """
        SELECT COALESCE(origem,'?') AS origem, COALESCE(origem_detalhe,'') AS detalhe,
               COUNT(*) AS perfis,
               ROUND(AVG(score),1) AS score_medio,
               SUM(score >= 60) AS bons,
               SUM(status IN ('contatado','respondeu','negociando','fechado','recusou','sem_resposta')) AS contatados,
               SUM(status IN ('respondeu','negociando','fechado','recusou')) AS responderam,
               SUM(status = 'fechado') AS fechados,
               SUM(status = 'descartado') AS descartados,
               SUM(status NOT IN ('novo','descartado','ignorado')) AS aceitos,
               SUM(status = 'ignorado') AS ignorados
        FROM perfis WHERE referencia IS NULL
        GROUP BY 1, 2 ORDER BY bons DESC, score_medio DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def taxas_por(con, campo):
    if campo not in ("cidade", "uf", "origem", "publicos"):
        raise ValueError(campo)
    rows = con.execute(
        f"""
        SELECT COALESCE({campo},'?') AS chave, COUNT(*) AS contatados,
               SUM(status IN ('respondeu','negociando','fechado','recusou')) AS responderam,
               SUM(status = 'fechado') AS fechados
        FROM perfis WHERE status IN ('contatado','respondeu','negociando','fechado','recusou','sem_resposta')
          AND referencia IS NULL AND COALESCE(origem,'') != 'manual'
        GROUP BY 1 ORDER BY contatados DESC
        """
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["taxa_resposta"] = round(100 * d["responderam"] / d["contatados"]) if d["contatados"] else 0
        d["taxa_fechamento"] = round(100 * d["fechados"] / d["contatados"]) if d["contatados"] else 0
        out.append(d)
    return out


RECALIBRAR_A_CADA = 5  # novas decisões suas (aprovar, descartar, resultado) até reaprender sozinho


def registrar_decisao(con):
    """Conta suas decisões e reaprende os pesos automaticamente a cada RECALIBRAR_A_CADA."""
    n = (db.get_config(con, "decisoes_desde_recalibracao", 0) or 0) + 1
    if n >= RECALIBRAR_A_CADA:
        db.backup()
        recalibrar(con, aplicar=True)
        n = 0
        db.set_config(con, "ultima_recalibracao", db.agora())
    db.set_config(con, "decisoes_desde_recalibracao", n)
