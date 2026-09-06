"""Скрипт установки (шаг 0): создание БД и таблиц.

Запуск: python setup.py
"""

import logging
from datetime import datetime
from pathlib import Path

import yaml

from backend.db.connection import connect
from backend.db.schema import create_schema
from utils.env import expand_env
from utils.logger import RunLogger

logger = logging.getLogger(__name__)


def normalize_room_dates(conn, rl) -> int:
    """Нормализация дат номеров в ISO (гггг-мм-дд).

    Поиск по датам сравнивает строки лексикографически — российский
    формат дд/мм/гггг сравнивает день раньше месяца и даёт мусор.
    """
    rows = conn.execute("SELECT id, free_date FROM hotel_rooms").fetchall()
    updated = 0
    for r in rows:
        d = (r["free_date"] or "").strip()
        if not d:
            continue
        parts = d.split("-")
        if len(parts) == 3 and len(parts[0]) == 4:
            continue
        try:
            iso = datetime.strptime(d, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            rl.error(f"setup: не распознана дата id={r['id']} date={d!r}")
            continue
        conn.execute("UPDATE hotel_rooms SET free_date = ? WHERE id = ?", (iso, r["id"]))
        updated += 1
    conn.commit()
    return updated


def migrate_reserved_column(conn, rl) -> bool:
    """Миграция (шаг 7): добавить hotel_rooms.reserved, если колонки ещё нет."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(hotel_rooms)").fetchall()]
    if "reserved" in cols:
        return False
    conn.execute("ALTER TABLE hotel_rooms ADD COLUMN reserved INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    rl.info("setup: миграция — hotel_rooms.reserved добавлена")
    return True


def migrate_status_dates(conn, rl) -> bool:
    """Миграция (шаг 8): добавить ghost_request.free_date/chosen_date/reserved_date."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(ghost_request)").fetchall()]
    added = False
    for col in ("free_date", "chosen_date", "reserved_date"):
        if col not in cols:
            conn.execute(f"ALTER TABLE ghost_request ADD COLUMN {col} TEXT")
            added = True
    if added:
        conn.commit()
        rl.info("setup: миграция — ghost_request.free_date/chosen_date/reserved_date добавлены")
    return added


def migrate_clean_stale_records(conn, rl) -> int:
    """Миграция (шаг 8): стереть устаревшие записи.

    - comment = 'нет подходящих домов' → NULL (старая логика шага 6)
    - match_percent = 0 → NULL (записей с нулевым соответствием больше не бывает)
    """
    cur = conn.execute("UPDATE ghost_request SET comment = NULL WHERE comment = 'нет подходящих домов'")
    n1 = cur.rowcount
    cur = conn.execute("UPDATE ghost_request SET match_percent = NULL WHERE match_percent = 0")
    n2 = cur.rowcount
    conn.commit()
    if n1 or n2:
        rl.info(f"setup: миграция — стёрто устаревших comment={n1}, match_percent=0: {n2}")
    return n1 + n2


def main():
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        config = expand_env(yaml.safe_load(f))

    rl = RunLogger(
        log_dir=config.get("logging", {}).get("log_dir", "logs"),
        level=config.get("logging", {}).get("level", "info"),
    )
    rl.info("setup: начало установки")

    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    create_schema(conn)
    n = normalize_room_dates(conn, rl)
    migrated = migrate_reserved_column(conn, rl)
    migrated_dates = migrate_status_dates(conn, rl)
    cleaned = migrate_clean_stale_records(conn, rl)
    conn.close()

    rl.info(f"setup: БД создана, path={db_path}, дат нормализовано: {n}, миграция reserved: {migrated}, миграция status_dates: {migrated_dates}, стёрто устаревших: {cleaned}")
    rl.info("setup: установка завершена")
    rl.close()


if __name__ == "__main__":
    main()
