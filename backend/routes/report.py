"""Роуты отчётов (шаг 8): GET /api/report?mode=...&days=...

Регистрация без префикса /api — префикс даёт Mount('/api', ...) в frontend/main.py.
"""

import logging

from fastapi import HTTPException, Request

from backend.services.report_service import build_report

logger = logging.getLogger(__name__)


def register(app):
    @app.get("/report")
    def get_report(request: Request, mode: str = "requests", days: int = 1):
        logger.info("report: GET /api/report, mode=%s, days=%s", mode, days)
        try:
            result = build_report(request.app.state.config, mode, days)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return result
