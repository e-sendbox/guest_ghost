"""Логирование запусков (шаг 0): access.log + error.log + debug.log.

Уровни (config.yaml → logging.level):
  DEBUG — пишутся все 3 лога
  INFO  — пишутся access и error
  ERROR — пишется только error
"""

import os
from datetime import datetime
from pathlib import Path

LOG_LEVELS = {"error": 0, "info": 1, "debug": 2}


class RunLogger:
    def __init__(self, log_dir: str = "logs", level: str = "info"):
        self.log_dir = Path(log_dir)
        os.makedirs(self.log_dir, exist_ok=True)
        self._access_fh = open(self.log_dir / "access.log", "a", encoding="utf-8")
        self._error_fh = open(self.log_dir / "error.log", "a", encoding="utf-8")
        self._debug_fh = open(self.log_dir / "debug.log", "a", encoding="utf-8")
        self._level = LOG_LEVELS.get(level.lower(), 1)

    def close(self):
        self._access_fh.close()
        self._error_fh.close()
        self._debug_fh.close()

    def _ts(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _write(self, fh, tag: str, msg: str):
        fh.write(f"[{tag}] {self._ts()} | {msg}\n")
        fh.flush()

    def info(self, msg: str):
        if self._level >= 1:
            self._write(self._access_fh, "INFO", msg)

    def error(self, msg: str):
        self._write(self._error_fh, "ERROR", msg)

    def debug(self, msg: str):
        if self._level >= 2:
            self._write(self._debug_fh, "DEBUG", msg)
