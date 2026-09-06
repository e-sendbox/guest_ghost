"""Общий модуль обогащения (шаг 4): LLM-нормализация тегов + эмбеддинг + сохранение.

Поток: данные карточки → LLM (JSON-массив строк-тегов, до 3 ретраев по 3с) →
эмбеддинг (один вектор на карточку) → сохранение tags + вектор в БД.

Функция возвращает "success" или "LLM error" — попапы рисует морда.
"""

import json
import logging
import re
import time

from backend.clients.embedding_client import EmbeddingClient
from backend.clients.llm_client import LLMClient
from backend.db.connection import connect
from prompts import ENRICH_TAGS

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 3.0


def _parse_tags(text: str) -> list[str]:
    """Распарсить ответ LLM в список строк. Бросает ValueError при невалидном формате."""
    text = text.strip()
    # вытащить JSON-массив из ответа (LLM может оборачивать в ```json ... ``` или добавлять пояснения)
    match = re.search(r"\[.*\]", text, re.S)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("LLM вернул невалидный JSON")
    if not isinstance(data, list) or not all(isinstance(x, str) and x.strip() for x in data):
        raise ValueError("LLM вернул не массив строк")
    return [x.strip() for x in data]


def enrich(config: dict, card_type: str, card_id: int, data: dict) -> str:
    """Обогатить карточку: LLM-теги → эмбеддинг → сохранение в БД.

    card_type: 'hotel' | 'ghost'
    data: поля карточки (name, description, characteristics/requirements, restrictions/preferences)
    Возвращает "success" или "LLM error".
    """
    llm = LLMClient(config)
    embedder = EmbeddingClient(config)

    text_parts = [data.get("name", "")]
    if data.get("description"):
        text_parts.append(data["description"])
    if data.get("characteristics"):
        text_parts.append(json.dumps(data["characteristics"], ensure_ascii=False))
    if data.get("requirements"):
        text_parts.append(json.dumps(data["requirements"], ensure_ascii=False))
    if data.get("restrictions"):
        text_parts.append(json.dumps(data["restrictions"], ensure_ascii=False))
    if data.get("preferences"):
        text_parts.append(data["preferences"])
    source_text = "\n".join(p for p in text_parts if p)

    tags = None
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = llm.chat([
                {"role": "system", "content": ENRICH_TAGS},
                {"role": "user", "content": source_text},
            ])
            tags = _parse_tags(raw)
            break
        except Exception as e:
            last_error = e
            logger.warning("enrich: попытка %s/%s не удалась: %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    if tags is None:
        logger.error("enrich: карточка %s id=%s не обогащена: %s", card_type, card_id, last_error)
        return "LLM error"

    tags_text = ", ".join(tags)
    vectors = embedder.embed([tags_text])
    vector = vectors[0]

    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    try:
        vector_json = json.dumps(vector)
        if card_type == "hotel":
            conn.execute("UPDATE hotel_card SET tags = ? WHERE id = ?",
                         (json.dumps(tags, ensure_ascii=False), card_id))
            conn.execute("INSERT OR REPLACE INTO hotel_card_emb (hotel_card_id, embedding) VALUES (?, ?)",
                         (card_id, vector_json))
        else:
            conn.execute("UPDATE ghost_request SET tags = ? WHERE id = ?",
                         (json.dumps(tags, ensure_ascii=False), card_id))
            conn.execute("INSERT OR REPLACE INTO ghost_request_emb (ghost_request_id, embedding) VALUES (?, ?)",
                         (card_id, vector_json))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    logger.info("enrich: карточка %s id=%s обогащена, тегов=%s, dim=%s",
                card_type, card_id, len(tags), len(vector))
    return "success"
