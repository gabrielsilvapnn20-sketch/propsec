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

from app import aprendizado, db, scoring, seguranca  # noqa: E402

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
# Agências/hubs que seguem várias das fechadas: quem elas seguem é ouro.
AGENCIAS = ["fly.creators.br", "hub.influ.br"]
REFERENCIAS_INICIAIS = "referencias/referencias_iniciais.json"
BUSCAS = ["aceito parcerias", "blogueira maranhão", "digital influencer MA",
          "mãe solo blogueira", "divulgação loja", "parcerias no direct", "blogueira nordeste",
          "notícias Codó", "acontece Imperatriz", "Caxias MA notícias", "Bacabal news",
          "loja feminina São Luís", "boutique Imperatriz", "fofoca Timon", "Teresina blogueira",
          "Fortaleza blogueira", "Belém blogueira", "Parnaíba blogueira"]


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
    if a.lucro is not None:
        con.execute("UPDATE perfis SET lucro_dia=? WHERE id=?", (a.lucro, p["id"]))
        db.registrar_evento(con, p["id"], "lucro_dia", para=str(a.lucro), nota=a.nota)
    if a.resultado:
        con.execute("UPDATE perfis SET resultado_nivel=? WHERE id=?", (a.resultado, p["id"]))
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
    for tipo, lista in (("agencia", AGENCIAS), ("local", CIDADES_MA), ("hashtag", HASHTAGS), ("busca", BUSCAS)):
        for v in lista:
            cur = con.execute("INSERT OR IGNORE INTO fontes(tipo, valor) VALUES(?,?)", (tipo, v))
            n += cur.rowcount
    con.commit()
    print(f"{n} fontes novas cadastradas")
    import os
    if os.path.exists(REFERENCIAS_INICIAIS):
        dados = json.load(open(REFERENCIAS_INICIAIS, encoding="utf-8"))
        for d in dados.get("perfis", []):
            d = dict(d); status = d.pop("status", None)
            db.salvar_perfil(con, d, status=status)
        for f in dados.get("fontes", []):
            con.execute("INSERT OR IGNORE INTO fontes(tipo, valor, nota) VALUES(?,?,?)",
                        (f["tipo"], f["valor"], f.get("nota")))
        con.commit()
        print(f"{len(dados.get('perfis', []))} referências iniciais carregadas")


REDE_CONHECIDA = ("agencia", "similar")  # fontes ligadas às referências/rede que vocês já trabalham


