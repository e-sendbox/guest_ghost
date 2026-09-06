"""Роуты отелей (шаг 2): POST /api/hotels, GET /api/characteristics.

Регистрация без префикса /api — префикс даёт Mount('/api', ...) в frontend/main.py.
"""

import logging

from fastapi import HTTPException, Request

from backend.db.connection import connect
from backend.services.hotel_service import ValidationError, create_hotel, list_hotels

logger = logging.getLogger(__name__)


def register(app):
    @app.post("/hotels")
    def post_hotel(request: Request, data: dict):
        logger.info("hotels: POST /api/hotels, data=%s", data)
        try:
            result = create_hotel(request.app.state.config, data)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return result

    @app.get("/hotels")
    def get_hotels(request: Request, filter: str | None = None, request_id: int | None = None):
        try:
            hotels = list_hotels(request.app.state.config, filter=filter, request_id=request_id)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        logger.info("hotels: GET /api/hotels, count=%s, filter=%s", len(hotels), filter)
        return {"hotels": hotels}

    @app.get("/characteristics")
    def get_characteristics(request: Request):
        db_path = request.app.state.config.get("db", {}).get("path", "data/guest_ghost.db")
        conn = connect(db_path)
        try:
            rows = conn.execute("SELECT name FROM hotel_characteristic ORDER BY name").fetchall()
        finally:
            conn.close()
        names = [r["name"] for r in rows]
        logger.info("hotels: GET /api/characteristics, count=%s", len(names))
        return {"characteristics": names}
