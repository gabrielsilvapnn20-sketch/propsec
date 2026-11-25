"""Painel web do PropSec (roda local: python propsec.py servidor)."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import aprendizado, db, scoring, seguranca

AQUI = Path(__file__).resolve().parent
app = FastAPI(title="PropSec")
app.mount("/static", StaticFiles(directory=AQUI / "static"), name="static")
tpl = Jinja2Templates(directory=AQUI / "templates")


def _fmt_int(v):
    if v is None or v == "":
        return "—"
    try:
        return f"{int(round(float(v))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(v)


tpl.env.filters["n"] = _fmt_int
tpl.env.filters["motivos"] = lambda s: json.loads(s) if s else []
tpl.env.globals["STATUS"] = db.STATUS
tpl.env.globals["NOMES"] = scoring.NOMES
tpl.env.globals["NIVEIS"] = db.NIVEIS_RESULTADO


VERSAO = "2026.11.25-c"


def render(request, nome, **ctx):
    try:
        ctx.setdefault("agente", seguranca.ler_atividade(seguranca.conectar()))
    except Exception:
        ctx.setdefault("agente", {"estado": "parado"})
    ctx["versao"] = VERSAO
    return tpl.TemplateResponse(request, nome, ctx)


def _voltar(request, padrao="/"):
    return RedirectResponse(request.headers.get("referer") or padrao, status_code=303)


def _pct(a, b):
    return round(100 * a / b) if b else 0


# ---------------------------------------------------------------- páginas
@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    con = db.conectar()
    # Referências (parcerias antigas) e "já contatados por fora" não entram nas taxas do funil.
    cont = {r["status"]: r["n"] for r in con.execute(
        "SELECT status, COUNT(*) n FROM perfis WHERE referencia IS NULL GROUP BY status")}
    taxa = {r["status"]: r["n"] for r in con.execute(
        "SELECT status, COUNT(*) n FROM perfis WHERE referencia IS NULL AND COALESCE(origem,'') != 'manual' "
        "GROUP BY status")}
    contatados = sum(taxa.get(s, 0) for s in db.STATUS_CONTATADOS)
    responderam = sum(taxa.get(s, 0) for s in db.STATUS_RESPONDERAM)
    fechados = taxa.get("fechado", 0)
    n_refs = con.execute("SELECT COUNT(*) FROM perfis WHERE referencia IS NOT NULL").fetchone()[0]
    ja_contatados = con.execute("SELECT COUNT(*) FROM perfis WHERE referencia IS NULL AND origem='manual' "
                                "AND status='contatado'").fetchone()[0]
    lucro = con.execute("SELECT SUM(lucro_dia) s, COUNT(*) FILTER (WHERE resultado_nivel='alto') a "
                        "FROM perfis WHERE status='fechado'").fetchone()
    views = con.execute("SELECT AVG(story_views_real) a, COUNT(story_views_real) n FROM perfis "
                        "WHERE story_views_real IS NOT NULL").fetchone()
    semana = con.execute("SELECT COUNT(*) FROM perfis WHERE criado_em >= date('now','-7 day') "
                         "AND referencia IS NULL").fetchone()[0]
    kpis = {
        "fila": cont.get("novo", 0), "aprovados": cont.get("aprovado", 0),
        "contatados": contatados, "responderam": responderam, "fechados": fechados,
        "taxa_resposta": _pct(responderam, contatados), "taxa_fechamento": _pct(fechados, contatados),
        "views_media": views["a"], "views_n": views["n"], "semana": semana,
        "lucro_total": lucro["s"], "resultado_alto": lucro["a"],
        "referencias": n_refs, "ja_contatados": ja_contatados,
    }
    funil = [(s, db.STATUS[s], cont.get(s, 0)) for s in db.STATUS]
    top = con.execute("SELECT * FROM perfis WHERE status='novo' ORDER BY score DESC LIMIT 8").fetchall()
    return render(request, "inicio.html", kpis=kpis, funil=funil, top=top,
                  fontes=aprendizado.desempenho_fontes(con)[:8],
                  cidades=aprendizado.taxas_por(con, "cidade")[:8])


@app.get("/fila", response_class=HTMLResponse)
def fila(request: Request, uf: str = "", min_score: float = 0, publico: str = ""):
    con = db.conectar()
    sql = "SELECT * FROM perfis WHERE status='novo' AND score >= ?"
    args: list = [min_score]
    if uf:
        sql += " AND uf = ?"; args.append(uf.upper())
    if publico:
        sql += " AND publicos LIKE ?"; args.append(f"%{publico}%")
    perfis = con.execute(sql + " ORDER BY score DESC LIMIT 200", args).fetchall()
    return render(request, "fila.html", perfis=perfis, uf=uf, min_score=min_score, publico=publico)


@app.get("/perfis", response_class=HTMLResponse)
def lista(request: Request, status: str = "", q: str = "", ordem: str = "score"):
    con = db.conectar()
    sql, args = "SELECT * FROM perfis WHERE 1=1", []
    if status:
        sql += " AND status=?"; args.append(status)
    if q:
        sql += " AND (username LIKE ? OR nome LIKE ? OR cidade LIKE ? OR publicos LIKE ? OR bio LIKE ?)"
        args += [f"%{q}%"] * 5
    ordens = {"score": "score DESC", "recentes": "atualizado_em DESC", "seguidores": "seguidores DESC",
              "views": "COALESCE(story_views_real, story_views_estimado) DESC"}
    perfis = con.execute(f"{sql} ORDER BY {ordens.get(ordem, 'score DESC')} LIMIT 500", args).fetchall()
    return render(request, "perfis.html", perfis=perfis, status=status, q=q, ordem=ordem)


ETAPAS_PIPELINE = ["aprovado", "contatado", "respondeu", "negociando", "fechado", "recusou", "sem_resposta"]


@app.get("/pipeline", response_class=HTMLResponse)
def pipeline(request: Request):
    con = db.conectar()
    colunas = []
    for s in ETAPAS_PIPELINE:
        rows = con.execute("SELECT * FROM perfis WHERE status=? AND referencia IS NULL "
                           "ORDER BY atualizado_em DESC LIMIT 100", (s,)).fetchall()
        colunas.append((s, db.STATUS[s], rows))
    return render(request, "pipeline.html", colunas=colunas, etapas=ETAPAS_PIPELINE)


@app.get("/p/{username}", response_class=HTMLResponse)
def perfil(request: Request, username: str):
    con = db.conectar()
    p = db.buscar_perfil(con, username)
    if not p:
        raise HTTPException(404, "perfil não encontrado")
    pesos, cfg = scoring.carregar(con)
    comp = scoring.componentes(p, cfg)
    eventos = con.execute("SELECT * FROM eventos WHERE perfil_id=? ORDER BY id DESC", (p["id"],)).fetchall()
    return render(request, "perfil.html", p=p, comp=comp, pesos=pesos, eventos=eventos)


@app.get("/referencias", response_class=HTMLResponse)
def referencias(request: Request):
    con = db.conectar()
    refs = con.execute("SELECT * FROM perfis WHERE referencia IS NOT NULL ORDER BY referencia, "
                        "CASE resultado_nivel WHEN 'alto' THEN 0 WHEN 'medio' THEN 1 ELSE 2 END, lucro_dia DESC, username").fetchall()
    return render(request, "referencias.html", refs=refs)


@app.get("/aprendizado", response_class=HTMLResponse)
def pag_aprendizado(request: Request):
    con = db.conectar()
    pesos, cfg = scoring.carregar(con)
    simulacao = aprendizado.recalibrar(con, aplicar=False)
    return render(request, "aprendizado.html", pesos=pesos, cfg=cfg, sim=simulacao,
                  fontes=aprendizado.desempenho_fontes(con),
                  por_origem=aprendizado.taxas_por(con, "origem"),
                  por_cidade=aprendizado.taxas_por(con, "cidade"),
                  historico=list(reversed(db.get_config(con, "historico_pesos", []))))


# ---------------------------------------------------------------- ações
@app.post("/p/{username}/status")
def acao_status(request: Request, username: str, status: str = Form(...), nota: str = Form("")):
    con = db.conectar()
    p = db.buscar_perfil(con, username)
    if not p:
        raise HTTPException(404)
    db.mudar_status(con, p["id"], status, nota=nota or None)
    return _voltar(request)


@app.post("/p/{username}/editar")
async def acao_editar(request: Request, username: str):
    con = db.conectar()
    p = db.buscar_perfil(con, username)
    if not p:
        raise HTTPException(404)
    form = dict(await request.form())
    dados = {"username": username}
    for k, v in form.items():
        if k in db.CAMPOS_PERFIL:
            dados[k] = v
    # permitir apagar valores: campos enviados vazios viram NULL
    vazios = [k for k, v in dados.items() if k != "username" and str(v).strip() == ""]
    if form.get("story_views_real") and str(form["story_views_real"]).strip() and not p["story_views_real"]:
        dados["story_views_informado_em"] = db.agora()
        db.registrar_evento(con, p["id"], "views_stories", para=str(form["story_views_real"]))
    db.salvar_perfil(con, dados)
    for k in vazios:
        con.execute(f"UPDATE perfis SET {k}=NULL WHERE id=?", (p["id"],))
    scoring.rescore_perfil(con, p["id"])
    con.commit()
    return RedirectResponse(f"/p/{p['username']}", status_code=303)


@app.post("/p/{username}/excluir")
def acao_excluir(username: str):
    con = db.conectar()
    con.execute("DELETE FROM perfis WHERE username=?", (db.normalizar_username(username),))
    con.commit()
    return RedirectResponse("/perfis", status_code=303)


@app.post("/novo")
def acao_novo(request: Request, username: str = Form(...), referencia: str = Form(""),
              status: str = Form("novo"), observacoes: str = Form("")):
    con = db.conectar()
    dados = {"username": username, "observacoes": observacoes, "origem": "manual"}
    if referencia:
        dados["referencia"] = referencia
    db.salvar_perfil(con, dados, status=status)
    return _voltar(request)


@app.post("/recalibrar")
def acao_recalibrar():
    con = db.conectar()
    db.backup()
    aprendizado.recalibrar(con, aplicar=True)
    return RedirectResponse("/aprendizado", status_code=303)


@app.post("/config")
async def acao_config(request: Request):
    con = db.conectar()
    form = await request.form()
    params = db.get_config(con, "parametros", {}) or {}
    for k in ("faixa_min", "faixa_ideal_min", "faixa_max", "faixa_especial_max"):
        if form.get(k):
            params[k] = int(form[k])
    if form.get("ufs_prioritarias") is not None:
        params["ufs_prioritarias"] = [u.strip().upper() for u in form["ufs_prioritarias"].split(",") if u.strip()]
    db.set_config(con, "parametros", params)
    pesos = db.get_config(con, "pesos", {}) or {}
    for k in scoring.PESOS_PADRAO:
        if form.get(f"peso_{k}"):
            pesos[k] = float(str(form[f"peso_{k}"]).replace(",", "."))
    db.set_config(con, "pesos", pesos)
    scoring.rescore_todos(con)
    return RedirectResponse("/aprendizado", status_code=303)


@app.post("/pesos/restaurar")
def acao_restaurar():
    con = db.conectar()
    db.set_config(con, "pesos", dict(scoring.PESOS_PADRAO))
    scoring.rescore_todos(con)
    return RedirectResponse("/aprendizado", status_code=303)


# ---------------------------------------------------------------- segurança
@app.get("/seguranca", response_class=HTMLResponse)
def pag_seguranca(request: Request):
    con = seguranca.conectar()
    pode, motivo, _ = seguranca.verificar(con)
    visitas = con.execute("SELECT * FROM visitas ORDER BY id DESC LIMIT 40").fetchall()
    alertas = con.execute("SELECT * FROM alertas ORDER BY id DESC LIMIT 20").fetchall()
    return render(request, "seguranca.html", cfg=seguranca.config(con), st=seguranca.estado(con),
                  c=seguranca.contagens(con), risco=seguranca.risco(con), pode=pode, motivo=motivo,
                  visitas=visitas, alertas=alertas)


@app.post("/seguranca/parar")
def seg_parar():
    seguranca.pausar(seguranca.conectar(), "parado pelo botão do painel")
    return RedirectResponse("/seguranca", status_code=303)


@app.post("/seguranca/retomar")
def seg_retomar():
    seguranca.retomar(seguranca.conectar())
    return RedirectResponse("/seguranca", status_code=303)


@app.post("/seguranca/config")
async def seg_config(request: Request):
    con = seguranca.conectar()
    form = await request.form()
    cfg = db.get_config(con, "seguranca", {}) or {}
    for k, v in seguranca.PADRAO.items():
        val = str(form.get(k, "")).strip()
        if not val:
            continue
        cfg[k] = val if isinstance(v, str) else int(float(val.replace(",", ".")))
    if cfg.get("intervalo_max", 0) < cfg.get("intervalo_min", 0):
        cfg["intervalo_max"] = cfg["intervalo_min"]
    if cfg.get("pausa_longa_max", 0) < cfg.get("pausa_longa_min", 0):
        cfg["pausa_longa_max"] = cfg["pausa_longa_min"]
    db.set_config(con, "seguranca", cfg)
    return RedirectResponse("/seguranca", status_code=303)


@app.post("/seguranca/perfil/{nome}")
def seg_perfil(nome: str):
    perfis = {
        "cautela": {"intervalo_min": 45, "intervalo_max": 120, "perfis_por_sessao": 15, "perfis_por_hora": 15,
                    "perfis_por_dia": 30, "pausa_longa_a_cada": 6, "pausa_longa_min": 300, "pausa_longa_max": 480},
        "normal": {k: seguranca.PADRAO[k] for k in ("intervalo_min", "intervalo_max", "perfis_por_sessao",
                   "perfis_por_hora", "perfis_por_dia", "pausa_longa_a_cada", "pausa_longa_min", "pausa_longa_max")},
        "acelerado": {"intervalo_min": 20, "intervalo_max": 60, "perfis_por_sessao": 40, "perfis_por_hora": 40,
                      "perfis_por_dia": 120, "pausa_longa_a_cada": 10, "pausa_longa_min": 180, "pausa_longa_max": 360},
    }
    if nome not in perfis:
        raise HTTPException(404)
    con = seguranca.conectar()
    cfg = db.get_config(con, "seguranca", {}) or {}
    cfg.update(perfis[nome])
    db.set_config(con, "seguranca", cfg)
    return RedirectResponse("/seguranca", status_code=303)


# ---------------------------------------------------------------- API / exportação
@app.post("/api/perfis")
async def api_salvar(request: Request):
    """Recebe um perfil (ou lista) em JSON — mesmo formato do `propsec.py salvar`."""
    con = db.conectar()
    corpo = await request.json()
    itens = corpo if isinstance(corpo, list) else [corpo]
    out = []
    for d in itens:
        status = d.pop("status", None)
        pid, criado = db.salvar_perfil(con, d, status=status)
        r = con.execute("SELECT username, score, status FROM perfis WHERE id=?", (pid,)).fetchone()
        out.append({**dict(r), "criado": criado})
    return JSONResponse(out)


@app.get("/api/versao")
def api_versao():
    return {"versao": VERSAO}


@app.get("/api/agente")
def api_agente():
    return seguranca.ler_atividade(seguranca.conectar())


@app.get("/api/perfis/{username}")
def api_perfil(username: str):
    con = db.conectar()
    p = db.buscar_perfil(con, username)
    if not p:
        raise HTTPException(404)
    return dict(p)


@app.get("/exportar.csv")
def exportar(status: str = ""):
    con = db.conectar()
    sql, args = "SELECT * FROM perfis", []
    if status:
        sql += " WHERE status=?"; args.append(status)
    rows = con.execute(sql + " ORDER BY score DESC", args).fetchall()
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";")
    if rows:
        w.writerow(rows[0].keys())
        w.writerows(list(r) for r in rows)
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=propsec.csv"})
