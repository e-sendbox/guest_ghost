"""Роуты ping (шаг 0): GET /api/ping.

Регистрация без префикса /api — префикс даёт Mount('/api', ...) в frontend/main.py.
"""

import logging

logger = logging.getLogger(__name__)


def register(app):
    @app.get("/ping")
    def ping():
        return {"status": "ok"}
