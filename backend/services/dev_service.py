"""Сервис DevINFO (шаг 13): reset_db() — обнуление БД, seed_demo() — предзаполнение.

seed_demo() добавляет 5 домов и 5 заявок через те же механизмы, что и формы:
create_hotel()/create_request() (валидация, каталог) + enrich() (LLM-теги, эмбеддинг).
"""

import logging

from backend.db.connection import connect
from backend.services.enrich_service import enrich
from backend.services.ghost_service import create_request
from backend.services.hotel_service import create_hotel
from demo_data.seed_data import GHOSTS, HOTELS

logger = logging.getLogger(__name__)

TABLES = [
    "hotel_card_emb",
    "ghost_request_emb",
    "hotel_rooms",
    "hotel_characteristic",
    "ghost_requirement",
    "ghost_request",
    "hotel_card",
]


def reset_db(config: dict) -> dict:
    """Очистить все таблицы (схема остаётся, данные пустые)."""
    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    try:
        for table in TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    logger.info("dev: БД обнулена")
    return {"status": "ok"}


def seed_demo(config: dict) -> dict:
    """Предзаполнить БД: 5 домов + 5 заявок через API-механизмы + обогащение."""
    hotels = 0
    ghosts = 0
    errors = 0

    for h in HOTELS:
        try:
            result = create_hotel(config, {
                "name": h["name"],
                "description": h["description"],
                "characteristics": h["characteristics"],
                "restrictions": [r.strip() for r in h["restrictions"].split(",") if r.strip()],
                "rooms": [{"free_date": iso} for (iso,) in h["rooms"]],
            })
            enrich(config, "hotel", result["id"], {
                "name": h["name"],
                "description": h["description"],
                "characteristics": h["characteristics"],
                "restrictions": [r.strip() for r in h["restrictions"].split(",") if r.strip()],
            })
            hotels += 1
        except Exception as e:
            errors += 1
            logger.error("dev: дом «%s» не создан: %s", h["name"], e)

    for g in GHOSTS:
        try:
            y, m, d = g["deadline"]
            result = create_request(config, {
                "name": g["name"],
                "anxiety": g["anxiety"],
                "requirements": g["requirements"],
                "preferences": g["preferences"],
                "deadline_date": f"{y:04d}-{m:02d}-{d:02d}",
            })
            enrich(config, "ghost", result["id"], {
                "name": g["name"],
                "requirements": g["requirements"],
                "preferences": g["preferences"],
            })
            ghosts += 1
        except Exception as e:
            errors += 1
            logger.error("dev: заявка «%s» не создана: %s", g["name"], e)

    logger.info("dev: предзаполнено домов=%s, заявок=%s, ошибок=%s", hotels, ghosts, errors)
    return {"status": "ok", "hotels": hotels, "ghosts": ghosts, "errors": errors}
