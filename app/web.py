"""Painel web do PropSec (roda local: python propsec.py servidor)."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime
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


def _valor(v):
    """Valor para campo de formulário: sem '.0' sobrando, vazio se nulo."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _dias(ts):
    if not ts:
        return None
    try:
        return (datetime.now() - datetime.fromisoformat(ts)).days
    except ValueError:
        return None


tpl.env.filters["n"] = _fmt_int
tpl.env.filters["v"] = _valor
tpl.env.filters["dias"] = _dias
tpl.env.filters["motivos"] = lambda s: json.loads(s) if s else []
tpl.env.globals["STATUS"] = db.STATUS
tpl.env.globals["NOMES"] = scoring.NOMES
tpl.env.globals["NIVEIS"] = db.NIVEIS_RESULTADO


VERSAO = "2026.11.26-c"

# Próximo passo de cada etapa (botões nas Conversas e no perfil)
PROXIMOS = {
    "novo": [("aprovado", "Aprovar"), ("descartado", "Descartar")],
    "aprovado": [("contatado", "Enviei mensagem")],
    "contatado": [("respondeu", "Respondeu"), ("sem_resposta", "Sem resposta")],
    "respondeu": [("negociando", "Negociando"), ("recusou", "Recusou")],
    "negociando": [("fechado", "Fechou parceria"), ("recusou", "Recusou")],
    "sem_resposta": [("respondeu", "Respondeu depois")],
    "recusou": [("negociando", "Voltou a negociar")],
    "fechado": [],
    "descartado": [("novo", "Voltar para a fila")],
    "ignorado": [("novo", "Voltar para a fila")],
}
tpl.env.globals["PROXIMOS"] = PROXIMOS
EM_ANDAMENTO = ["aprovado", "contatado", "respondeu", "negociando"]
DESCR_ETAPA = {
    "aprovado": "Aprovadas, falta mandar mensagem",
    "contatado": "Mensagem enviada, esperando resposta",
    "respondeu": "Responderam",
    "negociando": "Conversando valores",
}
tpl.env.globals["DESCR_ETAPA"] = DESCR_ETAPA
DIAS_PARADO = 2


def _menu(con):
    fila = con.execute("SELECT COUNT(*) FROM perfis WHERE status='novo'").fetchone()[0]
    aprovados = con.execute("SELECT COUNT(*) FROM perfis WHERE status='aprovado' AND referencia IS NULL").fetchone()[0]
    return {"fila": fila, "conversas": aprovados}


def render(request, nome, **ctx):
    try:
        con = seguranca.conectar()
        ctx.setdefault("agente", seguranca.ler_atividade(con))
        ctx.setdefault("menu", _menu(con))
    except Exception:
        ctx.setdefault("agente", {"estado": "parado"})
        ctx.setdefault("menu", {})
    ctx["versao"] = VERSAO
    return tpl.TemplateResponse(request, nome, ctx)


def _voltar(request, padrao="/"):
    return RedirectResponse(request.headers.get("referer") or padrao, status_code=303)


def _pct(a, b):
    return round(100 * a / b) if b else 0


