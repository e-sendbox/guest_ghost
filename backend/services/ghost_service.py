"""Сервис заявок (шаг 3): create_request() — валидация, сохранение, каталог требований."""

import json
import logging
from datetime import datetime

from backend.db.connection import connect

logger = logging.getLogger(__name__)


def _now() -> str:
    """Текущая дата-время для полей free_date/chosen_date/reserved_date."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class ValidationError(Exception):
    pass


def create_request(config: dict, data: dict) -> dict:
    """Создание заявки: валидация → ghost_request + каталог требований."""
    name = (data.get("name") or "").strip()
    anxiety = data.get("anxiety")
    requirements = data.get("requirements") or {}
    preferences = (data.get("preferences") or "").strip()
    deadline_date = (data.get("deadline_date") or "").strip()

    if not name:
        raise ValidationError("Имя приведения обязательно")
    if anxiety is None:
        raise ValidationError("Уровень тревожности обязателен")
    try:
        anxiety = float(anxiety)
    except (TypeError, ValueError):
        raise ValidationError("Некорректный уровень тревожности")
    if not (0 <= anxiety <= 1):
        raise ValidationError("Уровень тревожности должен быть от 0 до 1")
    if not requirements:
        raise ValidationError("Добавьте хотя бы одно требование")
    if not deadline_date:
        raise ValidationError("Укажите дату заселения")

    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO ghost_request (name, anxiety, requirements, preferences, deadline_date, status, free_date) "
            "VALUES (?, ?, ?, ?, ?, 'free', ?)",
            (name, anxiety, json.dumps(requirements, ensure_ascii=False), preferences, deadline_date, _now()),
        )
        request_id = cur.lastrowid

        for key in requirements:
            conn.execute("INSERT OR IGNORE INTO ghost_requirement (name) VALUES (?)", (key,))

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    logger.info("ghost_service: заявка сохранена, id=%s, name=%s, тревожность=%s, требований=%s, дедлайн=%s",
                request_id, name, anxiety, len(requirements), deadline_date)
    return {"id": request_id, "name": name}


def list_requirements(config: dict) -> list[str]:
    """Список требований из каталога ghost_requirement (по алфавиту)."""
    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT name FROM ghost_requirement ORDER BY name").fetchall()
    finally:
        conn.close()
    names = [r["name"] for r in rows]
    logger.info("ghost_service: каталог требований, count=%s", len(names))
    return names


def report_selection_sql(period_start: str) -> str:
    """Условие выборки отчёта (шаг 8): все незаселенные + заселенные в периоде.

    Общая функция — используется и в отчёте (report_service), и в фильтрах
    страницы заявок (шаг 10), чтобы формула не дублировалась.
    """
    return f"(status != 'reserved' OR (status = 'reserved' AND reserved_date >= '{period_start}'))"


def list_requests(config: dict, filter: str | None = None, date: str | None = None,
                  period_start: str | None = None, home_id: int | None = None) -> list[dict]:
    """Список заявок (по id) с именем дома при выборе/заселении.

    ghost_request.home_id ссылается на hotel_card(id); имя дома берём
    джойном hotel_card. В каждый объект selection_hotel подмешиваем
    tags из hotel_card (по home_id).

    Шаг 10: фильтры переходов из отчётов (формула = шаг 8):
      waiting        — заявки выборки отчёта за день date
      chosen         — + chosen_date IS NOT NULL
      reserved       — + reserved_date IS NOT NULL
      no_dates       — + comment = 'нет подходящих дат'
      no_homes       — + selection_hotel непустой, все match_percent = 0
      house_dynamics — заявки выборки отчёта с home_id (без date)
    """
    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    try:
        where = []
        params = []
        if filter in ("waiting", "chosen", "reserved", "no_dates", "no_homes"):
            if not period_start or not date:
                raise ValidationError("Для фильтра нужны period_start и date")
            where.append(report_selection_sql(period_start))
            where.append("date(free_date) = ?")
            params.append(date)
            if filter == "chosen":
                where.append("chosen_date IS NOT NULL")
            elif filter == "reserved":
                where.append("reserved_date IS NOT NULL")
            elif filter == "no_dates":
                where.append("comment = 'нет подходящих дат'")
        elif filter == "house_dynamics":
            if not period_start or home_id is None:
                raise ValidationError("Для фильтра нужны period_start и home_id")
            where.append(report_selection_sql(period_start))
            where.append("home_id = ?")
            params.append(home_id)
        elif filter is not None:
            raise ValidationError(f"Неизвестный фильтр: {filter}")

        sql = """
            SELECT gr.id, gr.name, gr.anxiety, gr.deadline_date, gr.status, gr.home_id,
                   gr.selection_hotel, gr.comment, gr.match_percent, gr.tags,
                   hc.name AS hotel_name
            FROM ghost_request gr
            LEFT JOIN hotel_card hc ON hc.id = gr.home_id
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY gr.id"
        rows = conn.execute(sql, params).fetchall()
        # теги всех домов: home_id -> tags
        tags_map = {}
        for hc in conn.execute("SELECT id, tags FROM hotel_card").fetchall():
            tags_map[hc["id"]] = hc["tags"]
    finally:
        conn.close()

    requests = []
    for r in rows:
        req = dict(r)
        req["home_id"] = int(req["home_id"]) if req.get("home_id") is not None else None
        try:
            selection = json.loads(req.get("selection_hotel") or "[]")
        except Exception:
            selection = []
        for item in selection:
            item["tags"] = tags_map.get(item.get("home_id"), "[]")
        req["selection_hotel"] = json.dumps(selection, ensure_ascii=False)
        requests.append(req)

    # no_homes: Python-фильтр (selection_hotel непустой, все match_percent = 0)
    if filter == "no_homes":
        requests = [r for r in requests if _all_homes_zero(r.get("selection_hotel"))]

    logger.info("ghost_service: список заявок, count=%s, filter=%s", len(requests), filter)
    return requests


