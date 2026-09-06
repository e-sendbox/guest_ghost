"""Юнит-тесты монолита (шаг 0): ping, create_hotel (успех), create_hotel (валидация).

Тестовая БД — отдельный файл (tmp), чтобы не засорять боевую.
Монолит собирается как в frontend/main.py: Mount('/api', fastapi_app).
"""

import json

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount

from backend.db.connection import connect
from backend.db.schema import create_schema
from backend.main import create_app


@pytest.fixture()
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = connect(db_path)
    create_schema(conn)
    conn.close()

    config = {
        "db": {"path": db_path},
        "app": {"mode": "monolith", "port": 8080, "title": "Guest Ghost"},
        "logging": {"level": "DEBUG", "log_dir": "logs"},
    }
    app = create_app(config)
    monolith = Mount("/api", app=app)
    return TestClient(monolith)


def test_ping(client):
    resp = client.get("/api/ping")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_hotel_success(client):
    data = {
        "name": "Замок Тьмы",
        "description": "Старинный замок с подвалом",
        "characteristics": {"освещение": "светло", "уровень шума": "низкий"},
        "restrictions": ["без котов"],
        "rooms": [{"free_date": "2026-09-01"}, {"free_date": "2026-09-01"}],
    }
    resp = client.post("/api/hotels", json=data)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Замок Тьмы"


def test_create_hotel_db_content(client, tmp_path):
    """После create_hotel: дом в hotel_card, номера в hotel_rooms, характеристики в каталог."""
    data = {
        "name": "Замок Тьмы",
        "description": "Старинный замок с подвалом",
        "characteristics": {"освещение": "светло", "уровень шума": "низкий"},
        "restrictions": ["без котов"],
        "rooms": [{"free_date": "2026-09-01"}, {"free_date": "2026-09-01"}],
    }
    resp = client.post("/api/hotels", json=data)
    assert resp.status_code == 200

    conn = connect(str(tmp_path / "test.db"))
    try:
        card = conn.execute("SELECT * FROM hotel_card WHERE name = ?", ("Замок Тьмы",)).fetchone()
        assert card is not None
        assert json.loads(card["characteristics"]) == {"освещение": "светло", "уровень шума": "низкий"}
        assert json.loads(card["restrictions"]) == ["без котов"]

        rooms = conn.execute("SELECT * FROM hotel_rooms WHERE hotel_id = ?", (card["id"],)).fetchall()
        assert len(rooms) == 2
        assert all(r["free_date"] == "2026-09-01" for r in rooms)

        chars = {r["name"] for r in conn.execute("SELECT name FROM hotel_characteristic")}
        assert {"освещение", "уровень шума"} <= chars
    finally:
        conn.close()


def test_characteristics_catalog(client):
    """Каталог пуст → после create_hotel содержит новые характеристики."""
    resp = client.get("/api/characteristics")
    assert resp.status_code == 200
    assert resp.json() == {"characteristics": []}

    data = {
        "name": "Замок Тьмы",
        "description": "Старинный замок с подвалом",
        "characteristics": {"освещение": "светло", "уровень шума": "низкий"},
        "restrictions": ["без котов"],
        "rooms": [{"free_date": "2026-09-01"}],
    }
    resp = client.post("/api/hotels", json=data)
    assert resp.status_code == 200

    resp = client.get("/api/characteristics")
    assert resp.status_code == 200
    assert set(resp.json()["characteristics"]) == {"освещение", "уровень шума"}


def test_create_hotel_validation(client):
    data = {
        "name": "",
        "description": "",
        "characteristics": {},
        "restrictions": [],
        "rooms": [],
    }
    resp = client.post("/api/hotels", json=data)
    assert resp.status_code == 400


def test_get_hotels_empty(client):
    """GET /api/hotels: пустой список."""
    resp = client.get("/api/hotels")
    assert resp.status_code == 200
    assert resp.json() == {"hotels": []}


def test_get_hotels_list(client, tmp_path):
    """GET /api/hotels: дома с полями для карточек (total_rooms/free_rooms)."""
    data = {
        "name": "Замок Тьмы",
        "description": "Старинный замок с подвалом",
        "characteristics": {"освещение": "светло", "уровень шума": "низкий"},
        "restrictions": ["без котов"],
        "rooms": [{"free_date": "2026-09-01"}, {"free_date": "2026-09-05"}],
    }
    resp = client.post("/api/hotels", json=data)
    assert resp.status_code == 200

    # занять один номер (reserved=1) — доступных станет 1
    conn = connect(str(tmp_path / "test.db"))
    conn.execute("UPDATE hotel_rooms SET reserved = 1 WHERE id = (SELECT MIN(id) FROM hotel_rooms)")
    conn.commit()
    conn.close()

    resp = client.get("/api/hotels")
    assert resp.status_code == 200
    hotels = resp.json()["hotels"]
    assert len(hotels) == 1
    h = hotels[0]
    assert h["name"] == "Замок Тьмы"
    assert h["description"] == "Старинный замок с подвалом"
    assert h["characteristics"] == {"освещение": "светло", "уровень шума": "низкий"}
    assert h["restrictions"] == ["без котов"]
    assert h["total_rooms"] == 2
    assert h["free_rooms"] == 1


def test_create_request_success(client):
    data = {
        "name": "Беспокойный дух",
        "anxiety": 0.7,
        "requirements": {"люблю сырость": "очень", "тишина": "нужна"},
        "preferences": "Без котов и пылесосов",
        "deadline_date": "2026-10-31",
    }
    resp = client.post("/api/ghosts", json=data)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Беспокойный дух"


def test_create_request_db_content(client, tmp_path):
    """После create_request: заявка в ghost_request (status='free'), требования в каталог."""
    data = {
        "name": "Беспокойный дух",
        "anxiety": 0.7,
        "requirements": {"люблю сырость": "очень", "тишина": "нужна"},
        "preferences": "Без котов и пылесосов",
        "deadline_date": "2026-10-31",
    }
    resp = client.post("/api/ghosts", json=data)
    assert resp.status_code == 200

    conn = connect(str(tmp_path / "test.db"))
    try:
        req = conn.execute("SELECT * FROM ghost_request WHERE name = ?", ("Беспокойный дух",)).fetchone()
        assert req is not None
        assert req["anxiety"] == 0.7
        assert json.loads(req["requirements"]) == {"люблю сырость": "очень", "тишина": "нужна"}
        assert req["preferences"] == "Без котов и пылесосов"
        assert req["deadline_date"] == "2026-10-31"
        assert req["status"] == "free"
        assert req["free_date"] is not None   # дата перехода в «не заселен» записана при создании

        reqs = {r["name"] for r in conn.execute("SELECT name FROM ghost_requirement")}
        assert {"люблю сырость", "тишина"} <= reqs
    finally:
        conn.close()