# ---------------------------------------------------------------- páginas
@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    con = seguranca.conectar()
    base = "FROM perfis WHERE referencia IS NULL"
    cont = {r["status"]: r["n"] for r in con.execute(f"SELECT status, COUNT(*) n {base} GROUP BY status")}
    # taxas só com o que passou pelo sistema (sem 'já contatados por fora')
    taxa = {r["status"]: r["n"] for r in con.execute(
        f"SELECT status, COUNT(*) n {base} AND COALESCE(origem,'') != 'manual' GROUP BY status")}
    contatados = sum(taxa.get(x, 0) for x in db.STATUS_CONTATADOS)
    responderam = sum(taxa.get(x, 0) for x in db.STATUS_RESPONDERAM)
    fechados = taxa.get("fechado", 0)
    semana = con.execute(f"SELECT COUNT(*) {base} AND criado_em >= date('now','-7 day') "
                         "AND status != 'ignorado'").fetchone()[0]
    lucro = con.execute(f"SELECT SUM(lucro_dia) {base} AND status='fechado'").fetchone()[0]

    parados = con.execute(
        f"SELECT * {base} AND status IN ('contatado','respondeu','negociando') "
        "AND atualizado_em < datetime('now','localtime',?) ORDER BY atualizado_em",
        (f"-{DIAS_PARADO} day",)).fetchall()
    sem_resultado = con.execute(
        f"SELECT * {base} AND status='fechado' AND lucro_dia IS NULL AND resultado_nivel IS NULL").fetchall()
    pode, motivo, _ = seguranca.verificar(con)

    acoes = []
    if not pode and "PAUSADO" in motivo:
        acoes.append({"n": "!", "titulo": "O agente está pausado", "texto": motivo, "url": "/seguranca",
                      "ir": "Ver agente", "alerta": True})
    if cont.get("novo"):
        acoes.append({"n": cont["novo"], "titulo": "perfis esperando sua aprovação",
                      "texto": "O agente achou; aprove ou descarte.", "url": "/fila", "ir": "Aprovar"})
    if cont.get("aprovado"):
        acoes.append({"n": cont["aprovado"], "titulo": "aprovados esperando mensagem",
                      "texto": "Mande a mensagem e marque 'Enviei mensagem'.", "url": "/conversas", "ir": "Abrir"})
    if parados:
        acoes.append({"n": len(parados), "titulo": f"conversas paradas há mais de {DIAS_PARADO} dias",
                      "texto": ", ".join("@" + p["username"] for p in parados[:4]) + (" …" if len(parados) > 4 else ""),
                      "url": "/conversas", "ir": "Ver"})
    if sem_resultado:
        acoes.append({"n": len(sem_resultado), "titulo": "parcerias fechadas sem resultado registrado",
                      "texto": "Registre o lucro do dia: é o que mais ensina o sistema.",
                      "url": f"/p/{sem_resultado[0]['username']}", "ir": "Registrar"})

    etapas = [("novo", "Na fila"), ("aprovado", "Aprovados"), ("contatado", "Mensagem enviada"),
              ("respondeu", "Responderam"), ("negociando", "Negociando"), ("fechado", "Fechadas")]
    funil = [(k, nome, cont.get(k, 0)) for k, nome in etapas]
    top = con.execute("SELECT * FROM perfis WHERE status='novo' ORDER BY score DESC LIMIT 5").fetchall()
    kpis = {"semana": semana, "contatados": contatados, "taxa_resposta": _pct(responderam, contatados),
            "fechados": fechados, "lucro": lucro}
    return render(request, "inicio.html", acoes=acoes, kpis=kpis, funil=funil, top=top)


@app.get("/fila", response_class=HTMLResponse)
def fila(request: Request, q: str = "", ordem: str = "nota"):
    con = db.conectar()
    sql, args = "SELECT * FROM perfis WHERE status='novo'", []
    if q:
        sql += " AND (cidade LIKE ? OR uf LIKE ? OR publicos LIKE ? OR bio LIKE ? OR username LIKE ?)"
        args += [f"%{q}%"] * 5
    ordens = {"nota": "score DESC", "seguidores": "seguidores DESC", "recentes": "criado_em DESC"}
    perfis = con.execute(f"{sql} ORDER BY {ordens.get(ordem, 'score DESC')} LIMIT 200", args).fetchall()
    return render(request, "fila.html", perfis=perfis, q=q, ordem=ordem)


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


@app.get("/pipeline")
def pipeline_antigo():
    return RedirectResponse("/conversas", status_code=301)


