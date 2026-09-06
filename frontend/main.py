"""Точка входа фронта (шаг 1: прототип морды; шаг 2: монолит).

ВНИМАНИЕ: этот файл — НЕ самостоятельный entrypoint. Он вызывается
диспетчером режимов из корневого main.py. Прямой запуск убран намеренно —
единая точка входа — корневой main.py, режим рулится config.yaml (app.mode).

В режиме monolith FastAPI монтируется внутрь NiceGUI (app.mount("/api", ...)) —
один процесс, один порт.
"""

import logging
from pathlib import Path

import yaml
from nicegui import ui
from starlette.requests import Request

from utils.env import expand_env

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path) as f:
        config = expand_env(yaml.safe_load(f))

    from frontend.ui.layout import build_chrome

    from nicegui import app as nicegui_app
    nicegui_app.add_static_files("/static", Path(__file__).parent / "static")

    mode = config.get("app", {}).get("mode", "frontend")
    port = config.get("app", {}).get("port", 8080)
    if mode == "monolith":
        from backend.main import create_app
        nicegui_app.mount("/api", create_app(config))
        logger.info("frontend: /api смонтирован")

        from frontend.api.client import ApiClient
        api = ApiClient(f"http://localhost:{port}/api")

        import asyncio

        async def _ping():
            logger.info("frontend: ping check start")
            try:
                ok = await asyncio.to_thread(api.ping)
                logger.info("frontend: ping result: %s", ok)
            except Exception as e:
                logger.error("frontend: ping exception: %s", e)
                ok = False
            if ok:
                logger.info("frontend: ping: ok")
            else:
                logger.error("frontend: ping: FAIL — монолит сломан, бэк не отвечает")

        nicegui_app.timer(2.0, _ping, once=True)

    @ui.page("/")
    def page():
        ui.navigate.to("/guest_ghost")

    @ui.page("/guest_ghost")
    def page_guest_ghost(request: Request):
        from frontend.ui.layout import build_chrome
        from frontend.ui.requests_page import build_requests_page
        build_chrome(config, "guest_ghost", lambda: build_requests_page(config, request.query_params))

    @ui.page("/homedirect")
    def page_homedirect(request: Request):
        from frontend.ui.layout import build_chrome
        from frontend.ui.hotels_page import build_hotels_page
        build_chrome(config, "homedirect", lambda: build_hotels_page(config, request.query_params))

    @ui.page("/devinfo")
    def page_devinfo():
        from frontend.ui.layout import build_chrome
        from frontend.ui.devinfo_page import build_devinfo_page
        build_chrome(config, "devinfo", lambda: build_devinfo_page(config))

    title = config.get("app", {}).get("title", "Guest Ghost")
    storage_secret = config.get("app", {}).get("storage_secret")
    logger.info("frontend: запуск, mode=%s, title=%s, port=%s", mode, title, port)
    ui.run(title=title, port=port, reload=False, show=False, storage_secret=storage_secret)
