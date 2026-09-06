"""Сервис отелей (шаг 2): create_hotel() — валидация, сохранение, каталог характеристик."""

import json
import logging

from backend.db.connection import connect

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    pass


def create_hotel(config: dict, data: dict) -> dict:
    """Создание дома: валидация → hotel_card + hotel_rooms + каталог характеристик."""
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    characteristics = data.get("characteristics") or {}
    restrictions = data.get("restrictions") or []
    rooms = data.get("rooms") or []

    if not name:
        raise ValidationError("Название дома обязательно")
    if not description:
        raise ValidationError("Описание дома обязательно")
    if not characteristics:
        raise ValidationError("Добавьте хотя бы одну характеристику")
    if not rooms:
        raise ValidationError("Добавьте хотя бы один номер")

    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO hotel_card (name, description, characteristics, restrictions) VALUES (?, ?, ?, ?)",
            (name, description, json.dumps(characteristics, ensure_ascii=False), json.dumps(restrictions, ensure_ascii=False)),
        )
        hotel_id = cur.lastrowid

        for room in rooms:
            conn.execute(
                "INSERT INTO hotel_rooms (hotel_id, free_date) VALUES (?, ?)",
                (hotel_id, room.get("free_date")),
            )

        for key in characteristics:
            conn.execute("INSERT OR IGNORE INTO hotel_characteristic (name) VALUES (?)", (key,))

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    logger.info("hotel_service: дом сохранён, id=%s, name=%s, характеристик=%s, номеров=%s",
                hotel_id, name, len(characteristics), len(rooms))
    return {"id": hotel_id, "name": name}


def list_hotels(config: dict, filter: str | None = None, request_id: int | None = None) -> list[dict]:
    """Список домов (шаг 9): карточки домов + вместимость.

    По каждому дому: total_rooms (все номера), free_rooms (reserved = 0).
    Шаг 10: filter=from_request — только дом, выбранный заявкой request_id
    (пусто, если home_id NULL).
    """
    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    try:
        where = ""
        params = []
        if filter == "from_request":
            if request_id is None:
                raise ValidationError("Для фильтра from_request нужен request_id")
            where = " WHERE hc.id = (SELECT home_id FROM ghost_request WHERE id = ?)"
            params.append(request_id)
        elif filter is not None:
            raise ValidationError(f"Неизвестный фильтр: {filter}")
        rows = conn.execute(
            f"""
            SELECT hc.id, hc.name, hc.description, hc.characteristics, hc.restrictions,
                   COUNT(hr.id) AS total_rooms,
                   SUM(CASE WHEN hr.reserved = 0 THEN 1 ELSE 0 END) AS free_rooms
            FROM hotel_card hc
            LEFT JOIN hotel_rooms hr ON hr.hotel_id = hc.id
            {where}
            GROUP BY hc.id
            ORDER BY hc.id
            """,
            params,
        ).fetchall()
    finally:
        conn.close()
    hotels = []
    for r in rows:
        hotels.append({
            "id": r["id"],
            "name": r["name"],
            "description": r["description"],
            "characteristics": json.loads(r["characteristics"] or "{}"),
            "restrictions": json.loads(r["restrictions"] or "[]"),
            "total_rooms": r["total_rooms"] or 0,
            "free_rooms": r["free_rooms"] or 0,
        })
    logger.info("hotel_service: список домов, count=%s, filter=%s", len(hotels), filter)
    return hotels
