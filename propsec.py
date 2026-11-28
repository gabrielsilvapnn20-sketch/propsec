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
# Agências/hubs: quem elas seguem provavelmente já é agenciada. NÃO usar como fonte.
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
    for tipo, lista in (("local", CIDADES_MA), ("hashtag", HASHTAGS), ("busca", BUSCAS)):
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
            atual = db.buscar_perfil(con, d["username"])
            if atual and atual["status"] not in ("novo", "ignorado", "descartado"):
                status = None  # já está andando no funil: não mexe na etapa
            db.salvar_perfil(con, d, status=status)
        for f in dados.get("fontes", []):
            con.execute("INSERT OR IGNORE INTO fontes(tipo, valor, nota) VALUES(?,?,?)",
                        (f["tipo"], f["valor"], f.get("nota")))
        con.commit()
        print(f"{len(dados.get('perfis', []))} referências iniciais carregadas")
    # versões antigas usavam agências e páginas de loja como fonte; desativa
    con.execute("UPDATE fontes SET ativa=0 WHERE tipo = 'agencia'")
    con.commit()
    db.corrigir_fontes(con)


def _sementes(con):
    """Perfis bons de onde seguir as SUGESTÕES do Instagram, com a prioridade de cada um.

    O uso de uma semente é medido de dois jeitos (o que for maior): quantas vezes foi registrada
    como fonte e quantos perfis já foram salvos a partir dela. Quanto mais usada, menos prioridade.
    """
    usadas = {r["valor"]: r for r in con.execute("SELECT * FROM fontes WHERE tipo='sugestoes'")}
    achados = {r["d"]: r["n"] for r in con.execute(
        "SELECT origem_detalhe d, COUNT(*) n FROM perfis WHERE origem='sugestoes' GROUP BY 1")}
    rows = con.execute(
        """SELECT username, status, referencia, resultado_nivel, score, cidade, uf FROM perfis
           WHERE status IN ('fechado','negociando','respondeu','aprovado','contatado')
              OR referencia IS NOT NULL OR (status='novo' AND score >= 65)""").fetchall()
    out = []
    for r in rows:
        base = {"fechado": 5, "negociando": 4, "respondeu": 3.5, "aprovado": 3, "contatado": 3}.get(r["status"], 1.5)
        if r["resultado_nivel"] == "alto":
            base += 2
        if r["referencia"] is None and r["status"] != "novo":
            base += 2  # aprovada por você: abre caminhos fora da rede antiga
        base += (r["score"] or 0) / 100
        uso_reg = usadas[r["username"]]["vezes_explorada"] if r["username"] in usadas else 0
        uso = max(uso_reg, achados.get(r["username"], 0) / 6)
        out.append((base / (1 + 0.8 * uso), r, uso))
    return out


def _sorteio_ponderado(itens, k, rng):
    """Escolhe k itens sem repetir; prioridade maior = mais chance (varia a cada sessão)."""
    itens, escolha = list(itens), []
    while itens and len(escolha) < k:
        total = sum(max(p, 0.01) for p, *_ in itens)
        x, acc = rng.uniform(0, total), 0.0
        for idx, it in enumerate(itens):
            acc += max(it[0], 0.01)
            if acc >= x:
                escolha.append(itens.pop(idx))
                break
    return escolha


