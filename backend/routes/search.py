"""Роут подбора (шаг 6): POST /api/search.

Регистрация без префикса /api — префикс даёт Mount('/api', ...) в frontend/main.py.
"""

import logging

from fastapi import Request

from backend.services.search_service import run_search

logger = logging.getLogger(__name__)


def register(app):
    @app.post("/search")
    def search(request: Request):
        logger.info("search: POST /api/search")
        return run_search(request.app.state.config)