def test_requirements_catalog(client):
    """Каталог требований пуст → после create_request содержит новые."""
    resp = client.get("/api/requirements")
    assert resp.status_code == 200
    assert resp.json() == {"requirements": []}

    data = {
        "name": "Беспокойный дух",
        "anxiety": 0.5,
        "requirements": {"люблю сырость": "очень", "тишина": "нужна"},
        "preferences": "Пожелания",
        "deadline_date": "2026-10-31",
    }
    resp = client.post("/api/ghosts", json=data)
    assert resp.status_code == 200

    resp = client.get("/api/requirements")
    assert resp.status_code == 200
    assert set(resp.json()["requirements"]) == {"люблю сырость", "тишина"}


def test_create_request_validation(client):
    data = {
        "name": "",
        "anxiety": None,
        "requirements": {},
        "preferences": "",
        "deadline_date": "",
    }
    resp = client.post("/api/ghosts", json=data)
    assert resp.status_code == 400


def test_get_requests_empty(client):
    """GET /api/ghosts на пустой БД → пустой список."""
    resp = client.get("/api/ghosts")
    assert resp.status_code == 200
    assert resp.json() == {"requests": []}


def test_get_requests_with_data(client, tmp_path):
    """GET /api/ghosts: заявка с полями для карточки; reserved → имя дома по home_id."""
    # заявка в статусе free
    data = {
        "name": "Беспокойный дух",
        "anxiety": 0.7,
        "requirements": {"люблю сырость": "очень"},
        "preferences": "Пожелания",
        "deadline_date": "2026-10-31",
    }
    resp = client.post("/api/ghosts", json=data)
    assert resp.status_code == 200
    req_id = resp.json()["id"]

    resp = client.get("/api/ghosts")
    assert resp.status_code == 200
    requests = resp.json()["requests"]
    assert len(requests) == 1
    r = requests[0]
    assert r["id"] == req_id
    assert r["name"] == "Беспокойный дух"
    assert r["anxiety"] == 0.7
    assert r["deadline_date"] == "2026-10-31"
    assert r["status"] == "free"
    assert r["selection_hotel"] == "[]"
    assert r["comment"] is None
    assert r["hotel_name"] is None

    # сделать заявку заселенной: поместить home_id на дом
    conn = connect(str(tmp_path / "test.db"))
    try:
        cur = conn.execute("INSERT INTO hotel_card (name, description, characteristics, restrictions) VALUES (?, ?, ?, ?)",
                           ("Замок Тьмы", "Описание", '{}', '[]'))
        home_id = cur.lastrowid
        conn.execute("UPDATE ghost_request SET home_id = ?, status = 'reserved' WHERE id = ?", (home_id, req_id))
        conn.commit()
    finally:
        conn.close()

    resp = client.get("/api/ghosts")
    requests = resp.json()["requests"]
    r = requests[0]
    assert r["status"] == "reserved"
    assert r["home_id"] == home_id
    assert r["hotel_name"] == "Замок Тьмы"



# ---------- Шаг 4: обогащение (мок LLM и эмбеддинга) ----------

class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def chat(self, messages, timeout=60):
        self.calls += 1
        if self._responses:
            return self._responses.pop(0)
        raise RuntimeError("LLM не отвечает")


class FakeEmbedder:
    def __init__(self, dim=768):
        self.dim = dim

    def embed(self, texts):
        return [[0.1] * self.dim for _ in texts]


def _enrich_config(tmp_path):
    return {
        "db": {"path": str(tmp_path / "test.db")},
        "llm": {"ollama": {"base_url": "https://ollama.com", "model": "m", "api_key_env": "OLLAMA_API_KEY", "temperature": 0.1}},
        "embedding": {"url": "http://localhost:11434", "model": "m"},
    }


def test_enrich_hotel_success(tmp_path, monkeypatch):
    """Обогащение дома: теги в hotel_card.tags, вектор в hotel_card_emb."""
    from backend.services import enrich_service

    monkeypatch.setattr(enrich_service, "LLMClient", lambda config: FakeLLM(['["освещение: светло", "тишина"]']))
    monkeypatch.setattr(enrich_service, "EmbeddingClient", lambda config: FakeEmbedder())

    config = _enrich_config(tmp_path)
    conn = connect(config["db"]["path"])
    create_schema(conn)
    cur = conn.execute("INSERT INTO hotel_card (name, description, characteristics, restrictions) VALUES (?, ?, ?, ?)",
                       ("Замок", "Тёмный замок", '{"освещение": "светло"}', '[]'))
    card_id = cur.lastrowid
    conn.commit()
    conn.close()

    status = enrich_service.enrich(config, "hotel", card_id, {
        "name": "Замок", "description": "Тёмный замок",
        "characteristics": {"освещение": "светло"}, "restrictions": [],
    })
    assert status == "success"

    conn = connect(config["db"]["path"])
    row = conn.execute("SELECT tags FROM hotel_card WHERE id = ?", (card_id,)).fetchone()
    assert json.loads(row["tags"]) == ["освещение: светло", "тишина"]
    emb = conn.execute("SELECT vec_length(embedding) AS d FROM hotel_card_emb WHERE hotel_card_id = ?", (card_id,)).fetchone()
    assert emb["d"] == 768
    conn.close()


def test_enrich_ghost_success(tmp_path, monkeypatch):
    """Обогащение заявки: теги в ghost_request.tags, вектор в ghost_request_emb."""
    from backend.services import enrich_service

    monkeypatch.setattr(enrich_service, "LLMClient", lambda config: FakeLLM(['["сырость", "тишина"]']))
    monkeypatch.setattr(enrich_service, "EmbeddingClient", lambda config: FakeEmbedder())

    config = _enrich_config(tmp_path)
    conn = connect(config["db"]["path"])
    create_schema(conn)
    cur = conn.execute(
        "INSERT INTO ghost_request (name, anxiety, requirements, preferences, deadline_date, status) VALUES (?, ?, ?, ?, ?, 'free')",
        ("Дух", 0.5, '{"сырость": "очень"}', "Пожелания", "2026-10-31"),
    )
    req_id = cur.lastrowid
    conn.commit()
    conn.close()

    status = enrich_service.enrich(config, "ghost", req_id, {
        "name": "Дух", "requirements": {"сырость": "очень"}, "preferences": "Пожелания",
    })
    assert status == "success"

    conn = connect(config["db"]["path"])
    row = conn.execute("SELECT tags FROM ghost_request WHERE id = ?", (req_id,)).fetchone()
    assert json.loads(row["tags"]) == ["сырость", "тишина"]
    emb = conn.execute("SELECT vec_length(embedding) AS d FROM ghost_request_emb WHERE ghost_request_id = ?", (req_id,)).fetchone()
    assert emb["d"] == 768
    conn.close()


def test_enrich_retries_then_success(tmp_path, monkeypatch):
    """Невалидный ответ LLM → ретраи → успех на 2-й попытке."""
    from backend.services import enrich_service

    fake = FakeLLM(["не json", '["тег"]'])
    monkeypatch.setattr(enrich_service, "LLMClient", lambda config: fake)
    monkeypatch.setattr(enrich_service, "EmbeddingClient", lambda config: FakeEmbedder())
    monkeypatch.setattr(enrich_service, "RETRY_DELAY", 0)

    config = _enrich_config(tmp_path)
    conn = connect(config["db"]["path"])
    create_schema(conn)
    cur = conn.execute("INSERT INTO hotel_card (name, description, characteristics, restrictions) VALUES (?, ?, ?, ?)",
                       ("Замок", "Описание", '{}', '[]'))
    card_id = cur.lastrowid
    conn.commit()
    conn.close()

    status = enrich_service.enrich(config, "hotel", card_id, {"name": "Замок"})
    assert status == "success"
    assert fake.calls == 2


