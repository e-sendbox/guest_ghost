"""Инициализация приложения (шаг 0): создание БД и таблиц при старте, если их нет.

Шаг 12: проверка доступности эмбеддинг-провайдера при старте — недоступен/неверная
размерность → стектрейс, приложение не стартует.
"""

import logging

from backend.clients.embedding_client import EmbeddingClient
from backend.db.connection import connect
from backend.db.schema import create_schema

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768


def _check_embedding(config: dict):
    client = EmbeddingClient(config)
    try:
        vectors = client.embed(["тест"])
    except Exception as e:
        raise RuntimeError(
            f"init: эмбеддинг-провайдер недоступен (type={client.type}, provider={client.provider}): {e}"
        ) from e
    if not vectors or len(vectors[0]) != EMBEDDING_DIM:
        raise RuntimeError(
            f"init: эмбеддинг-провайдер вернул неверную размерность "
            f"(ожидалось {EMBEDDING_DIM}, получено {len(vectors[0]) if vectors else 0})"
        )
    logger.info("init: эмбеддинг-провайдер доступен, type=%s, provider=%s, dim=%s",
                client.type, client.provider, len(vectors[0]))


def init(config: dict):
    db_path = config.get("db", {}).get("path", "data/guest_ghost.db")
    conn = connect(db_path)
    create_schema(conn)
    conn.close()
    logger.info("init: БД готова, path=%s", db_path)
    _check_embedding(config)