def cmd_proximas_fontes(a):
    """Plano da sessão com equilíbrio: seguir a linha aprovada x explorar caminhos novos."""
    import random
    con = db.conectar()
    n = a.perfis
    q_linha, q_pot = round(n * 0.5), round(n * 0.2)
    q_exp = max(n - q_linha - q_pot, 1)
    print(f"PLANO PARA {n} PERFIS — equilíbrio entre seguir o que deu certo e descobrir estilos novos:")
    print(f"  A. ~{q_linha} pela LINHA APROVADA (sugestões de fechadas/aprovadas/referências)")
    print(f"  B. ~{q_pot} por POTENCIAL ainda não validado (sugestões de achados novos com nota boa)")
    print(f"  C. ~{q_exp} por EXPLORAÇÃO (cidades do interior, lojas/Marcados, hashtags) — aceite")
    print("     estilos diferentes das aprovadas se tiver público real; marque 'exploração' nas observações.\n")

    rng = random.Random()
    sementes = _sementes(con)
    aprovadas = [x for x in sementes if not x[1]["referencia"] and x[1]["status"] != "novo"]
    referencias = [x for x in sementes if x[1]["referencia"]]
    potencial = [x for x in sementes if not x[1]["referencia"] and x[1]["status"] == "novo"]
    # Linha aprovada: até 3 que você aprovou + 2 referências antigas (ou completa com o que houver)
    linha = _sorteio_ponderado(aprovadas, 3, rng)
    linha += _sorteio_ponderado(referencias, 5 - len(linha), rng)
    if len(linha) < 5:
        linha += _sorteio_ponderado([x for x in aprovadas if x not in linha], 5 - len(linha), rng)

    def mostra(lista):
        for prio, r, uso in lista:
            if r["referencia"]:
                tag = f"referência{', resultado ' + r['resultado_nivel'] if r['resultado_nivel'] else ''}"
            else:
                tag = {"novo": "achado, não avaliado"}.get(r["status"], f"aprovada por você ({r['status']})")
            usada = f"já rendeu {uso:.0f}x" if uso >= 1 else "pouco usada"
            print(f"  sugestoes  @{r['username']:<26} [{tag}] {r['cidade'] or ''} ({usada})")
        if not lista:
            print("  (nenhuma ainda)")

    print("== A. Linha aprovada (sorteada entre aprovadas e referências; muda a cada sessão) ==")
    mostra(linha)
    print("\n== B. Potencial: achados novos com nota boa, ainda não avaliados por você ==")
    mostra(_sorteio_ponderado(potencial, 3, rng))

    print("\n== C. Exploração (sorteado para variar a cada sessão) ==")
    fontes = con.execute("SELECT * FROM fontes WHERE ativa=1").fetchall()
    def menos_exploradas(tipo, k):
        grupo = [f for f in fontes if f["tipo"] == tipo]
        if not grupo:
            return []
        menor = min(f["vezes_explorada"] for f in grupo)
        candidatas = [f for f in grupo if f["vezes_explorada"] <= menor + 1]
        return random.sample(candidatas, min(k, len(candidatas)))
    cidades = menos_exploradas("local", 2)
    for f in cidades:
        print(f"  local      {f['valor']:<28} (explorada {f['vezes_explorada']}x) — perfis com localização e lojas da cidade")
    lojas = menos_exploradas("pagina_local", 1)
    for f in lojas:
        print(f"  pagina_local @{f['valor']:<26} (explorada {f['vezes_explorada']}x) — aba Marcados")
    if cidades:
        print(f"  pagina_local (nova)  procure 'boutique {cidades[0]['valor']}' ou 'loja feminina {cidades[0]['valor']}' → aba Marcados")
    for f in menos_exploradas("hashtag", 1) + menos_exploradas("busca", 1):
        print(f"  {f['tipo']:<10} {f['valor']:<28} (explorada {f['vezes_explorada']}x)")


