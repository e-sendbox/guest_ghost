"""Роуты эмбеддингов (шаг 12): POST /embedding/recalc — пересчёт векторов старых карточек.

Проходит по hotel_card / ghost_request с непустыми tags, пересчитывает векторы
текущим провайдером (embedding.type из config.yaml). LLM не вызывается — теги уже есть.
"""

import json
import logging

from backend.clients.embedding_client import EmbeddingClient
from backend.db.connection import connect

logger = logging.getLogger(__name__)


def _recalc(config: dict) -> dict:
    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    embedder = EmbeddingClient(config)
    conn = connect(db_path)
    processed = 0
    errors = 0
    try:
        hotels = conn.execute(
            "SELECT id, tags FROM hotel_card WHERE tags IS NOT NULL AND tags != '[]'"
        ).fetchall()
        ghosts = conn.execute(
            "SELECT id, tags FROM ghost_request WHERE tags IS NOT NULL AND tags != '[]'"
        ).fetchall()

        for row in hotels:
            try:
                tags = json.loads(row["tags"])
                vector = embedder.embed([", ".join(tags)])[0]
                conn.execute("DELETE FROM hotel_card_emb WHERE hotel_card_id = ?", (row["id"],))
                conn.execute("INSERT INTO hotel_card_emb (hotel_card_id, embedding) VALUES (?, ?)",
                             (row["id"], json.dumps(vector)))
                processed += 1
            except Exception as e:
                errors += 1
                logger.error("recalc: дом id=%s: %s", row["id"], e)

        for row in ghosts:
            try:
                tags = json.loads(row["tags"])
                vector = embedder.embed([", ".join(tags)])[0]
                conn.execute("DELETE FROM ghost_request_emb WHERE ghost_request_id = ?", (row["id"],))
                conn.execute("INSERT INTO ghost_request_emb (ghost_request_id, embedding) VALUES (?, ?)",
                             (row["id"], json.dumps(vector)))
                processed += 1
            except Exception as e:
                errors += 1
                logger.error("recalc: заявка id=%s: %s", row["id"], e)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    logger.info("recalc: пересчитано векторов=%s, ошибок=%s", processed, errors)
    return {"processed": processed, "errors": errors}


def register(app):
    @app.post("/embedding/recalc")
    def recalc():
        config = app.state.config
        return _recalc(config)