def test_enrich_fails_after_retries(tmp_path, monkeypatch):
    """LLM всё время невалиден → "LLM error" после 3 попыток."""
    from backend.services import enrich_service

    fake = FakeLLM(["не json", "не json", "не json"])
    monkeypatch.setattr(enrich_service, "LLMClient", lambda config: fake)
    monkeypatch.setattr(enrich_service, "EmbeddingClient", lambda config: FakeEmbedder())
    monkeypatch.setattr(enrich_service, "RETRY_DELAY", 0)

    config = _enrich_config(tmp_path)
    conn = connect(config["db"]["path"])
    create_schema(conn)
    cur = conn.execute("INSERT INTO hotel_card (name, description, characteristics, restrictions) VALUES (?, ?, ?, ?)",
                       ("Замок", "Описание", '{}', '[]'))
    card_id = cur.lastrowid
    conn.commit()
    conn.close()

    status = enrich_service.enrich(config, "hotel", card_id, {"name": "Замок"})
    assert status == "LLM error"
    assert fake.calls == 3


# ---------- Шаг 6: подбор вариантов (мок cosine/LLM) ----------

def _insert_house(conn, name, restrictions="[]", tags="[]", rooms=None):
    cur = conn.execute("INSERT INTO hotel_card (name, description, characteristics, restrictions, tags) VALUES (?, ?, '{}', ?, ?)",
                       (name, "Описание", restrictions, tags))
    home_id = cur.lastrowid
    for free_date in (rooms or ["2026-09-01"]):
        conn.execute("INSERT INTO hotel_rooms (hotel_id, free_date) VALUES (?, ?)", (home_id, free_date))
    return home_id


def _insert_ghost(conn, name, anxiety, deadline, reqs='{"сырость": "очень"}', prefs="Пожелания"):
    cur = conn.execute(
        "INSERT INTO ghost_request (name, anxiety, requirements, preferences, deadline_date, status) VALUES (?, ?, ?, ?, ?, 'free')",
        (name, anxiety, reqs, prefs, deadline))
    return cur.lastrowid


def test_match_formula():
    """Формула match_percent: порог, идеальное, отрицательное → 0, an >= 1."""
    from backend.services import search_service
    assert search_service._match_percent(0.3, 0.3) == 0      # на пороге
    assert search_service._match_percent(0.3, 1.0) == 100    # идеально
    assert search_service._match_percent(0.3, 0.65) == 50    # (0.65-0.3)/(0.7)*100
    assert search_service._match_percent(0.3, 0.2) == 0      # ниже порога → 0
    assert search_service._match_percent(0.8, 0.9) == 50     # тревожное
    assert search_service._match_percent(1.0, 1.0) == 100    # паника, идеально
    assert search_service._match_percent(1.0, 0.5) == 0      # паника, не идеально


def test_run_search_no_requests(tmp_path):
    """Нет заявок в статусе free → {"no_requests": True}."""
    from backend.services import search_service
    config = _enrich_config(tmp_path)
    conn = connect(config["db"]["path"])
    create_schema(conn)
    conn.close()

    result = search_service.run_search(config)
    assert result["no_requests"] is True


def test_run_search_success(tmp_path, monkeypatch):
    """Заявка free обрабатывается: дома по датам, косинус мок, LLM комментирует, запись."""
    from backend.services import search_service

    config = _enrich_config(tmp_path)
    conn = connect(config["db"]["path"])
    create_schema(conn)
    home1 = _insert_house(conn, "Замок Тьмы", rooms=["2026-09-01"])
    home2 = _insert_house(conn, "Особняк", rooms=["2026-09-10"])
    ghost_id = _insert_ghost(conn, "Барсук", 0.3, "2026-09-15")
    conn.commit()
    conn.close()

    # мок косинуса: дом1 → 0.65 (выше порога → 50%), дом2 → 0.2 (ниже порога → 0%)
    def fake_cosine(conn, gid, hid):
        return {home1: 0.65, home2: 0.20}[hid]

    monkeypatch.setattr(search_service, "_cosine_sim", fake_cosine)
    monkeypatch.setattr(search_service, "LLMClient", lambda config: FakeLLM([
        json.dumps([{"home_id": home1, "comment": "Подходит по сырости."},
                    {"home_id": home2, "comment": "Не подходит: скрипуч."}], ensure_ascii=False)
    ]))

    result = search_service.run_search(config)
    assert result["processed"] == 1

    conn = connect(config["db"]["path"])
    row = conn.execute("SELECT id, name, anxiety, requirements, preferences, deadline_date, home_id, match_percent, status, selection_hotel, comment, chosen_date FROM ghost_request WHERE id = ?", (ghost_id,)).fetchone()
    assert row["status"] == "chosen"
    assert row["home_id"] == str(home1)   # лучший дом
    assert row["match_percent"] == 50
    assert row["chosen_date"] is not None   # дата перехода в «подобран дом» записана
    sel = json.loads(row["selection_hotel"])
    assert len(sel) == 2
    assert sel[0]["home_id"] == home1
    assert sel[0]["match_percent"] == 50
    assert sel[1]["home_id"] == home2
    assert sel[1]["match_percent"] == 0
    assert "Подходит" in sel[0]["comment"]
    assert "Не подходит" in sel[1]["comment"]
    conn.close()


def test_run_search_no_dates(tmp_path, monkeypatch):
    """Дом с поздней датой не проходит фильтр → comment = "нет подходящих дат"."""
    from backend.services import search_service

    config = _enrich_config(tmp_path)
    conn = connect(config["db"]["path"])
    create_schema(conn)
    _insert_house(conn, "Замок", rooms=["2026-10-01"])   # позже дедлайна
    ghost_id = _insert_ghost(conn, "Дух", 0.5, "2026-09-01")
    conn.commit()
    conn.close()

    result = search_service.run_search(config)
    assert result["processed"] == 1

    conn = connect(config["db"]["path"])
    conn.row_factory = None
    row = conn.execute("SELECT comment, selection_hotel FROM ghost_request WHERE id = ?", (ghost_id,)).fetchone()
    assert row[0] == "нет подходящих дат"
    assert row[1] == "[]"
    conn.close()


