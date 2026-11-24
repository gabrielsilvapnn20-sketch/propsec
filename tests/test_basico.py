import os, tempfile

os.environ["PROPSEC_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient  # noqa: E402
from app import aprendizado, db  # noqa: E402
from app.web import app  # noqa: E402


def test_fluxo():
    con = db.conectar()
    bom, _ = db.salvar_perfil(con, {"username": "@Boa", "seguidores": 5000, "media_views_reels": 4500,
                                     "media_curtidas": 400, "media_comentarios": 30, "stories_ativos": True, "uf": "ma"})
    ruim, _ = db.salvar_perfil(con, {"username": "https://instagram.com/ruim/", "seguidores": 5000,
                                      "media_views_reels": 300, "media_curtidas": 40, "suspeita_compra": 1})
    s = {r["username"]: r["score"] for r in con.execute("SELECT username, score FROM perfis")}
    assert s["boa"] > 70 > 30 > s["ruim"]
    # atualizar sem apagar campos
    db.salvar_perfil(con, {"username": "boa", "cidade": "Codó"})
    p = db.buscar_perfil(con, "boa")
    assert p["seguidores"] == 5000 and p["cidade"] == "Codó" and p["uf"] == "MA"
    db.mudar_status(con, bom, "contatado"); db.mudar_status(con, bom, "recusou")
    assert len(con.execute("SELECT * FROM eventos WHERE perfil_id=?", (bom,)).fetchall()) == 3
    rel = aprendizado.recalibrar(con, aplicar=False)
    assert rel["amostras"] == 0  # recusou não é rótulo
    c = TestClient(app)
    for u in ["/", "/fila", "/perfis", "/pipeline", "/p/boa", "/referencias", "/aprendizado", "/exportar.csv"]:
        assert c.get(u).status_code == 200, u
