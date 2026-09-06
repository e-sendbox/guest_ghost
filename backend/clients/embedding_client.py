"""Клиент эмбеддингов (шаг 4; шаг 12: два режима — local/cloud).

Провайдеры:
  - local (ollama): POST {url}/api/embed, {"model", "input"} — L2-нормализует сама
  - cloud (jina):   POST {url}/v1/embeddings, Bearer-ключ, {"model", "input", "normalized": true}

Переключатель — config.yaml → embedding.type (cloud по умолчанию / local запасной),
провайдер — параметр внутри типа (cloud → jina, local → ollama).
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

DEFAULT_LOCAL_URL = "http://localhost:11434"
DEFAULT_LOCAL_MODEL = "paraphrase-multilingual:latest"
DEFAULT_CLOUD_URL = "https://api.jina.ai/v1/embeddings"
DEFAULT_CLOUD_MODEL = "jina-embeddings-v5-omni-nano"


class EmbeddingClient:
    """Клиент эмбеддингов: единый интерфейс embed(texts) для local/cloud."""

    def __init__(self, config: dict):
        embed_cfg = config.get("embedding", {})
        self.type = embed_cfg.get("type", "cloud")
        self.provider = embed_cfg.get("provider", "jina" if self.type == "cloud" else "ollama")
        self.model = embed_cfg.get("model", DEFAULT_CLOUD_MODEL if self.type == "cloud" else DEFAULT_LOCAL_MODEL)
        self.url = embed_cfg.get("url", DEFAULT_CLOUD_URL if self.type == "cloud" else DEFAULT_LOCAL_URL).rstrip("/")
        self.api_key_env = embed_cfg.get("api_key_env", "JINA_API_KEY")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.type == "local":
            return self._embed_ollama(texts)
        return self._embed_jina(texts)

    def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        resp = requests.post(
            f"{self.url}/api/embed",
            json={"model": self.model, "input": texts},
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]

    def _embed_jina(self, texts: list[str]) -> list[list[float]]:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"embedding: не задан ключ {self.api_key_env} в env")
        resp = requests.post(
            self.url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": self.model, "input": texts, "normalized": True},
            timeout=300,
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data.get("data", [])]