def test_run_search_all_zero(tmp_path, monkeypatch):
    """Все дома прошли фильтр дат, но косинус ниже порога → home_id не пишем (NULL)."""
    from backend.services import search_service

    config = _enrich_config(tmp_path)
    conn = connect(config["db"]["path"])
    create_schema(conn)
    home1 = _insert_house(conn, "Замок Тьмы", rooms=["2026-09-01"])
    home2 = _insert_house(conn, "Особняк", rooms=["2026-09-10"])
    ghost_id = _insert_ghost(conn, "Барсук", 0.8, "2026-09-15")
    conn.commit()
    conn.close()

    # мок косинуса: оба дома ниже порога (an=0.8) → match_percent = 0
    def fake_cosine(conn, gid, hid):
        return {home1: 0.5, home2: 0.2}[hid]

    monkeypatch.setattr(search_service, "_cosine_sim", fake_cosine)
    monkeypatch.setattr(search_service, "LLMClient", lambda config: FakeLLM([
        json.dumps([{"home_id": home1, "comment": "Не подходит: слишком светло."},
                    {"home_id": home2, "comment": "Не подходит: скрипуч."}], ensure_ascii=False)
    ]))

    result = search_service.run_search(config)
    assert result["processed"] == 1

    conn = connect(config["db"]["path"])
    row = conn.execute("SELECT home_id, match_percent, status, selection_hotel, comment FROM ghost_request WHERE id = ?", (ghost_id,)).fetchone()
    assert row["status"] == "chosen"
    assert row["home_id"] is None          # лучший дом не пишем
    assert row["match_percent"] == 0
    assert row["comment"] is None          # «нет подходящих домов» больше не пишем
    sel = json.loads(row["selection_hotel"])
    assert len(sel) == 2
    assert all(it["match_percent"] == 0 for it in sel)
    assert "Не подходит" in sel[0]["comment"]
    conn.close()


# ---------- Шаг 5.1: перевыбор дома и сброс заявки ----------

def _seed_request_with_selection(client, tmp_path):
    """Заявка chosen с selection_hotel из двух домов (match 50 и 0)."""
    conn = connect(str(tmp_path / "test.db"))
    try:
        cur = conn.execute("INSERT INTO hotel_card (name, description, characteristics, restrictions) VALUES (?, ?, ?, ?)",
                           ("Замок Тьмы", "Описание", '{}', '[]'))
        home1 = cur.lastrowid
        cur = conn.execute("INSERT INTO hotel_card (name, description, characteristics, restrictions) VALUES (?, ?, ?, ?)",
                           ("Особняк", "Описание", '{}', '[]'))
        home2 = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO ghost_request (name, anxiety, requirements, preferences, deadline_date, status, home_id, match_percent, selection_hotel) "
            "VALUES (?, ?, ?, ?, ?, 'chosen', ?, ?, ?)",
            ("Барсук", 0.3, '{"сырость": "очень"}', "Пожелания", "2026-09-15", home1, 50,
             json.dumps([
                 {"home_id": home1, "name": "Замок Тьмы", "free_date": "2026-09-01", "match_percent": 50, "comment": "Подходит."},
                 {"home_id": home2, "name": "Особняк", "free_date": "2026-09-10", "match_percent": 0, "comment": "Не подходит."},
             ], ensure_ascii=False)))
        req_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return req_id, home1, home2


def test_select_home_success(client, tmp_path):
    """Перевыбор: home_id и match_percent обновляются из selection_hotel."""
    req_id, home1, home2 = _seed_request_with_selection(client, tmp_path)

    resp = client.post(f"/api/ghosts/{req_id}/select", json={"home_id": home2})
    assert resp.status_code == 200
    assert resp.json()["home_id"] == home2
    assert resp.json()["match_percent"] == 0

    conn = connect(str(tmp_path / "test.db"))
    row = conn.execute("SELECT home_id, match_percent, status FROM ghost_request WHERE id = ?", (req_id,)).fetchone()
    assert row["home_id"] == str(home2)
    assert row["match_percent"] == 0
    assert row["status"] == "chosen"   # статус не меняем
    conn.close()


def test_select_home_not_in_selection(client, tmp_path):
    """home_id нет в selection_hotel → 400."""
    req_id, home1, home2 = _seed_request_with_selection(client, tmp_path)

    resp = client.post(f"/api/ghosts/{req_id}/select", json={"home_id": 999})
    assert resp.status_code == 400


def test_reset_request(client, tmp_path):
    """Сброс: status=free, home_id/match_percent/selection_hotel/comment/chosen_date обнулены."""
    req_id, home1, home2 = _seed_request_with_selection(client, tmp_path)
    conn = connect(str(tmp_path / "test.db"))
    conn.execute("UPDATE ghost_request SET comment = 'нет подходящих домов', chosen_date = '2026-09-01 10:00:00' WHERE id = ?", (req_id,))
    conn.commit()
    conn.close()

    resp = client.post(f"/api/ghosts/{req_id}/reset")
    assert resp.status_code == 200
    assert resp.json()["status"] == "free"

    conn = connect(str(tmp_path / "test.db"))
    row = conn.execute("SELECT status, home_id, match_percent, selection_hotel, comment, chosen_date FROM ghost_request WHERE id = ?", (req_id,)).fetchone()
    assert row["status"] == "free"
    assert row["home_id"] is None
    assert row["match_percent"] is None
    assert row["selection_hotel"] == "[]"
    assert row["comment"] is None
    assert row["chosen_date"] is None   # дата «подобран дом» стёрта при сбросе
    conn.close()


# ---------- Шаг 7: заселение приведений ----------

def _seed_booking_data(client, tmp_path):
    """Два дома с номерами, две заявки chosen (home_id на дома)."""
    conn = connect(str(tmp_path / "test.db"))
    try:
        cur = conn.execute("INSERT INTO hotel_card (name, description, characteristics, restrictions) VALUES (?, ?, ?, ?)",
                           ("Замок Тьмы", "Описание", '{}', '[]'))
        home1 = cur.lastrowid
        cur = conn.execute("INSERT INTO hotel_card (name, description, characteristics, restrictions) VALUES (?, ?, ?, ?)",
                           ("Особняк", "Описание", '{}', '[]'))
        home2 = cur.lastrowid
        r11 = conn.execute("INSERT INTO hotel_rooms (hotel_id, free_date) VALUES (?, ?)", (home1, "2026-09-01")).lastrowid
        r12 = conn.execute("INSERT INTO hotel_rooms (hotel_id, free_date) VALUES (?, ?)", (home1, "2026-09-05")).lastrowid
        r21 = conn.execute("INSERT INTO hotel_rooms (hotel_id, free_date) VALUES (?, ?)", (home2, "2026-09-10")).lastrowid
        cur = conn.execute(
            "INSERT INTO ghost_request (name, anxiety, requirements, preferences, deadline_date, status, home_id) "
            "VALUES (?, ?, ?, ?, ?, 'chosen', ?)",
            ("Барсук", 0.3, '{"сырость": "очень"}', "Пожелания", "2026-09-15", home1))
        req1 = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO ghost_request (name, anxiety, requirements, preferences, deadline_date, status, home_id) "
            "VALUES (?, ?, ?, ?, ?, 'chosen', ?)",
            ("Тихоня", 0.5, '{"тишина": "да"}', "Пожелания", "2026-09-20", home2))
        req2 = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return {"home1": home1, "home2": home2, "r11": r11, "r12": r12, "r21": r21, "req1": req1, "req2": req2}


