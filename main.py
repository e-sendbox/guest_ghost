"""Точка входа — диспетчер режимов (шаг 1).

Режим рулится config.yaml → app.mode:
  frontend — NiceGUI-морда отдельным процессом (прототип, шаг 1)
  monolith — фронт + бэк в одном процессе (задел, реализуется позже)
"""

import logging
from pathlib import Path

import yaml

from backend.init import init
from utils.env import expand_env
from utils.logger import RunLogger

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        config = expand_env(yaml.safe_load(f))

    rl = RunLogger(
        log_dir=config.get("logging", {}).get("log_dir", "logs"),
        level=config.get("logging", {}).get("level", "info"),
    )
    rl.info("app: запуск")

    init(config)
    rl.info("app: инициализация завершена")

    mode = config.get("app", {}).get("mode", "frontend")
    logger.info("mode=%s", mode)
    rl.info(f"app: mode={mode}")

    if mode == "frontend":
        from frontend.main import main as frontend_main
        frontend_main()
    elif mode == "monolith":
        from frontend.main import main as frontend_main
        frontend_main()
    else:
        raise ValueError(f"Неизвестный режим app.mode: {mode}")


if __name__ == "__main__":
    main()
