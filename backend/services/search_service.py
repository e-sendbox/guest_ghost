"""Сервис подбора вариантов (шаг 6): free-заявки → фильтр дат → косинус → формула → LLM-комментарии → запись.

Формула match_percent:
  an = anxiety (0..1)
  cosine_sim = 1 - vec_distance_cosine(ghost_emb, home_emb)
  match_percent = max(0, (cosine_sim - an) / (1 - an) * 100)
  при an >= 1: только идеальное совпадение (cosine_sim = 1) → 100
"""

import json
import logging
from datetime import datetime

from backend.clients.llm_client import LLMClient
from backend.db.connection import connect
from prompts import SEARCH_COMMENTS

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 3.0


def _cosine_sim(conn, ghost_id: int, home_id: int) -> float:
    row = conn.execute(
        """
        SELECT vec_distance_cosine(g.embedding, h.embedding) AS d
        FROM ghost_request_emb g, hotel_card_emb h
        WHERE g.ghost_request_id = ? AND h.hotel_card_id = ?
        """,
        (ghost_id, home_id),
    ).fetchone()
    if row is None or row[0] is None:
        return 0.0
    return 1.0 - row[0]


def _match_percent(an: float, cosine: float) -> int:
    if an >= 1:
        return 100 if cosine >= 0.999 else 0
    value = (cosine - an) / (1 - an) * 100
    return max(0, round(value))


def _parse_comments(text: str) -> dict[int, str]:
    import re
    text = text.strip()
    m = re.search(r"\[.*\]", text, re.S)
    if m:
        text = m.group(0)
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("LLM вернул не массив")
    result = {}
    for item in data:
        if isinstance(item, dict) and "home_id" in item:
            result[int(item["home_id"])] = str(item.get("comment", "")).strip()
    return result


def _llm_comments(config: dict, name: str, ghost_tags: str, houses: list[dict]) -> dict[int, str]:
    """Запросить комментарии LLM по каждому дому. Бросает исключение при неудаче."""
    llm = LLMClient(config)
    lines = []
    for h in houses:
        lines.append(f"{h['home_id']}. {h['name']} | сходство: {h['match_percent']}% | теги: {h['tags']}")
    prompt = SEARCH_COMMENTS.format(name=name, ghost_tags=ghost_tags, houses="\n".join(lines))
    error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = llm.chat([
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Прокомментируй дома."},
            ])
            comments = _parse_comments(raw)
            if comments:
                return comments
            error = "LLM вернул пустой результат"
        except Exception as e:
            error = str(e)
            logger.warning("search: LLM попытка %s/%s: %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                import time
                time.sleep(RETRY_DELAY)
    raise RuntimeError(f"LLM не отвечает корректно: {error}")


def run_search(config: dict) -> dict:
    """Запустить подбор: обработать все заявки в статусе free.

    Возвращает {"processed": N, "no_requests": True/False}.
    """
    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    try:
        requests = conn.execute(
            "SELECT id, name, anxiety, deadline_date, status FROM ghost_request WHERE status = 'free' ORDER BY id"
        ).fetchall()
        if not requests:
            return {"processed": 0, "no_requests": True}

        for req in requests:
            req_id = req["id"]
            an = req["anxiety"]
            deadline = req["deadline_date"]

            # 1. жёсткий фильтр по датам
            houses = conn.execute(
                """
                SELECT hc.id AS home_id, hc.name, hc.tags, MIN(hr.free_date) AS free_date
                FROM hotel_card hc
                JOIN hotel_rooms hr ON hr.hotel_id = hc.id
                WHERE hr.free_date <= ?
                GROUP BY hc.id
                ORDER BY hc.id
                """,
                (deadline,),
            ).fetchall()
            if not houses:
                conn.execute(
                    "UPDATE ghost_request SET comment = 'нет подходящих дат', selection_hotel = '[]' WHERE id = ?",
                    (req_id,),
                )
                conn.commit()
                logger.info("search: заявка %s — нет подходящих дат", req_id)
                continue

            # 2. векторное сравнение + формула
            scored = []
            for h in houses:
                cosine = _cosine_sim(conn, req_id, h["home_id"])
                match = _match_percent(an, cosine)
                scored.append({
                    "home_id": h["home_id"],
                    "name": h["name"],
                    "free_date": h["free_date"],
                    "match_percent": match,
                    "tags": h["tags"],
                })
            scored.sort(key=lambda x: x["match_percent"], reverse=True)

            # 3. LLM-комментарии
            ghost_tags = conn.execute("SELECT tags FROM ghost_request WHERE id = ?", (req_id,)).fetchone()[0]
            comments = {}
            try:
                comments = _llm_comments(config, req["name"], ghost_tags, scored)
            except Exception as e:
                logger.error("search: LLM ошибка для заявки %s: %s", req_id, e)

            selection = []
            for s in scored:
                selection.append({
                    "home_id": s["home_id"],
                    "name": s["name"],
                    "free_date": s["free_date"],
                    "match_percent": s["match_percent"],
                    "comment": comments.get(s["home_id"], f"Ошибка LLM: комментарий не получен"),
                })

            best_home = scored[0]["home_id"] if scored and scored[0]["match_percent"] > 0 else None
            best_match = scored[0]["match_percent"] if scored else 0
            chosen_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conn.execute(
                "UPDATE ghost_request SET selection_hotel = ?, home_id = ?, match_percent = ?, status = 'chosen', comment = NULL, chosen_date = ? WHERE id = ?",
                (json.dumps(selection, ensure_ascii=False), best_home, best_match, chosen_date, req_id),
            )
            conn.commit()
            logger.info("search: заявка %s обработана, домов=%s, лучший=%s (%s%%)",
                        req_id, len(selection), best_home, best_match)

        return {"processed": len(requests), "no_requests": False}
    finally:
        conn.close()