def test_booking_candidates(client, tmp_path):
    """Кандидаты: только chosen с home_id; номера свободные и с датой <= deadline."""
    d = _seed_booking_data(client, tmp_path)

    resp = client.get("/api/booking/candidates")
    assert resp.status_code == 200
    candidates = resp.json()["candidates"]
    assert len(candidates) == 2

    by_home = {int(g["home_id"]): g for g in candidates}
    g1 = by_home[d["home1"]]
    assert g1["name"] == "Замок Тьмы"
    assert len(g1["requests"]) == 1
    rooms = g1["requests"][0]["rooms"]
    assert [r["id"] for r in rooms] == [d["r11"], d["r12"]]

    # дом с поздней датой (2026-09-10) — заявка с дедлайном 2026-09-20: номер проходит
    g2 = by_home[d["home2"]]
    assert len(g2["requests"][0]["rooms"]) == 1
    assert g2["requests"][0]["rooms"][0]["id"] == d["r21"]


def test_booking_success(client, tmp_path):
    """Бронь: заявки reserved, номера reserved=1 + free_date = фактическая дата заселения."""
    d = _seed_booking_data(client, tmp_path)

    resp = client.post("/api/booking", json={"bookings": [
        {"request_id": d["req1"], "room_id": d["r11"]},
        {"request_id": d["req2"], "room_id": d["r21"]},
    ]})
    assert resp.status_code == 200
    assert resp.json()["booked"] == 2

    conn = connect(str(tmp_path / "test.db"))
    rows = conn.execute("SELECT id, status, reserved_date FROM ghost_request WHERE id IN (?, ?)", (d["req1"], d["req2"])).fetchall()
    assert all(r["status"] == "reserved" for r in rows)
    assert all(r["reserved_date"] is not None for r in rows)   # дата «заселен» записана
    rooms = conn.execute("SELECT id, reserved, free_date FROM hotel_rooms WHERE id IN (?, ?)", (d["r11"], d["r21"])).fetchall()
    assert all(r["reserved"] == 1 for r in rooms)
    # free_date = фактическая дата-время заселения (совпадает с reserved_date заявки)
    by_room = {r["id"]: r for r in rooms}
    by_req = {r["id"]: r for r in rows}
    assert by_room[d["r11"]]["free_date"] == by_req[d["req1"]]["reserved_date"]
    assert by_room[d["r21"]]["free_date"] == by_req[d["req2"]]["reserved_date"]
    conn.close()


def test_no_reserved_without_chosen_date(client, tmp_path):
    """Инвариант: нет заявок с reserved_date, но без chosen_date."""
    d = _seed_booking_data(client, tmp_path)
    conn = connect(str(tmp_path / "test.db"))
    conn.execute("UPDATE ghost_request SET chosen_date = '2026-09-01 10:00:00' WHERE id IN (?, ?)", (d["req1"], d["req2"]))
    conn.commit()
    conn.close()

    resp = client.post("/api/booking", json={"bookings": [
        {"request_id": d["req1"], "room_id": d["r11"]},
        {"request_id": d["req2"], "room_id": d["r21"]},
    ]})
    assert resp.status_code == 200

    conn = connect(str(tmp_path / "test.db"))
    bad = conn.execute(
        "SELECT id FROM ghost_request WHERE reserved_date IS NOT NULL AND chosen_date IS NULL"
    ).fetchall()
    assert bad == []   # у всех заселенных есть дата «подобран дом»
    conn.close()


def test_booking_conflict(client, tmp_path):
    """Занятый номер (уже reserved) → 400, ничего не записано."""
    d = _seed_booking_data(client, tmp_path)
    conn = connect(str(tmp_path / "test.db"))
    conn.execute("UPDATE hotel_rooms SET reserved = 1 WHERE id = ?", (d["r11"],))
    conn.commit()
    conn.close()

    resp = client.post("/api/booking", json={"bookings": [
        {"request_id": d["req1"], "room_id": d["r11"]},
    ]})
    assert resp.status_code == 400

    conn = connect(str(tmp_path / "test.db"))
    row = conn.execute("SELECT status FROM ghost_request WHERE id = ?", (d["req1"],)).fetchone()
    assert row["status"] == "chosen"
    conn.close()


def test_booking_wrong_room(client, tmp_path):
    """Номер не из дома заявки → 400."""
    d = _seed_booking_data(client, tmp_path)

    resp = client.post("/api/booking", json={"bookings": [
        {"request_id": d["req1"], "room_id": d["r21"]},   # r21 — номер Особняка, заявка на Замок
    ]})
    assert resp.status_code == 400


# ---------- Шаг 8: отчёт по заявкам / по домам ----------

def _seed_report_data(client, tmp_path):
    """Дом с номерами, заявки с датами переходов (free/chosen/reserved).

    Даты привязаны к реальному «сегодня» (datetime.now()), т.к. период отчёта
    считается от текущей даты: 1 день = с 00:00 сегодня.
    """
    from datetime import datetime, timedelta
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    conn = connect(str(tmp_path / "test.db"))
    try:
        cur = conn.execute("INSERT INTO hotel_card (name, description, characteristics, restrictions) VALUES (?, ?, ?, ?)",
                           ("Замок Тьмы", "Описание", '{}', '[]'))
        home1 = cur.lastrowid
        cur = conn.execute("INSERT INTO hotel_card (name, description, characteristics, restrictions) VALUES (?, ?, ?, ?)",
                           ("Особняк", "Описание", '{}', '[]'))
        home2 = cur.lastrowid
        r1 = conn.execute("INSERT INTO hotel_rooms (hotel_id, free_date) VALUES (?, ?)", (home1, "2026-09-01")).lastrowid
        r2 = conn.execute("INSERT INTO hotel_rooms (hotel_id, free_date) VALUES (?, ?)", (home1, "2026-09-05")).lastrowid
        r3 = conn.execute("INSERT INTO hotel_rooms (hotel_id, free_date) VALUES (?, ?)", (home2, "2026-09-10")).lastrowid

        # заявка 1: заселена сегодня (в периоде)
        cur = conn.execute(
            "INSERT INTO ghost_request (name, anxiety, requirements, preferences, deadline_date, status, home_id, match_percent, selection_hotel, free_date, chosen_date, reserved_date) "
            "VALUES (?, ?, ?, ?, ?, 'reserved', ?, 50, ?, ?, ?, ?)",
            ("Барсук", 0.3, '{"сырость": "очень"}', "Пожелания", "2026-09-15", home1,
             json.dumps([
                 {"home_id": home1, "name": "Замок Тьмы", "free_date": "2026-09-01", "match_percent": 50, "comment": "ок"},
                 {"home_id": home2, "name": "Особняк", "free_date": "2026-09-10", "match_percent": 10, "comment": "слабо"},
             ]),
             f"{today} 09:00:00", f"{today} 10:00:00", f"{today} 11:00:00"))
        req1 = cur.lastrowid
        # заявка 2: заселена сегодня, match 30
        cur = conn.execute(
            "INSERT INTO ghost_request (name, anxiety, requirements, preferences, deadline_date, status, home_id, match_percent, selection_hotel, free_date, chosen_date, reserved_date) "
            "VALUES (?, ?, ?, ?, ?, 'reserved', ?, 30, ?, ?, ?, ?)",
            ("Тихоня", 0.5, '{"тишина": "да"}', "Пожелания", "2026-09-20", home1,
             json.dumps([
                 {"home_id": home1, "name": "Замок Тьмы", "free_date": "2026-09-05", "match_percent": 30, "comment": "ок"},
                 {"home_id": home2, "name": "Особняк", "free_date": "2026-09-10", "match_percent": 20, "comment": "средне"},
             ]),
             f"{today} 12:00:00", f"{today} 13:00:00", f"{today} 14:00:00"))
        req2 = cur.lastrowid
        # заявка 3: заселена ДО периода (вчера) — должна отсечься при days=1
        cur = conn.execute(
            "INSERT INTO ghost_request (name, anxiety, requirements, preferences, deadline_date, status, home_id, match_percent, free_date, chosen_date, reserved_date) "
            "VALUES (?, ?, ?, ?, ?, 'reserved', ?, 10, ?, ?, ?)",
            ("Старый", 0.7, '{"мрак": "да"}', "Пожелания", "2026-09-10", home2,
             f"{yesterday} 09:00:00", f"{yesterday} 10:00:00", f"{yesterday} 11:00:00"))
        req3 = cur.lastrowid
        # заявка 4: chosen (не заселена) — не попадает в отчёт
        cur = conn.execute(
            "INSERT INTO ghost_request (name, anxiety, requirements, preferences, deadline_date, status, home_id, match_percent, selection_hotel, free_date, chosen_date) "
            "VALUES (?, ?, ?, ?, ?, 'chosen', ?, 20, ?, ?, ?)",
            ("Дух", 0.4, '{"простор": "да"}', "Пожелания", "2026-09-25", home2,
             json.dumps([
                 {"home_id": home2, "name": "Особняк", "free_date": "2026-09-10", "match_percent": 20, "comment": "ок"},
             ]),
             f"{today} 15:00:00", f"{today} 16:00:00"))
        req4 = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return {"home1": home1, "home2": home2, "r1": r1, "r2": r2, "r3": r3,
            "req1": req1, "req2": req2, "req3": req3, "req4": req4}


