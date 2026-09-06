"""Сервис отчётов (шаг 8): build_report() — по заявкам / по домам.

Иерархия выборки: сначала получаем массив заявок (отсекаем заселенных
на начало периода), потом по массиву считаем поля воронки и проблемные.
Все вычисления округляются до целых.
"""

import logging
from datetime import datetime, timedelta

from backend.db.connection import connect

logger = logging.getLogger(__name__)


def _period_start(days: int) -> str:
    """Начало периода: сегодня минус (N-1) дней, 00:00 (гггг-мм-дд чч:мм:сс).

    1 день = с 00:00 сегодня, 2 дня = с 00:00 вчера, 3 дня = с 00:00 позавчера...
    """
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    return start.strftime("%Y-%m-%d %H:%M:%S")


def _day(date_str: str | None) -> str | None:
    """Дата (гггг-мм-дд) из даты-времени; None если пусто."""
    if not date_str:
        return None
    return date_str[:10]


def build_report(config: dict, mode: str, days: int = 1) -> dict:
    """Собрать отчёт за последние N дней.

    mode: "requests" — по заявкам, "houses" — по домам.
    """
    if mode not in ("requests", "houses"):
        raise ValueError(f"Неизвестный режим отчёта: {mode}")
    if days < 1:
        raise ValueError("Период должен быть не меньше 1 дня")

    start = _period_start(days)
    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    try:
        if mode == "requests":
            return _report_requests(conn, start)
        return _report_houses(conn, start)
    finally:
        conn.close()


def _report_requests(conn, start: str) -> dict:
    """Отчёт по заявкам: все незаселенные + заселенные в периоде, группировка по free_date.

    Незаселенные попадают в отчёт независимо от даты создания: если кого-то
    не заселили хоть когда — это должно быть видно (включая проблемные).
    """
    from backend.services.ghost_service import report_selection_sql
    rows = conn.execute(
        f"""
        SELECT free_date, chosen_date, reserved_date, comment, selection_hotel
        FROM ghost_request
        WHERE {report_selection_sql(start)}
        """
    ).fetchall()

    by_day: dict[str, dict] = {}
    for r in rows:
        day = _day(r["free_date"])
        if day is None:
            continue
        group = by_day.setdefault(day, {
            "date": day,
            "waiting": 0,
            "chosen": 0,
            "reserved": 0,
            "no_dates": 0,
            "no_homes": 0,
        })
        group["waiting"] += 1
        if r["chosen_date"] is not None:
            group["chosen"] += 1
        if r["reserved_date"] is not None:
            group["reserved"] += 1
        if (r["comment"] or "").strip() == "нет подходящих дат":
            group["no_dates"] += 1
        if _all_homes_zero(r["selection_hotel"]):
            group["no_homes"] += 1

    result = sorted(by_day.values(), key=lambda g: g["date"])
    logger.info("report: по заявкам, период с %s, дней с событиями=%s", start, len(result))
    return {"mode": "requests", "period_start": start, "rows": result}


def _all_homes_zero(selection_hotel) -> bool:
    """True, если в selection_hotel есть дома, но у всех match_percent = 0.

    «Нет подходящих домов»: дома по датам прошли, семантически не подошли
    (home_id заявки при этом NULL).
    """
    items = _selection_items(selection_hotel)
    if not items:
        return False
    return all(int(item.get("match_percent") or 0) == 0 for item in items)


def _selection_items(selection_hotel) -> list[dict]:
    """Распарсить selection_hotel в список объектов; при ошибке — пустой список."""
    import json
    try:
        items = json.loads(selection_hotel) if isinstance(selection_hotel, str) else selection_hotel
    except Exception:
        return []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _report_houses(conn, start: str) -> dict:
    """Отчёт по домам: дома из той же выборки, что и по заявкам (все незаселенные + заселенные в периоде).

    Джойн по home_id отсекает заявки без дома (home_id NULL).
    MAX/AVG % соответствия считаются по всем вариантам из selection_hotel
    заявок выборки (с учётом нулевых значений), а не по match_percent
    привязанных заявок.
    """
    from backend.services.ghost_service import report_selection_sql
    rows = conn.execute(
        f"""
        SELECT gr.home_id, hc.name AS hotel_name, gr.selection_hotel,
               gr.reserved_date
        FROM ghost_request gr
        JOIN hotel_card hc ON hc.id = gr.home_id
        WHERE {report_selection_sql(start)}
        """
    ).fetchall()

    by_home: dict[int, dict] = {}
    for r in rows:
        home_id = int(r["home_id"])
        by_home.setdefault(home_id, {
            "home_id": home_id,
            "name": r["hotel_name"],
            "total_rooms": 0,
            "free_start": 0,
            "free_end": 0,
            "max_match": None,
            "avg_match": None,
            "fill_dynamics": 0,
            "matches": [],
        })
    # второй проход: по полному набору домов выборки собираем проценты из selection_hotel
    for r in rows:
        for item in _selection_items(r["selection_hotel"]):
            hid = item.get("home_id")
            if hid is not None and int(hid) in by_home:
                by_home[int(hid)]["matches"].append(int(item.get("match_percent") or 0))

    # статистика по номерам каждого дома
    for home_id, group in by_home.items():
        rooms = conn.execute(
            "SELECT reserved, free_date FROM hotel_rooms WHERE hotel_id = ?",
            (home_id,),
        ).fetchall()
        group["total_rooms"] = len(rooms)
        free_start = 0
        free_end = 0
        filled_in_period = 0
        for room in rooms:
            if not room["reserved"]:
                free_start += 1
                free_end += 1
            else:
                # забронированы во время периода → на начало были свободны
                if room["free_date"] is not None and room["free_date"] > start:
                    free_start += 1
                    filled_in_period += 1
        group["free_start"] = free_start
        group["free_end"] = free_end
        if group["matches"]:
            group["max_match"] = max(group["matches"])
            group["avg_match"] = round(sum(group["matches"]) / len(group["matches"]))
        if group["total_rooms"]:
            group["fill_dynamics"] = round(filled_in_period / group["total_rooms"] * 100)
        group.pop("matches", None)

    result = sorted(by_home.values(), key=lambda g: g["name"])
    logger.info("report: по домам, период с %s, домов=%s", start, len(result))
    return {"mode": "houses", "period_start": start, "rows": result}
