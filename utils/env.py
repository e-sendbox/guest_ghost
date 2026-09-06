"""Подстановка env-переменных в конфиг (шаг 0.2: дистрибуция на Render).

Раскрывает ${VAR:-default} во всех значениях config.yaml (рекурсивно):
  - переменная задана → её значение
  - переменной нет → default
  - default не указан (${VAR}) → пустая строка

Пример: port: ${PORT:-8080} — на Render слушает $PORT, локально fallback 8080.
"""

import os
import re

_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _expand_value(value):
    if isinstance(value, dict):
        return {k: _expand_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_value(v) for v in value]
    if isinstance(value, str):
        return _PATTERN.sub(
            lambda m: os.environ.get(m.group(1), m.group(2) or ""), value
        )
    return value


def expand_env(config: dict) -> dict:
    """Рекурсивно раскрыть ${VAR:-default} во всех значениях конфига."""
    return _expand_value(config)