def _all_homes_zero(selection_hotel) -> bool:
    """True, если в selection_hotel есть дома, но у всех match_percent = 0."""
    try:
        items = json.loads(selection_hotel) if isinstance(selection_hotel, str) else selection_hotel
    except Exception:
        return False
    if not isinstance(items, list) or not items:
        return False
    return all(int(item.get("match_percent") or 0) == 0 for item in items if isinstance(item, dict))


def select_home(config: dict, request_id: int, home_id: int) -> dict:
    """Перевыбор дома для заселения (шаг 5.1).

    home_id должен быть в selection_hotel заявки; match_percent берём
    из selection_hotel выбранного дома. status не меняем.
    """
    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT selection_hotel FROM ghost_request WHERE id = ?", (request_id,)
        ).fetchone()
        if row is None:
            raise ValidationError("Заявка не найдена")
        try:
            selection = json.loads(row["selection_hotel"] or "[]")
        except Exception:
            selection = []
        match = None
        for item in selection:
            if item.get("home_id") == home_id:
                match = item.get("match_percent")
                break
        if match is None:
            raise ValidationError("Дом не найден в выборке заявки")
        conn.execute(
            "UPDATE ghost_request SET home_id = ?, match_percent = ? WHERE id = ?",
            (home_id, match, request_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    logger.info("ghost_service: перевыбор дома, request_id=%s, home_id=%s, match=%s",
                request_id, home_id, match)
    return {"id": request_id, "home_id": home_id, "match_percent": match}


def reset_request(config: dict, request_id: int) -> dict:
    """Сброс заявки «никуда не заселять» (шаг 5.1): free + обнуление выборки."""
    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT id FROM ghost_request WHERE id = ?", (request_id,)).fetchone()
        if row is None:
            raise ValidationError("Заявка не найдена")
        conn.execute(
            "UPDATE ghost_request SET status = 'free', home_id = NULL, match_percent = NULL, "
            "selection_hotel = '[]', comment = NULL, chosen_date = NULL WHERE id = ?",
            (request_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    logger.info("ghost_service: сброс заявки, request_id=%s", request_id)
    return {"id": request_id, "status": "free"}


def list_booking_candidates(config: dict) -> list[dict]:
    """Список кандидатов на заселение (шаг 7): заявки chosen с выбранным домом.

    Возвращает дома сгруппированными по hotel_card, в каждой группе — заявки
    (name, anxiety, deadline_date, home_id, match_percent) и свободные номера
    дома (reserved = 0), подходящие по дате (free_date <= deadline заявки).
    """
    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT gr.id, gr.name, gr.anxiety, gr.deadline_date, gr.home_id, gr.match_percent,
                   hc.name AS hotel_name
            FROM ghost_request gr
            JOIN hotel_card hc ON hc.id = gr.home_id
            WHERE gr.status = 'chosen' AND gr.home_id IS NOT NULL
            ORDER BY hc.id, gr.id
            """
        ).fetchall()
    finally:
        conn.close()

    groups: dict[int, dict] = {}
    for r in rows:
        home_id = r["home_id"]
        hotel_name = r["hotel_name"]

        # свободные номера дома, подходящие по дате для КАЖДОЙ заявки — считаем отдельно
        rooms = _available_rooms(db_path, home_id, r["deadline_date"])
        group = groups.setdefault(home_id, {
            "home_id": home_id,
            "name": hotel_name,
            "requests": [],
        })
        group["requests"].append({
            "id": r["id"],
            "name": r["name"],
            "anxiety": r["anxiety"],
            "deadline_date": r["deadline_date"],
            "match_percent": r["match_percent"],
            "rooms": rooms,
        })

    result = list(groups.values())
    logger.info("ghost_service: кандидаты на бронь, домов=%s", len(result))
    return result


def _available_rooms(db_path: str, home_id: int, deadline_date: str) -> list[dict]:
    """Свободные номера дома с датой <= deadline (для выпадашки «Выбрать номер»)."""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, free_date FROM hotel_rooms
            WHERE hotel_id = ? AND reserved = 0 AND free_date <= ?
            ORDER BY free_date, id
            """,
            (home_id, deadline_date),
        ).fetchall()
    finally:
        conn.close()
    return [{"id": r["id"], "free_date": r["free_date"]} for r in rows]


def book_requests(config: dict, bookings: list[dict]) -> dict:
    """Бронь номеров для заявок (шаг 7): транзакционная запись.

    bookings — [{"request_id": N, "room_id": N}]. Каждая заявка: chosen + home_id
    не пуст; номер: существует, reserved = 0, free_date <= deadline заявки.
    При ошибке — ValidationError (400), ничего не записываем.
    """
    if not bookings:
        raise ValidationError("Лист бронирования пуст")

    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    try:
        for b in bookings:
            try:
                request_id = int(b.get("request_id"))
                room_id = int(b.get("room_id"))
            except (TypeError, ValueError):
                raise ValidationError("Некорректный id заявки или номера")

            req = conn.execute(
                "SELECT id, home_id, deadline_date, status FROM ghost_request WHERE id = ?",
                (request_id,),
            ).fetchone()
            if req is None:
                raise ValidationError(f"Заявка {request_id} не найдена")
            if req["status"] != "chosen" or req["home_id"] is None:
                raise ValidationError(f"Заявка {request_id} не готова к бронированию")

            home_id = int(req["home_id"])
            room = conn.execute(
                "SELECT id, hotel_id, free_date, reserved FROM hotel_rooms WHERE id = ?",
                (room_id,),
            ).fetchone()
            if room is None:
                raise ValidationError(f"Номер {room_id} не найден")
            if room["hotel_id"] != home_id:
                raise ValidationError(f"Номер {room_id} не относится к дому заявки {request_id}")
            if room["reserved"]:
                raise ValidationError(f"Номер {room_id} уже занят")
            if room["free_date"] is None or room["free_date"] > req["deadline_date"]:
                raise ValidationError(f"Номер {room_id} не подходит по дате для заявки {request_id}")

        for b in bookings:
            conn.execute(
                "UPDATE ghost_request SET status = 'reserved', reserved_date = ? WHERE id = ?",
                (_now(), b["request_id"]),
            )
            conn.execute(
                "UPDATE hotel_rooms SET reserved = 1, free_date = ? WHERE id = ?",
                (_now(), b["room_id"]),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    logger.info("ghost_service: бронь выполнена, заявок=%s", len(bookings))
    return {"booked": len(bookings)}