def test_report_requests(client, tmp_path):
    """Отчёт по заявкам: выборка (все незаселенные + заселенные в периоде), группировка по free_date, воронка."""
    d = _seed_report_data(client, tmp_path)

    resp = client.get("/api/report", params={"mode": "requests", "days": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "requests"
    rows = data["rows"]
    # заявки периода: Барсук (reserved), Тихоня (reserved), Дух (chosen, не заселен);
    # Старый (reserved вчера) отсекается при days=1 — группировка по free_date (сегодня)
    assert len(rows) == 1
    row = rows[0]
    assert row["waiting"] == 3      # все заявки выборки (включая незаселенную Дух)
    assert row["chosen"] == 3       # chosen_date в массиве
    assert row["reserved"] == 2      # reserved_date в массиве
    assert row["no_dates"] == 0
    assert row["no_homes"] == 0


def test_report_requests_no_dates(client, tmp_path):
    """Отчёт по заявкам: проблемные — «нет подходящих дат»."""
    d = _seed_report_data(client, tmp_path)
    conn = connect(str(tmp_path / "test.db"))
    conn.execute(
        "UPDATE ghost_request SET comment = 'нет подходящих дат', selection_hotel = '[]' WHERE id = ?",
        (d["req2"],),
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/report", params={"mode": "requests", "days": 1})
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["no_dates"] == 1


def test_report_requests_no_homes(client, tmp_path):
    """Отчёт по заявкам: проблемные — «нет подходящих домов» (все дома в selection_hotel с 0%)."""
    d = _seed_report_data(client, tmp_path)
    conn = connect(str(tmp_path / "test.db"))
    conn.execute(
        "UPDATE ghost_request SET selection_hotel = ? WHERE id = ?",
        (json.dumps([
            {"home_id": d["home1"], "name": "Замок Тьмы", "free_date": "2026-09-01", "match_percent": 0, "comment": "не подходит"},
            {"home_id": d["home2"], "name": "Особняк", "free_date": "2026-09-10", "match_percent": 0, "comment": "не подходит"},
        ]), d["req4"]),
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/report", params={"mode": "requests", "days": 1})
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["no_homes"] == 1


def test_report_houses(client, tmp_path):
    """Отчёт по домам: места, воронка наполнения, аналитика, динамика."""
    from datetime import datetime
    d = _seed_report_data(client, tmp_path)
    # занять номер r1 в периоде (заселение сегодня)
    conn = connect(str(tmp_path / "test.db"))
    conn.execute("UPDATE hotel_rooms SET reserved = 1, free_date = ? WHERE id = ?",
                 (datetime.now().strftime("%Y-%m-%d 11:00:00"), d["r1"]))
    conn.commit()
    conn.close()

    resp = client.get("/api/report", params={"mode": "houses", "days": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "houses"
    rows = {r["name"]: r for r in data["rows"]}

    # Замок Тьмы: 2 номера, 1 занят в периоде
    zamok = rows["Замок Тьмы"]
    assert zamok["total_rooms"] == 2
    assert zamok["free_start"] == 2      # оба свободны на начало (1 занят в периоде)
    assert zamok["free_end"] == 1        # 1 свободен на конец
    assert zamok["max_match"] == 50
    assert zamok["avg_match"] == 40      # (50+30)/2
    assert zamok["fill_dynamics"] == 50  # 1/2 = 50%

    # Особняк: 1 номер, заявка Дух (chosen, не заселена) → в отчёте, номер свободен
    osobnyak = rows["Особняк"]
    assert osobnyak["total_rooms"] == 1
    assert osobnyak["free_start"] == 1
    assert osobnyak["free_end"] == 1
    assert osobnyak["max_match"] == 20
    assert osobnyak["avg_match"] == 17      # (10+20+20)/3 из selection_hotel (Барсук, Тихоня, Дух)
    assert osobnyak["fill_dynamics"] == 0


def test_report_period_filter(client, tmp_path):
    """Период: заявка, заселенная до начала периода, отсекается."""
    d = _seed_report_data(client, tmp_path)

    resp = client.get("/api/report", params={"mode": "requests", "days": 1})
    rows = resp.json()["rows"]
    total = sum(r["reserved"] for r in rows)
    assert total == 2   # Старый (вчера) не попал

    resp = client.get("/api/report", params={"mode": "requests", "days": 7})
    rows = resp.json()["rows"]
    total = sum(r["reserved"] for r in rows)
    assert total == 3   # Старый попал (7 дней назад)


def test_report_invalid_mode(client):
    """Неизвестный режим → 400."""
    resp = client.get("/api/report", params={"mode": "bogus", "days": 1})
    assert resp.status_code == 400


def test_booking_not_chosen(client, tmp_path):
    """Заявка не в статусе chosen → 400."""
    d = _seed_booking_data(client, tmp_path)
    conn = connect(str(tmp_path / "test.db"))
    conn.execute("UPDATE ghost_request SET status = 'free' WHERE id = ?", (d["req1"],))
    conn.commit()
    conn.close()

    resp = client.post("/api/booking", json={"bookings": [
        {"request_id": d["req1"], "room_id": d["r11"]},
    ]})
    assert resp.status_code == 400


# ---------- Шаг 10: глобальные фильтры ----------

def _seed_filter_data(client, tmp_path):
    """Данные для фильтров: 2 дома, заявки с датами переходов и selection_hotel."""
    d = _seed_report_data(client, tmp_path)
    # Дух (chosen, home2): все дома в selection_hotel с 0% → no_homes
    conn = connect(str(tmp_path / "test.db"))
    conn.execute(
        "UPDATE ghost_request SET selection_hotel = ? WHERE id = ?",
        (json.dumps([
            {"home_id": d["home1"], "name": "Замок Тьмы", "free_date": "2026-09-01", "match_percent": 0, "comment": "не подходит"},
            {"home_id": d["home2"], "name": "Особняк", "free_date": "2026-09-10", "match_percent": 0, "comment": "не подходит"},
        ]), d["req4"]),
    )
    conn.commit()
    conn.close()
    return d


def test_filter_waiting(client, tmp_path):
    """filter=waiting: заявки выборки отчёта за день (все, без доп. условия)."""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    d = _seed_filter_data(client, tmp_path)
    resp = client.get("/api/ghosts", params={"filter": "waiting", "date": today, "period_start": f"{today} 00:00:00"})
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()["requests"]}
    assert ids == {d["req1"], d["req2"], d["req4"]}  # Старый (вчера) отсечён


def test_filter_chosen(client, tmp_path):
    """filter=chosen: + chosen_date IS NOT NULL."""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    d = _seed_filter_data(client, tmp_path)
    resp = client.get("/api/ghosts", params={"filter": "chosen", "date": today, "period_start": f"{today} 00:00:00"})
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()["requests"]}
    assert ids == {d["req1"], d["req2"], d["req4"]}


def test_filter_reserved(client, tmp_path):
    """filter=reserved: + reserved_date IS NOT NULL."""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    d = _seed_filter_data(client, tmp_path)
    resp = client.get("/api/ghosts", params={"filter": "reserved", "date": today, "period_start": f"{today} 00:00:00"})
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()["requests"]}
    assert ids == {d["req1"], d["req2"]}


def test_filter_no_dates(client, tmp_path):
    """filter=no_dates: + comment = 'нет подходящих дат'."""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    d = _seed_filter_data(client, tmp_path)
    conn = connect(str(tmp_path / "test.db"))
    conn.execute("UPDATE ghost_request SET comment = 'нет подходящих дат', selection_hotel = '[]' WHERE id = ?", (d["req2"],))
    conn.commit()
    conn.close()
    resp = client.get("/api/ghosts", params={"filter": "no_dates", "date": today, "period_start": f"{today} 00:00:00"})
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()["requests"]}
    assert ids == {d["req2"]}


def test_filter_no_homes(client, tmp_path):
    """filter=no_homes: selection_hotel непустой, все match_percent = 0."""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    d = _seed_filter_data(client, tmp_path)
    resp = client.get("/api/ghosts", params={"filter": "no_homes", "date": today, "period_start": f"{today} 00:00:00"})
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()["requests"]}
    assert ids == {d["req4"]}


def test_filter_house_dynamics(client, tmp_path):
    """filter=house_dynamics: заявки выборки отчёта с home_id."""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    d = _seed_filter_data(client, tmp_path)
    resp = client.get("/api/ghosts", params={"filter": "house_dynamics", "home_id": d["home1"], "period_start": f"{today} 00:00:00"})
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()["requests"]}
    assert ids == {d["req1"], d["req2"]}