def cmd_exemplos(a):
    """Mostra ao agente exemplos REAIS do gosto do usuário, para calibrar a nota de estilo."""
    con = db.conectar()

    def linha(p):
        partes = [f"@{p['username']}", f"{p['seguidores'] or '?'} seg"]
        if p["cidade"]:
            partes.append(f"{p['cidade']}/{p['uf'] or ''}")
        if p["resultado_nivel"]:
            partes.append(f"resultado {p['resultado_nivel']}")
        if p["lucro_dia"]:
            partes.append(f"R$ {p['lucro_dia']:.0f}/dia")
        txt = " | ".join(partes)
        extra = " · ".join(x for x in (p["bio"], p["publicos"], p["observacoes"]) if x)
        return f"  {txt}\n      {extra[:220]}" if extra else f"  {txt}"

    blocos = [
        ("FECHARAM COM RESULTADO ALTO (o alvo)",
         "SELECT * FROM perfis WHERE resultado_nivel='alto' OR lucro_dia >= 1000 ORDER BY lucro_dia DESC"),
        ("O USUÁRIO DESTACOU COMO MUITO BONS (referência 'gostamos')",
         "SELECT * FROM perfis WHERE referencia='gostamos' ORDER BY atualizado_em DESC"),
        ("FECHARAM COM RESULTADO MÉDIO",
         "SELECT * FROM perfis WHERE resultado_nivel='medio' ORDER BY atualizado_em DESC LIMIT 8"),
        ("O USUÁRIO APROVOU RECENTEMENTE (siga esta linha)",
         "SELECT * FROM perfis WHERE referencia IS NULL AND status IN "
         "('aprovado','contatado','respondeu','negociando','fechado','recusou','sem_resposta') "
         "AND COALESCE(origem,'') != 'manual' ORDER BY atualizado_em DESC LIMIT 12"),
        ("O USUÁRIO DESCARTOU (evite este tipo)",
         "SELECT * FROM perfis WHERE status='descartado' ORDER BY atualizado_em DESC LIMIT 10"),
    ]
    for titulo, sql in blocos:
        rows = con.execute(sql).fetchall()
        if rows:
            print(f"== {titulo} ({len(rows)}) ==")
            for r in rows:
                print(linha(r))
            print()


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
        con.execute("UPDATE sessoes SET fim=? WHERE fim IS NULL", (db.agora(),))  # fecha sessões esquecidas
        cur = con.execute("INSERT INTO sessoes(inicio) VALUES(?)", (db.agora(),))
        con.commit()
        seguranca.atividade(con, "buscando")
        print(f"sessao={cur.lastrowid}")
        cmd_hoje(a)
    else:
        sid = a.id or con.execute("SELECT MAX(id) FROM sessoes").fetchone()[0]
        con.execute("UPDATE sessoes SET fim=?, perfis_visitados=?, perfis_salvos=?, nota=? WHERE id=?",
                    (db.agora(), a.visitados, a.salvos, a.nota, sid))
        con.commit()
        seguranca.atividade(con, "parado")
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
    import socket
    import threading
    import time
    import urllib.request
    import webbrowser

    url = f"http://localhost:{a.porta}"

    def responde():
        try:
            with urllib.request.urlopen(url + "/api/versao", timeout=2) as r:
                return r.status == 200
        except Exception:
            return False

    # Porta ocupada? Se for um PropSec já aberto, só abre o navegador nele.
    with socket.socket() as s:
        ocupada = s.connect_ex(("127.0.0.1", a.porta)) == 0
    if ocupada:
        if responde():
            print(f"O painel já está aberto em {url}. Abrindo o navegador.")
            if not a.sem_navegador:
                webbrowser.open(url)
            return
        sys.exit(f"ERRO: outro programa está usando a porta {a.porta}. Feche esse programa "
                 f"ou rode: python propsec.py servidor --porta 8010")

    def abrir_quando_pronto():
        for _ in range(60):  # espera o painel responder (até ~30 s) e só então abre o navegador
            if responde():
                print(f"\nPainel pronto: {url}  (deixe esta janela aberta; para fechar o painel, feche a janela)")
                if not a.sem_navegador:
                    webbrowser.open(url)
                return
            time.sleep(0.5)
        print("AVISO: o painel demorou para responder. Veja as mensagens acima.")

    threading.Thread(target=abrir_quando_pronto, daemon=True).start()
    import uvicorn
    print(f"Iniciando o painel em {url} ...")
    uvicorn.run("app.web:app", host="127.0.0.1", port=a.porta, log_level="warning")


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
    s = sub.add_parser("fonte"); s.add_argument("tipo", choices=["sugestoes", "pagina_local", "hashtag", "local", "busca", "explorar", "similar", "achado", "comentarios"])
    s.add_argument("valor"); s.add_argument("--vistos", type=int, default=0); s.add_argument("--nota")
    s.set_defaults(f=cmd_fonte)
    s = sub.add_parser("semear"); s.set_defaults(f=cmd_semear)
    s = sub.add_parser("exemplos"); s.set_defaults(f=cmd_exemplos)
    s = sub.add_parser("contatados"); s.add_argument("usernames", nargs="*")
    s.add_argument("--arquivo", help="arquivo .txt com os @ (um por linha ou separados por espaço)")
    s.set_defaults(f=cmd_contatados)
    s = sub.add_parser("proximas-fontes"); s.add_argument("perfis", type=int, nargs="?", default=20,
                                                         help="quantos perfis a sessão vai buscar")
    s.add_argument("-n", type=int, help=argparse.SUPPRESS); s.set_defaults(f=cmd_proximas_fontes)
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
    s = sub.add_parser("servidor"); s.add_argument("--porta", type=int, default=8000)
    s.add_argument("--sem-navegador", action="store_true"); s.set_defaults(f=cmd_servidor)

    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
