"""FastAPI-приложение (шаг 2: подключение роутов; шаг 3: роуты заявок)."""

import logging

from fastapi import FastAPI

from backend.routes.booking import register as register_booking
from backend.routes.dev import register as register_dev
from backend.routes.embedding import register as register_embedding
from backend.routes.enrich import register as register_enrich
from backend.routes.ghosts import register as register_ghosts
from backend.routes.hotels import register as register_hotels
from backend.routes.ping import register as register_ping
from backend.routes.report import register as register_report
from backend.routes.search import register as register_search

logger = logging.getLogger(__name__)


def create_app(config: dict) -> FastAPI:
    app = FastAPI(title="Guest Ghost API")
    app.state.config = config
    register_ping(app)
    register_hotels(app)
    register_ghosts(app)
    register_search(app)
    register_booking(app)
    register_report(app)
    register_embedding(app)
    register_enrich(app)
    register_dev(app)
    logger.info("backend: приложение создано, routes=%s", [getattr(r, "path", "?") for r in app.routes])
    return app