def cmd_proximas_fontes(a):
    """Plano de fontes da sessão: no máximo 1/3 da rede conhecida, o resto horizonte novo."""
    con = db.conectar()
    rend = {(r["origem"], r["detalhe"]): r for r in aprendizado.desempenho_fontes(con)}
    fontes = con.execute("SELECT * FROM fontes WHERE ativa=1").fetchall()
    conhecida, nova = [], []
    for f in fontes:
        r = rend.get((f["tipo"], f["valor"]))
        bons = (r["bons"] or 0) if r else 0
        fechados = (r["fechados"] or 0) if r else 0
        vistos = max(f["perfis_vistos"], 1)
        rendimento = min((bons + 3 * fechados) / vistos * 5, 1)
        novidade = 1.0 / (1 + f["vezes_explorada"])
        item = (0.6 * rendimento + 0.4 * novidade, f, bons, fechados)
        (conhecida if f["tipo"] in REDE_CONHECIDA else nova).append(item)

    # "Bola de neve" a partir de achados NOVOS (fora da rede das referências)
    ja = {f["valor"] for f in fontes if f["tipo"] in ("similar", "achado")}
    achados = con.execute(
        "SELECT username, score, cidade, uf FROM perfis WHERE referencia IS NULL "
        "AND COALESCE(origem,'') NOT IN ('referencia','manual','agencia','similar') "
        "AND status IN ('novo','aprovado','contatado','respondeu','negociando','fechado') AND score >= 60 "
        "ORDER BY score DESC LIMIT 30").fetchall()
    achados = [r for r in achados if r["username"] not in ja][:8]

    def linha(item):
        nota, f, bons, fechados = item
        return (f"{f['tipo']:<12} {f['valor']:<28} exploradas={f['vezes_explorada']} "
                f"vistos={f['perfis_vistos']} bons={bons} fechados={fechados}"
                + (f"  ({f['nota']})" if f["nota"] else ""))

    print("PLANO DA SESSÃO: no máximo 1/3 dos perfis da REDE CONHECIDA; o resto de HORIZONTE NOVO.\n")
    print("== 1. Horizonte novo: bola de neve a partir de achados fora da rede (sugeridos/comentaristas) ==")
    for r in achados:
        print(f"achado       @{r['username']:<27} score={r['score']} {r['cidade'] or ''}")
    if not achados:
        print("(nenhum ainda: comece por locais, páginas locais e hashtags)")
    print("\n== 2. Horizonte novo: locais, páginas locais, hashtags, buscas ==")
    for item in sorted(nova, key=lambda x: -x[0])[: a.n]:
        print(linha(item))
    print("\n== 3. Rede conhecida (agências e próximos das referências) — use pouco ==")
    for item in sorted(conhecida, key=lambda x: -x[0])[: max(3, a.n // 3)]:
        print(linha(item))


def cmd_contatados(a):
    """Marca perfis que vocês já chamaram fora do sistema, para o agente não trazer de novo."""
    con = db.conectar()
    nomes = list(a.usernames)
    if a.arquivo:
        texto = open(a.arquivo, encoding="utf-8").read()
        nomes += [t for t in texto.replace(",", " ").split() if t.strip()]
    n_novos = n_atual = 0
    for u in nomes:
        u = db.normalizar_username(u)
        if not u:
            continue
        p = db.buscar_perfil(con, u)
        if p is None:
            db.salvar_perfil(con, {"username": u, "origem": "manual",
                                   "observacoes": "já contatado antes de entrar no sistema"}, status="contatado")
            n_novos += 1
        elif p["status"] in ("novo", "aprovado", "ignorado", "descartado"):
            db.mudar_status(con, p["id"], "contatado", nota="já contatado (informado pelo usuário)")
            n_atual += 1
    print(f"{n_novos} perfis adicionados como já contatados, {n_atual} atualizados")


def cmd_hoje(a):
    con = seguranca.conectar()
    hoje = date.today().isoformat()
    salvos = con.execute("SELECT COUNT(*) FROM perfis WHERE criado_em LIKE ?", (hoje + "%",)).fetchone()[0]
    c, cfg = seguranca.contagens(con), seguranca.config(con)
    print(f"hoje: {c['dia']}/{cfg['perfis_por_dia']} perfis visitados, {salvos} cadastrados | "
          f"última hora: {c['hora']}/{cfg['perfis_por_hora']} | sessão: {c['sessao']}/{cfg['perfis_por_sessao']}")
    pode, motivo, _ = seguranca.verificar(con)
    print("SITUAÇÃO: pode prospectar" if pode else f"SITUAÇÃO: BLOQUEADO — {motivo}")


def cmd_liberar(a):
    """Porteiro: chamar ANTES de abrir cada perfil. Espera o intervalo seguro ou manda parar."""
    con = seguranca.conectar()
    ok, msg = seguranca.liberar(con, a.username)
    print(msg if ok else f"PARAR: {msg}")
    if not ok:
        sys.exit(2)


def cmd_alerta(a):
    con = seguranca.conectar()
    cfg = seguranca.config(con)
    seguranca.pausar(con, a.texto, horas=cfg["horas_pausa_apos_alerta"], tipo="alerta")
    print(f"AGENTE PAUSADO por {cfg['horas_pausa_apos_alerta']}h: {a.texto}")


def cmd_parar(a):
    con = seguranca.conectar()
    seguranca.pausar(con, a.motivo or "parado pelo usuário")
    print("agente pausado")


def cmd_retomar(a):
    con = seguranca.conectar()
    seguranca.retomar(con)
    print("agente liberado")


def cmd_sessao(a):
    con = seguranca.conectar()
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
    s.add_argument("--lucro", type=float, help="lucro em R$ no dia da parceria")
    s.add_argument("--resultado", choices=list(db.NIVEIS_RESULTADO), help="nível do resultado")
    s.add_argument("--qualidade", type=int, choices=range(1, 6)); s.add_argument("--nota")
    s.set_defaults(f=cmd_status)
    s = sub.add_parser("fonte"); s.add_argument("tipo", choices=["agencia", "similar", "achado", "pagina_local", "hashtag", "local", "busca", "comentarios", "explorar"])
    s.add_argument("valor"); s.add_argument("--vistos", type=int, default=0); s.add_argument("--nota")
    s.set_defaults(f=cmd_fonte)
    s = sub.add_parser("semear"); s.set_defaults(f=cmd_semear)
    s = sub.add_parser("contatados"); s.add_argument("usernames", nargs="*")
    s.add_argument("--arquivo", help="arquivo .txt com os @ (um por linha ou separados por espaço)")
    s.set_defaults(f=cmd_contatados)
    s = sub.add_parser("proximas-fontes"); s.add_argument("-n", type=int, default=15); s.set_defaults(f=cmd_proximas_fontes)
    s = sub.add_parser("hoje"); s.set_defaults(f=cmd_hoje)
    s = sub.add_parser("liberar"); s.add_argument("username"); s.set_defaults(f=cmd_liberar)
    s = sub.add_parser("alerta"); s.add_argument("texto"); s.set_defaults(f=cmd_alerta)
    s = sub.add_parser("parar"); s.add_argument("motivo", nargs="?"); s.set_defaults(f=cmd_parar)
    s = sub.add_parser("retomar"); s.set_defaults(f=cmd_retomar)
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
