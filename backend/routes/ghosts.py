"""Роуты заявок (шаг 3: POST /api/ghosts, GET /api/requirements; шаг 5: GET /api/ghosts).

Регистрация без префикса /api — префикс даёт Mount('/api', ...) в frontend/main.py.
"""

import logging

from fastapi import HTTPException, Request

from backend.services.ghost_service import (
    ValidationError,
    create_request,
    list_requests,
    list_requirements,
    reset_request,
    select_home,
)

logger = logging.getLogger(__name__)


def register(app):
    @app.post("/ghosts")
    def post_request(request: Request, data: dict):
        logger.info("ghosts: POST /api/ghosts, data=%s", data)
        try:
            result = create_request(request.app.state.config, data)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return result

    @app.get("/ghosts")
    def get_requests(request: Request, filter: str | None = None, date: str | None = None,
                     period_start: str | None = None, home_id: int | None = None):
        try:
            requests = list_requests(request.app.state.config, filter=filter, date=date,
                                      period_start=period_start, home_id=home_id)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"requests": requests}

    @app.get("/requirements")
    def get_requirements(request: Request):
        names = list_requirements(request.app.state.config)
        return {"requirements": names}

    @app.post("/ghosts/{request_id}/select")
    def post_select(request: Request, request_id: int, data: dict):
        logger.info("ghosts: POST /api/ghosts/%s/select, data=%s", request_id, data)
        try:
            result = select_home(request.app.state.config, request_id, data.get("home_id"))
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return result

    @app.post("/ghosts/{request_id}/reset")
    def post_reset(request: Request, request_id: int):
        logger.info("ghosts: POST /api/ghosts/%s/reset", request_id)
        try:
            result = reset_request(request.app.state.config, request_id)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return result