def test_filter_unknown(client):
    """Неизвестный фильтр → 400."""
    resp = client.get("/api/ghosts", params={"filter": "bogus"})
    assert resp.status_code == 400


def test_filter_from_request(client, tmp_path):
    """GET /api/hotels?filter=from_request: только дом заявки."""
    d = _seed_filter_data(client, tmp_path)
    resp = client.get("/api/hotels", params={"filter": "from_request", "request_id": d["req1"]})
    assert resp.status_code == 200
    hotels = resp.json()["hotels"]
    assert len(hotels) == 1
    assert hotels[0]["id"] == d["home1"]

    # заявка без дома → пусто
    conn = connect(str(tmp_path / "test.db"))
    conn.execute("UPDATE ghost_request SET home_id = NULL WHERE id = ?", (d["req4"],))
    conn.commit()
    conn.close()
    resp = client.get("/api/hotels", params={"filter": "from_request", "request_id": d["req4"]})
    assert resp.status_code == 200
    assert resp.json()["hotels"] == []


# ---------- Шаг 12: облачная embedding-модель (Jina) ----------


def test_embedding_client_local(monkeypatch):
    """local-режим: POST {url}/api/embed, без ключа, парсинг embeddings."""
    from backend.clients.embedding_client import EmbeddingClient

    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"embeddings": [[0.1] * 768]}

    def fake_post(url, json=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr("backend.clients.embedding_client.requests.post", fake_post)
    client = EmbeddingClient({"embedding": {"type": "local", "provider": "ollama",
                                            "url": "http://localhost:11434", "model": "m"}})
    vectors = client.embed(["тест"])
    assert len(vectors) == 1 and len(vectors[0]) == 768
    assert captured["url"] == "http://localhost:11434/api/embed"
    assert captured["json"] == {"model": "m", "input": ["тест"]}


def test_embedding_client_jina(monkeypatch):
    """cloud-режим: POST api.jina.ai, Bearer-ключ, normalized: true, парсинг data[].embedding."""
    from backend.clients.embedding_client import EmbeddingClient

    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"embedding": [0.1] * 768}]}

    def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr("backend.clients.embedding_client.requests.post", fake_post)
    monkeypatch.setenv("JINA_API_KEY", "test-key")
    client = EmbeddingClient({"embedding": {"type": "cloud", "provider": "jina",
                                            "url": "https://api.jina.ai/v1/embeddings",
                                            "model": "jina-embeddings-v5-omni-nano",
                                            "api_key_env": "JINA_API_KEY"}})
    vectors = client.embed(["тест"])
    assert len(vectors) == 1 and len(vectors[0]) == 768
    assert captured["url"] == "https://api.jina.ai/v1/embeddings"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["normalized"] is True
    assert captured["json"]["model"] == "jina-embeddings-v5-omni-nano"


def test_embedding_client_jina_no_key(monkeypatch):
    """cloud-режим без ключа в env → RuntimeError."""
    from backend.clients.embedding_client import EmbeddingClient

    monkeypatch.delenv("JINA_API_KEY", raising=False)
    client = EmbeddingClient({"embedding": {"type": "cloud", "provider": "jina"}})
    with pytest.raises(RuntimeError, match="JINA_API_KEY"):
        client.embed(["тест"])