@app.get("/conversas", response_class=HTMLResponse)
def conversas(request: Request, aba: str = "andamento"):
    con = db.conectar()
    q = "SELECT * FROM perfis WHERE status=? AND referencia IS NULL ORDER BY atualizado_em LIMIT 200"
    contagem = {r["status"]: r["n"] for r in con.execute(
        "SELECT status, COUNT(*) n FROM perfis WHERE referencia IS NULL GROUP BY status")}
    if aba == "andamento":
        colunas = [(st, db.STATUS[st], con.execute(q, (st,)).fetchall()) for st in EM_ANDAMENTO]
        lista = []
    else:
        colunas = []
        lista = con.execute(q.replace("ORDER BY atualizado_em", "ORDER BY atualizado_em DESC"), (aba,)).fetchall() \
            if aba in ("fechado", "recusou", "sem_resposta") else []
    return render(request, "pipeline.html", colunas=colunas, lista=lista, aba=aba, contagem=contagem,
                  dias_parado=DIAS_PARADO)


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
    fontes = aprendizado.desempenho_fontes(con)
    for f in fontes:
        avaliados = (f["aceitos"] or 0) + (f["descartados"] or 0)
        f["taxa_aprov"] = _pct(f["aceitos"] or 0, avaliados) if avaliados else None
        f["taxa_resp"] = _pct(f["responderam"] or 0, f["contatados"] or 0) if f["contatados"] else None
    return render(request, "aprendizado.html", pesos=pesos, cfg=cfg, sim=simulacao,
                  fontes=fontes,
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
    anterior = p["status"]
    db.mudar_status(con, p["id"], status, nota=nota or None)
    if status in ("aprovado", "descartado", "fechado") and anterior != status:
        aprendizado.registrar_decisao(con)
    return _voltar(request)


@app.post("/p/{username}/resultado")
def acao_resultado(username: str, lucro_dia: str = Form(""), resultado_nivel: str = Form(""),
                   story_views_real: str = Form("")):
    con = db.conectar()
    p = db.buscar_perfil(con, username)
    if not p:
        raise HTTPException(404)
    def num(x):
        x = x.strip().replace("R$", "").replace(".", "").replace(",", ".")
        return float(x) if x else None
    lucro, views = num(lucro_dia), num(story_views_real)
    if lucro is not None:
        con.execute("UPDATE perfis SET lucro_dia=? WHERE id=?", (lucro, p["id"]))
        db.registrar_evento(con, p["id"], "lucro_dia", para=f"R$ {lucro:.0f}")
        if not resultado_nivel:
            resultado_nivel = "alto" if lucro >= 1000 else ("medio" if lucro >= 200 else "baixo")
    if resultado_nivel in db.NIVEIS_RESULTADO:
        con.execute("UPDATE perfis SET resultado_nivel=? WHERE id=?", (resultado_nivel, p["id"]))
    if views is not None:
        con.execute("UPDATE perfis SET story_views_real=?, story_views_informado_em=? WHERE id=?",
                    (views, db.agora(), p["id"]))
        db.registrar_evento(con, p["id"], "views_stories", para=str(int(views)))
    scoring.rescore_perfil(con, p["id"])
    con.commit()
    if lucro is not None or resultado_nivel:
        aprendizado.registrar_decisao(con)
    return RedirectResponse(f"/p/{p['username']}", status_code=303)


@app.post("/api/perfis/{username}/status")
async def api_status(username: str, request: Request):
    """Muda a etapa sem recarregar a página (fila de aprovação)."""
    con = db.conectar()
    p = db.buscar_perfil(con, username)
    if not p:
        raise HTTPException(404)
    novo = (await request.json()).get("status")
    if novo not in db.STATUS:
        raise HTTPException(400, "status inválido")
    anterior = p["status"]
    db.mudar_status(con, p["id"], novo, nota="pelo painel")
    if novo in ("aprovado", "descartado", "fechado") and anterior != novo:
        aprendizado.registrar_decisao(con)
    return {"ok": True, "username": p["username"], "status": novo, "anterior": anterior,
            "fila": con.execute("SELECT COUNT(*) FROM perfis WHERE status='novo'").fetchone()[0]}


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
    cfg = seguranca.config(con)
    return render(request, "seguranca.html", cfg=cfg, modo=_modo_atual(cfg), st=seguranca.estado(con),
                  c=seguranca.contagens(con), risco=seguranca.risco(con), pode=pode, motivo=motivo,
                  ativ=seguranca.ler_atividade(con),
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


MODOS = {
        "cautela": {"intervalo_min": 45, "intervalo_max": 120, "perfis_por_sessao": 15, "perfis_por_hora": 15,
                    "perfis_por_dia": 30, "pausa_longa_a_cada": 6, "pausa_longa_min": 300, "pausa_longa_max": 480},
        "normal": {k: seguranca.PADRAO[k] for k in ("intervalo_min", "intervalo_max", "perfis_por_sessao",
                   "perfis_por_hora", "perfis_por_dia", "pausa_longa_a_cada", "pausa_longa_min", "pausa_longa_max")},
        "acelerado": {"intervalo_min": 20, "intervalo_max": 60, "perfis_por_sessao": 40, "perfis_por_hora": 40,
                      "perfis_por_dia": 120, "pausa_longa_a_cada": 10, "pausa_longa_min": 180, "pausa_longa_max": 360},
}


def _modo_atual(cfg):
    for nome, valores in MODOS.items():
        if all(cfg.get(k) == v for k, v in valores.items()):
            return nome
    return "personalizado"


@app.post("/seguranca/perfil/{nome}")
def seg_perfil(nome: str):
    perfis = MODOS
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
