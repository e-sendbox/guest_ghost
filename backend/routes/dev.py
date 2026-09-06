"""Роуты DevINFO (шаг 13): POST /dev/reset (обнулить БД), POST /dev/seed (предзаполнить)."""

import logging

from backend.services.dev_service import reset_db, seed_demo

logger = logging.getLogger(__name__)


def register(app):
    @app.post("/dev/reset")
    def dev_reset():
        config = app.state.config
        return reset_db(config)

    @app.post("/dev/seed")
    def dev_seed():
        config = app.state.config
        return seed_demo(config)