def test_embedding_client_default_cloud():
    """По умолчанию type=cloud, provider=jina."""
    from backend.clients.embedding_client import EmbeddingClient

    client = EmbeddingClient({"embedding": {}})
    assert client.type == "cloud"
    assert client.provider == "jina"
    assert client.model == "jina-embeddings-v5-omni-nano"


def test_embedding_recalc(client, tmp_path, monkeypatch):
    """POST /api/embedding/recalc: пересчёт векторов по непустым tags."""
    from backend.clients import embedding_client as ec_module

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"embedding": [0.2] * 768}]}

    def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        return FakeResp()

    monkeypatch.setattr(ec_module.requests, "post", fake_post)
    monkeypatch.setenv("JINA_API_KEY", "test-key")

    conn = connect(str(tmp_path / "test.db"))
    cur = conn.execute("INSERT INTO hotel_card (name, description, characteristics, restrictions, tags) VALUES (?, ?, ?, ?, ?)",
                       ("Замок", "Описание", '{}', '[]', '["тишина"]'))
    home_id = cur.lastrowid
    cur = conn.execute("INSERT INTO ghost_request (name, anxiety, requirements, preferences, deadline_date, status, tags) VALUES (?, ?, ?, ?, ?, 'free', ?)",
                       ("Дух", 0.5, '{}', "", "2026-10-31", '["сырость"]'))
    req_id = cur.lastrowid
    conn.commit()
    conn.close()

    resp = client.post("/api/embedding/recalc")
    assert resp.status_code == 200
    result = resp.json()
    assert result["processed"] == 2
    assert result["errors"] == 0

    conn = connect(str(tmp_path / "test.db"))
    emb = conn.execute("SELECT vec_length(embedding) AS d FROM hotel_card_emb WHERE hotel_card_id = ?", (home_id,)).fetchone()
    assert emb["d"] == 768
    emb2 = conn.execute("SELECT vec_length(embedding) AS d FROM ghost_request_emb WHERE ghost_request_id = ?", (req_id,)).fetchone()
    assert emb2["d"] == 768
    conn.close()


# ---------- Шаг 13: DevINFO (reset, seed, enrich-эндпоинт) ----------


def test_dev_reset(client, tmp_path):
    """POST /api/dev/reset: все таблицы пустые, схема на месте."""
    conn = connect(str(tmp_path / "test.db"))
    conn.execute("INSERT INTO hotel_card (name, description, characteristics, restrictions) VALUES (?, ?, ?, ?)",
                 ("Замок", "Описание", '{}', '[]'))
    conn.execute("INSERT INTO ghost_request (name, anxiety, requirements, preferences, deadline_date, status) VALUES (?, ?, ?, ?, ?, 'free')",
                 ("Дух", 0.5, '{}', "", "2026-10-31"))
    conn.commit()
    conn.close()

    resp = client.post("/api/dev/reset")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    conn = connect(str(tmp_path / "test.db"))
    for table in ("hotel_card", "hotel_rooms", "hotel_characteristic", "ghost_request", "ghost_requirement"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    conn.close()


def test_dev_seed(client, tmp_path, monkeypatch):
    """POST /api/dev/seed: 5 домов + 5 заявок через API-механизмы + обогащение."""
    from backend.services import dev_service

    class FakeLLM:
        def chat(self, messages, timeout=60):
            return '["тег"]'

    class FakeEmbedder:
        def embed(self, texts):
            return [[0.1] * 768 for _ in texts]

    monkeypatch.setattr(dev_service, "enrich", lambda config, ct, cid, data: "success")
    monkeypatch.setattr("backend.services.enrich_service.LLMClient", lambda config: FakeLLM())
    monkeypatch.setattr("backend.services.enrich_service.EmbeddingClient", lambda config: FakeEmbedder())

    resp = client.post("/api/dev/seed")
    assert resp.status_code == 200
    result = resp.json()
    assert result["hotels"] == 5
    assert result["ghosts"] == 5
    assert result["errors"] == 0

    conn = connect(str(tmp_path / "test.db"))
    assert conn.execute("SELECT COUNT(*) FROM hotel_card").fetchone()[0] == 5
    assert conn.execute("SELECT COUNT(*) FROM ghost_request").fetchone()[0] == 5
    assert conn.execute("SELECT COUNT(*) FROM hotel_rooms").fetchone()[0] > 0
    conn.close()


def test_enrich_endpoint(client, tmp_path, monkeypatch):
    """POST /api/enrich: обёртка над enrich_service.enrich."""
    from backend.services import enrich_service

    monkeypatch.setattr(enrich_service, "LLMClient", lambda config: FakeLLM(['["тишина"]']))
    monkeypatch.setattr(enrich_service, "EmbeddingClient", lambda config: FakeEmbedder())

    conn = connect(str(tmp_path / "test.db"))
    cur = conn.execute("INSERT INTO hotel_card (name, description, characteristics, restrictions) VALUES (?, ?, ?, ?)",
                       ("Замок", "Описание", '{}', '[]'))
    card_id = cur.lastrowid
    conn.commit()
    conn.close()

    resp = client.post("/api/enrich", json={"card_type": "hotel", "card_id": card_id, "data": {"name": "Замок", "description": "Описание"}})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    conn = connect(str(tmp_path / "test.db"))
    emb = conn.execute("SELECT vec_length(embedding) AS d FROM hotel_card_emb WHERE hotel_card_id = ?", (card_id,)).fetchone()
    assert emb["d"] == 768
    conn.close()


# ---------- Шаг 0.2: подстановка env в конфиге ----------

def test_expand_env_default(monkeypatch):
    """${VAR:-default} → default при отсутствии переменной."""
    from utils.env import expand_env

    monkeypatch.delenv("GG_TEST_VAR", raising=False)
    config = expand_env({"port": "${GG_TEST_VAR:-8080}"})
    assert config["port"] == "8080"


def test_expand_env_value(monkeypatch):
    """${VAR:-default} → значение при наличии переменной."""
    from utils.env import expand_env

    monkeypatch.setenv("GG_TEST_VAR", "10000")
    config = expand_env({"port": "${GG_TEST_VAR:-8080}"})
    assert config["port"] == "10000"


def test_expand_env_nested(monkeypatch):
    """Вложенные ключи конфига раскрываются рекурсивно."""
    from utils.env import expand_env

    monkeypatch.setenv("GG_TEST_VAR", "10000")
    config = expand_env({
        "app": {"port": "${GG_TEST_VAR:-8080}", "api_url": "http://localhost:${GG_TEST_VAR:-8080}/api"},
        "list": ["${GG_TEST_VAR:-8080}"],
    })
    assert config["app"]["port"] == "10000"
    assert config["app"]["api_url"] == "http://localhost:10000/api"
    assert config["list"] == ["10000"]


def test_expand_env_no_placeholder(monkeypatch):
    """Строки без ${...} не меняются."""
    from utils.env import expand_env

    config = expand_env({"title": "Guest Ghost", "mode": "monolith"})
    assert config == {"title": "Guest Ghost", "mode": "monolith"}
