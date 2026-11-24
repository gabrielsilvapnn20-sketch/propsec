#!/usr/bin/env python3
"""PropSec — linha de comando usada pelo agente de prospecção (e por você).

Exemplos:
  python propsec.py existe @maria @joana          # quais já estão no banco (não revisitar)
  python propsec.py salvar perfil.json            # cadastra/atualiza (JSON objeto ou lista)
  echo '{...}' | python propsec.py salvar -       # idem, lendo da entrada
  python propsec.py fonte hashtag blogueiramaranhense --vistos 30
  python propsec.py proximas-fontes               # onde o agente deve procurar agora
  python propsec.py hoje                          # quantos perfis já foram visitados hoje
  python propsec.py status @maria contatado
  python propsec.py status @maria fechado --views 1800
  python propsec.py recalibrar                    # reaprende os pesos com os resultados
  python propsec.py resumo
  python propsec.py exportar saida.csv
  python propsec.py servidor                      # abre o painel em http://localhost:8000
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")  # Windows

from app import aprendizado, db, scoring  # noqa: E402

CIDADES_MA = [
    "São Luís", "Imperatriz", "São José de Ribamar", "Timon", "Caxias", "Codó",
    "Paço do Lumiar", "Açailândia", "Bacabal", "Balsas", "Santa Inês", "Pinheiro",
    "Barra do Corda", "Chapadinha", "Santa Luzia", "Grajaú", "Itapecuru-Mirim",
    "Coroatá", "Zé Doca", "Viana", "Presidente Dutra", "Lago da Pedra",
    "Barreirinhas", "Rosário", "Pedreiras", "Buriticupu", "Estreito", "Colinas",
]
HASHTAGS = [
    "blogueiramaranhense", "maranhao", "saoluis", "saoluisma", "imperatrizma",
    "timonma", "caxiasma", "codoma", "bacabalma", "balsasma",
    "blogueirinha", "influenciadoradigital", "influencerdigital", "publi", "publipost",
    "recebidos", "parceria", "permuta", "provador", "lookdodia",
    "maesolo", "maesolteira", "maternidadereal", "maedemenina", "maedemenino",
    "mulherdepreso", "esposadedetento", "visitaintima", "fielaoamor",
]
BUSCAS = ["aceito parcerias", "blogueira maranhão", "digital influencer MA",
          "mãe solo blogueira", "divulgação loja"]


def _ler_json(caminho):
    texto = sys.stdin.read() if caminho == "-" else open(caminho, encoding="utf-8").read()
    dados = json.loads(texto)
    return dados if isinstance(dados, list) else [dados]


def cmd_existe(a):
    con = db.conectar()
    for u in a.usernames:
        p = db.buscar_perfil(con, u)
        nome = db.normalizar_username(u)
        if p:
            print(f"JA_EXISTE @{nome} status={p['status']} score={p['score']}")
        else:
            print(f"NOVO @{nome}")


def cmd_salvar(a):
    con = db.conectar()
    for d in _ler_json(a.arquivo):
        if a.referencia:
            d["referencia"] = a.referencia
        status = d.pop("status", None) or a.status
        pid, criado = db.salvar_perfil(con, d, status=status)
        p = con.execute("SELECT username, score, story_views_estimado, status FROM perfis WHERE id=?",
                        (pid,)).fetchone()
        print(f"{'CRIADO' if criado else 'ATUALIZADO'} @{p['username']} score={p['score']} "
              f"stories_est={p['story_views_estimado']} status={p['status']}")


def cmd_status(a):
    con = db.conectar()
    p = db.buscar_perfil(con, a.username)
    if not p:
        sys.exit(f"perfil @{db.normalizar_username(a.username)} não encontrado")
    if a.views is not None:
        con.execute("UPDATE perfis SET story_views_real=?, story_views_informado_em=? WHERE id=?",
                    (a.views, db.agora(), p["id"]))
        db.registrar_evento(con, p["id"], "views_stories", para=str(a.views), nota=a.nota)
    if a.qualidade is not None:
        con.execute("UPDATE perfis SET qualidade_manual=? WHERE id=?", (a.qualidade, p["id"]))
    db.mudar_status(con, p["id"], a.novo_status, nota=a.nota)
    scoring.rescore_perfil(con, p["id"])
    con.commit()
    print(f"@{p['username']}: {p['status']} -> {a.novo_status}")


def cmd_fonte(a):
    con = db.conectar()
    db.registrar_fonte(con, a.tipo, a.valor, a.vistos, a.nota)
    print(f"fonte registrada: {a.tipo}:{a.valor} (+{a.vistos} vistos)")


def cmd_semear(a):
    con = db.conectar()
    n = 0
    for tipo, lista in (("local", CIDADES_MA), ("hashtag", HASHTAGS), ("busca", BUSCAS)):
        for v in lista:
            cur = con.execute("INSERT OR IGNORE INTO fontes(tipo, valor) VALUES(?,?)", (tipo, v))
            n += cur.rowcount
    con.commit()
    print(f"{n} fontes novas cadastradas")


def cmd_proximas_fontes(a):
    """Mistura: fontes que mais renderam (explorar mais fundo) + fontes pouco exploradas."""
    con = db.conectar()
    rend = {(r["origem"], r["detalhe"]): r for r in aprendizado.desempenho_fontes(con)}
    fontes = con.execute("SELECT * FROM fontes WHERE ativa=1").fetchall()
    ranqueadas = []
    for f in fontes:
        r = rend.get((f["tipo"], f["valor"]))
        bons = (r["bons"] or 0) if r else 0
        fechados = (r["fechados"] or 0) if r else 0
        vistos = max(f["perfis_vistos"], 1)
        rendimento = (bons + 3 * fechados) / vistos
        novidade = 1.0 / (1 + f["vezes_explorada"])
        ranqueadas.append((0.6 * min(rendimento * 5, 1) + 0.4 * novidade, f, bons, fechados))
    # Similares das melhores (fechadas/referências) sempre entram como sugestão
    refs = con.execute(
        "SELECT username FROM perfis WHERE referencia IS NOT NULL OR status='fechado' "
        "ORDER BY COALESCE(story_views_real,0) DESC, score DESC LIMIT 20").fetchall()
    ja = {f["valor"] for f in fontes if f["tipo"] == "similar"}
    print("== Similares de perfis que deram certo (sugeridos/seguidos/comentaristas) ==")
    for r in refs:
        if r["username"] not in ja:
            print(f"similar  @{r['username']}  (nunca explorado)")
    print("\n== Fontes ranqueadas (rendimento + novidade) ==")
    for nota, f, bons, fechados in sorted(ranqueadas, key=lambda x: -x[0])[: a.n]:
        print(f"{f['tipo']:<8} {f['valor']:<28} exploradas={f['vezes_explorada']} "
              f"vistos={f['perfis_vistos']} bons={bons} fechados={fechados}")


def cmd_hoje(a):
    con = db.conectar()
    hoje = date.today().isoformat()
    salvos = con.execute("SELECT COUNT(*) FROM perfis WHERE criado_em LIKE ?", (hoje + "%",)).fetchone()[0]
    visitados = con.execute(
        "SELECT COALESCE(SUM(perfis_visitados),0) FROM sessoes WHERE inicio LIKE ?", (hoje + "%",)
    ).fetchone()[0]
    limite = db.get_config(con, "limite_diario", 120)
    print(f"hoje: {salvos} perfis cadastrados, {visitados} visitados (limite diário: {limite})")


def cmd_sessao(a):
    con = db.conectar()
    if a.acao == "inicio":
        cur = con.execute("INSERT INTO sessoes(inicio) VALUES(?)", (db.agora(),))
        con.commit()
        print(f"sessao={cur.lastrowid}")
        cmd_hoje(a)
    else:
        sid = a.id or con.execute("SELECT MAX(id) FROM sessoes").fetchone()[0]
        con.execute("UPDATE sessoes SET fim=?, perfis_visitados=?, perfis_salvos=?, nota=? WHERE id=?",
                    (db.agora(), a.visitados, a.salvos, a.nota, sid))
        con.commit()
        print(f"sessao {sid} encerrada")


def cmd_recalibrar(a):
    con = db.conectar()
    db.backup()
    rel = aprendizado.recalibrar(con, aplicar=not a.simular)
    print(json.dumps(rel, ensure_ascii=False, indent=2))


def cmd_resumo(a):
    con = db.conectar()
    for r in con.execute("SELECT status, COUNT(*) n FROM perfis GROUP BY status ORDER BY n DESC"):
        print(f"{db.STATUS.get(r['status'], r['status']):<26} {r['n']}")
    print("\nTop 10 aguardando aprovação:")
    for r in con.execute("SELECT username, score, seguidores, cidade, story_views_estimado FROM perfis "
                         "WHERE status='novo' ORDER BY score DESC LIMIT 10"):
        print(f"  @{r['username']:<28} score={r['score']:<5} seg={r['seguidores']} "
              f"{r['cidade'] or ''} stories~{r['story_views_estimado']}")


def cmd_exportar(a):
    con = db.conectar()
    rows = con.execute("SELECT * FROM perfis ORDER BY score DESC").fetchall()
    with open(a.saida, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        if rows:
            w.writerow(rows[0].keys())
            for r in rows:
                w.writerow(list(r))
    print(f"{len(rows)} perfis exportados para {a.saida}")


def cmd_servidor(a):
    import uvicorn
    print(f"Painel em http://localhost:{a.porta}")
    uvicorn.run("app.web:app", host="127.0.0.1", port=a.porta)


def main():
    ap = argparse.ArgumentParser(description="PropSec — prospecção de influenciadoras")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("existe"); s.add_argument("usernames", nargs="+"); s.set_defaults(f=cmd_existe)
    s = sub.add_parser("salvar"); s.add_argument("arquivo")
    s.add_argument("--status", choices=list(db.STATUS)); s.add_argument("--referencia", choices=["fechado", "gostamos"])
    s.set_defaults(f=cmd_salvar)
    s = sub.add_parser("status"); s.add_argument("username"); s.add_argument("novo_status", choices=list(db.STATUS))
    s.add_argument("--views", type=float, help="views médias reais dos stories")
    s.add_argument("--qualidade", type=int, choices=range(1, 6)); s.add_argument("--nota")
    s.set_defaults(f=cmd_status)
    s = sub.add_parser("fonte"); s.add_argument("tipo", choices=["hashtag", "local", "similar", "busca", "comentarios", "explorar"])
    s.add_argument("valor"); s.add_argument("--vistos", type=int, default=0); s.add_argument("--nota")
    s.set_defaults(f=cmd_fonte)
    s = sub.add_parser("semear"); s.set_defaults(f=cmd_semear)
    s = sub.add_parser("proximas-fontes"); s.add_argument("-n", type=int, default=15); s.set_defaults(f=cmd_proximas_fontes)
    s = sub.add_parser("hoje"); s.set_defaults(f=cmd_hoje)
    s = sub.add_parser("sessao"); s.add_argument("acao", choices=["inicio", "fim"]); s.add_argument("--id", type=int)
    s.add_argument("--visitados", type=int, default=0); s.add_argument("--salvos", type=int, default=0); s.add_argument("--nota")
    s.set_defaults(f=cmd_sessao)
    s = sub.add_parser("recalibrar"); s.add_argument("--simular", action="store_true"); s.set_defaults(f=cmd_recalibrar)
    s = sub.add_parser("resumo"); s.set_defaults(f=cmd_resumo)
    s = sub.add_parser("exportar"); s.add_argument("saida"); s.set_defaults(f=cmd_exportar)
    s = sub.add_parser("servidor"); s.add_argument("--porta", type=int, default=8000); s.set_defaults(f=cmd_servidor)

    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
