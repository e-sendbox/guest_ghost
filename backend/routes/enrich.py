"""Роуты обогащения (шаг 13): POST /enrich — обёртка над enrich_service.enrich.

Единый механизм: формы «Добавить жилище/заявку» и seed_demo() вызывают обогащение
через HTTP, а не напрямую.
"""

import logging

from backend.services.enrich_service import enrich

logger = logging.getLogger(__name__)


def register(app):
    @app.post("/enrich")
    def enrich_card(payload: dict):
        config = app.state.config
        card_type = payload.get("card_type")
        card_id = payload.get("card_id")
        data = payload.get("data") or {}
        if card_type not in ("hotel", "ghost"):
            return {"status": "error", "message": "card_type должен быть hotel или ghost"}
        if card_id is None:
            return {"status": "error", "message": "card_id обязателен"}
        status = enrich(config, card_type, int(card_id), data)
        return {"status": status}
