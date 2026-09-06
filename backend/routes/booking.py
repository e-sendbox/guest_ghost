"""Роуты бронирования (шаг 7): GET /api/booking/candidates, POST /api/booking.

Регистрация без префикса /api — префикс даёт Mount('/api', ...) в frontend/main.py.
"""

import logging

from fastapi import HTTPException, Request

from backend.services.ghost_service import ValidationError, book_requests, list_booking_candidates

logger = logging.getLogger(__name__)


def register(app):
    @app.get("/booking/candidates")
    def get_booking_candidates(request: Request):
        candidates = list_booking_candidates(request.app.state.config)
        return {"candidates": candidates}

    @app.post("/booking")
    def post_booking(request: Request, data: dict):
        logger.info("booking: POST /api/booking, bookings=%s", data.get("bookings"))
        try:
            result = book_requests(request.app.state.config, data.get("bookings") or [])
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return result
