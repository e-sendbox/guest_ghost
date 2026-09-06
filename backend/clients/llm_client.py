"""Клиент для облачной Ollama (LLM, шаг 4). Паттерн из Rag: OllamaClient."""

import json
import logging
import os

import requests

logger = logging.getLogger(__name__)


class LLMClient:
    """Клиент для Ollama Cloud API (LLM, чат)."""

    def __init__(self, config: dict):
        ollama_cfg = config["llm"]["ollama"]
        self.base_url = ollama_cfg["base_url"].rstrip("/")
        self.model = ollama_cfg["model"]
        self.temperature = ollama_cfg.get("temperature", 0.1)
        key_env = ollama_cfg.get("api_key_env", "OLLAMA_API_KEY")
        self.api_key = os.environ.get(key_env)
        if not self.api_key:
            raise ValueError(f"{key_env} не задан. Установите переменную окружения.")

    def chat(self, messages: list[dict], timeout: int = 90) -> str:
        url = f"{self.base_url}/api/chat"
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "stream": True,
                "options": {"temperature": self.temperature},
            },
            timeout=(30, timeout),
            stream=True,
        )
        resp.raise_for_status()
        full_text = ""
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            data = json.loads(line)
            if "message" in data and "content" in data["message"]:
                full_text += data["message"]["content"]
            if data.get("done"):
                break
        return full_text
