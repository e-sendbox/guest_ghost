"""HTTP-клиент к бэку (шаг 0: заготовка с ping(); шаг 2: create_hotel())."""

import logging

import requests

logger = logging.getLogger(__name__)


class ApiClient:
    def __init__(self, base_url: str = "http://localhost:8080/api"):
        self.base_url = base_url.rstrip("/")

    def ping(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/ping", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def create_hotel(self, data: dict) -> dict:
        resp = requests.post(f"{self.base_url}/hotels", json=data, timeout=10)
        if resp.status_code != 200:
            detail = resp.json().get("detail", "Неизвестная ошибка") if resp.content else "Неизвестная ошибка"
            raise ValueError(detail)
        return resp.json()

    def get_characteristics(self) -> list[str]:
        resp = requests.get(f"{self.base_url}/characteristics", timeout=10)
        if resp.status_code != 200:
            raise ValueError("Не удалось загрузить каталог характеристик")
        return resp.json().get("characteristics", [])

    def get_hotels(self, filter: str | None = None, request_id: int | None = None) -> list[dict]:
        params = {}
        if filter:
            params["filter"] = filter
        if request_id is not None:
            params["request_id"] = request_id
        resp = requests.get(f"{self.base_url}/hotels", params=params, timeout=10)
        if resp.status_code != 200:
            raise ValueError("Не удалось загрузить список домов")
        return resp.json().get("hotels", [])

    def create_request(self, data: dict) -> dict:
        resp = requests.post(f"{self.base_url}/ghosts", json=data, timeout=10)
        if resp.status_code != 200:
            detail = resp.json().get("detail", "Неизвестная ошибка") if resp.content else "Неизвестная ошибка"
            raise ValueError(detail)
        return resp.json()

    def get_requirements(self) -> list[str]:
        resp = requests.get(f"{self.base_url}/requirements", timeout=10)
        if resp.status_code != 200:
            raise ValueError("Не удалось загрузить каталог требований")
        return resp.json().get("requirements", [])

    def get_requests(self, filter: str | None = None, date: str | None = None,
                     period_start: str | None = None, home_id: int | None = None) -> list[dict]:
        params = {}
        if filter:
            params["filter"] = filter
        if date:
            params["date"] = date
        if period_start:
            params["period_start"] = period_start
        if home_id is not None:
            params["home_id"] = home_id
        resp = requests.get(f"{self.base_url}/ghosts", params=params, timeout=10)
        if resp.status_code != 200:
            raise ValueError("Не удалось загрузить список заявок")
        return resp.json().get("requests", [])

    def run_search(self) -> dict:
        resp = requests.post(f"{self.base_url}/search", timeout=600)
        if resp.status_code != 200:
            raise ValueError("Не удалось запустить подбор")
        return resp.json()

    def select_home(self, request_id: int, home_id: int) -> dict:
        resp = requests.post(f"{self.base_url}/ghosts/{request_id}/select", json={"home_id": home_id}, timeout=10)
        if resp.status_code != 200:
            detail = resp.json().get("detail", "Неизвестная ошибка") if resp.content else "Неизвестная ошибка"
            raise ValueError(detail)
        return resp.json()

    def reset_request(self, request_id: int) -> dict:
        resp = requests.post(f"{self.base_url}/ghosts/{request_id}/reset", timeout=10)
        if resp.status_code != 200:
            detail = resp.json().get("detail", "Неизвестная ошибка") if resp.content else "Неизвестная ошибка"
            raise ValueError(detail)
        return resp.json()

    def get_booking_candidates(self) -> list[dict]:
        resp = requests.get(f"{self.base_url}/booking/candidates", timeout=10)
        if resp.status_code != 200:
            raise ValueError("Не удалось загрузить список кандидатов на заселение")
        return resp.json().get("candidates", [])

    def book(self, bookings: list[dict]) -> dict:
        resp = requests.post(f"{self.base_url}/booking", json={"bookings": bookings}, timeout=10)
        if resp.status_code != 200:
            detail = resp.json().get("detail", "Неизвестная ошибка") if resp.content else "Неизвестная ошибка"
            raise ValueError(detail)
        return resp.json()

    def get_report(self, mode: str, days: int) -> dict:
        resp = requests.get(f"{self.base_url}/report", params={"mode": mode, "days": days}, timeout=10)
        if resp.status_code != 200:
            detail = resp.json().get("detail", "Неизвестная ошибка") if resp.content else "Неизвестная ошибка"
            raise ValueError(detail)
        return resp.json()

    def enrich(self, card_type: str, card_id: int, data: dict) -> str:
        resp = requests.post(f"{self.base_url}/enrich", json={"card_type": card_type, "card_id": card_id, "data": data}, timeout=300)
        if resp.status_code != 200:
            raise ValueError("Не удалось обогатить карточку")
        return resp.json().get("status", "error")

    def reset_db(self) -> dict:
        resp = requests.post(f"{self.base_url}/dev/reset", timeout=60)
        if resp.status_code != 200:
            raise ValueError("Не удалось обнулить БД")
        return resp.json()

    def seed_demo(self) -> dict:
        resp = requests.post(f"{self.base_url}/dev/seed", timeout=600)
        if resp.status_code != 200:
            raise ValueError("Не удалось предзаполнить БД")
        return resp.json()
