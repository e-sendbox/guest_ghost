"""Разовый скрипт заливки демо-данных через интерфейс (Playwright).

Добавляет 10 домов и 10 заявок через формы морды ровно так, как это делал
бы человек: поля, автокомплит характеристик/требований, календарь, чипы,
сохранение, ожидание обогащения и закрытие попапа успеха.

Данные:
  - 10 домов, номера свободны с октября 2026 (все min(free_date) >= 2026-10-01)
  - 9 приведений с дедлайнами ноябрь 2026 — февраль 2027 (пересечение с датами домов)
  - приведение №10 («Шепчущий Нерон»): дедлайн 2026-07-15 — раньше дат всех
    домов → после подбора получит comment «нет подходящих дат»

Запуск: python3 scripts/seed_demo.py (сервер main.py должен быть поднят)
"""

import logging
import re
import time

from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PwTimeoutError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_demo")

URL = "http://localhost:8080"

MONTHS_SHORT = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
MONTHS_FULL = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]

HOTELS = [
    {
        "name": "Замок Крюк-на-Тумане",
        "description": (
            "Средневековый замок на обрыве у побережья, вечно окутан туманом. "
            "Стены промозглые, в подвалах грибные сады, в главной башне сквозняк "
            "напоминает старую волынку. Полы каменные, скрипучая лестница, "
            "ни одного живого соседа на три мили."
        ),
        "characteristics": {
            "сырость": "высокая",
            "освещение": "темно",
            "сквозняки": "постоянные",
            "насекомые": "много",
        },
        "restrictions": "без живых людей, без кошек, без музыки",
        "rooms": [("2026-10-01",), ("2026-10-15",), ("2026-11-01",)],
    },
    {
        "name": "Чердак Вороньего Дома",
        "description": (
            "Простой двухэтажный дом на окраине города, чердак под самой крышей. "
            "Пыль густая, доски рассохшие, сквозь щели тянет холодом. Над головой, "
            "под коньком, иногда стучит голубь — в остальном тишина и покой. Очень "
            "любят такие места тихие и нелюдимые привидения."
        ),
        "characteristics": {
            "тишина": "полная",
            "освещение": "полумрак",
            "пыль": "много",
            "температура": "прохладно",
        },
        "restrictions": "без дневных посетителей",
        "rooms": [("2026-10-05",), ("2026-11-20",)],
    },
    {
        "name": "Особняк Разбитого Рояля",
        "description": (
            "Заброшенный купеческий особняк с бальной залой, где до сих пор стоит "
            "рассыпающийся рояль. Паркет шумит, люстры звенят от малейшего ветерка, "
            "в гостиной висит огромное зеркало. Идеальное место для тех, кто любит "
            "поскрипеть половицами в ночной тишине."
        ),
        "characteristics": {
            "эхо": "богатое",
            "освещение": "светло",
            "простор": "большой",
            "зеркала": "есть",
        },
        "restrictions": "без ремонта, без пианистов",
        "rooms": [("2026-10-10",), ("2026-12-01",), ("2026-12-20",)],
    },
    {
        "name": "Подвал Пивоварни «Дубовая Бочка»",
        "description": (
            "Старинный подвал, где когда-то варили пиво: запах дрожжей и хмеля "
            "держится до сих пор. Своды кирпичные, в углу ржавые краны, глухо и "
            "темно. Прохладно круглый год. Для тех, кто не переносит дневного света "
            "и любит пошуршать в залежах пустых бочек."
        ),
        "characteristics": {
            "темнота": "полная",
            "запах дрожжей": "стойкий",
            "температура": "холодно",
            "влажность": "повышенная",
        },
        "restrictions": "без света",
        "rooms": [("2026-10-02",), ("2026-10-20",), ("2026-11-10",), ("2026-12-05",)],
    },
    {
        "name": "Мельница Ветров",
        "description": (
            "Каменная ветряная мельница на холме, крылья давно замерли. Внутри "
            "жернова, мука столетней давности, наверху скрипят балки. Открыто "
            "всем ветрам: гулкая и свободная. Хороший вариант для приведения, "
            "которому нужно много воздуха и никаких соседей."
        ),
        "characteristics": {
            "сквозняки": "сильные",
            "эхо": "гулкое",
            "запах зерна": "есть",
            "тишина": "частичная",
        },
        "restrictions": "без ветряных мельниц, без детей",
        "rooms": [("2026-10-18",), ("2026-11-05",)],
    },
    {
        "name": "Лесной Сторожек",
        "description": (
            "Небольшая избушка лесника в двух километрах от деревни, стоит у "
            "тёмного оврага. Печка нетоплена, в сенях пахнет сеном и берёзовыми "
            "вениками. Крыша течёт в одном углу, пол в другом — сыро и уютно. "
            "Кругом густой ельник, слышно только, как ухает сова."
        ),
        "characteristics": {
            "тишина": "полная",
            "сырость": "высокая",
            "запах сена": "стойкий",
            "теснота": "уютная",
        },
        "restrictions": "без собак, без ружей",
        "rooms": [("2026-10-08",), ("2026-11-15",), ("2026-12-10",)],
    },
    {
        "name": "Склеп Благородных Теней",
        "description": (
            "Семейный склеп на старом кладбище, сложен из серого гранита. Внутри "
            "ровные ряды ниш, каменный пол, единственная лампаду держит кто-то "
            "невридимый. Прохладно, торжественно и очень тихо. Никто не приходит, "
            "кроме старушки в среду и в субботу."
        ),
        "characteristics": {
            "тишина": "абсолютная",
            "температура": "холодно",
            "каменные стены": "есть",
            "одиночество": "полное",
        },
        "restrictions": "без факелов, без экскурсий",
        "rooms": [("2026-10-12",), ("2026-11-01",)],
    },
    {
        "name": "Баня Колдуна",
        "description": (
            "Бревенчатая баня в глубине сада, парная с каменкой давно остыла. "
            "Пар поднимается только по ночам, сам собой. Дубовые полки, запах "
            "веников и трав. Стены пропахли паром насквозь, так что сырость "
            "гарантирована, и тепло тоже."
        ),
        "characteristics": {
            "пар": "ночной",
            "запах трав": "стойкий",
            "тепло": "остаточное",
            "теснота": "уютная",
        },
        "restrictions": "без мочалок",
        "rooms": [("2026-10-25",), ("2026-12-15",)],
    },
    {
        "name": "Библиотека Призрачного Смотрителя",
        "description": (
            "Чёрдак-библиотека в городском особняке: стеллажи от пола до потолка, "
            "фолианты в кожаных переплётах. Пахнет старой бумагой и воском. Если "
            "привидение любит шелестеть страницами и переставлять книги по ночам — "
            "это его место. Свет проникает только через круглые окна-иллюминаторы."
        ),
        "characteristics": {
            "запах старых книг": "стойкий",
            "освещение": "полумрак",
            "тишина": "полная",
            "пыль книжная": "есть",
        },
        "restrictions": "без огня, без читателей",
        "rooms": [("2026-10-30",), ("2026-11-25",)],
    },
    {
        "name": "Покинутая Усадьба",
        "description": (
            "Большая усадьба с колоннами, заросшая лебедой и полынью: хозяйская "
            "часть разорена, зато флигель сохранился. Мебель в чехлах, в камине "
            "зола. Просторно, полутемно, ветер гуляет по анфиладе комнат. Любимое "
            "прибежище тех, кто привык держаться в тени."
        ),
        "characteristics": {
            "простор": "большой",
            "запущенность": "полная",
            "освещение": "сумерки",
            "запах полыни": "есть",
        },
        "restrictions": "без фейерверков",
        "rooms": [("2026-10-15",), ("2026-11-30",), ("2026-12-25",)],
    },
]

GHOSTS = [
    {
        "name": "Сэм Блуждающий",
        "anxiety": 0.3,
        "requirements": {
            "сырость": "нужна",
            "тишина": "важна",
        },
        "preferences": (
            "Люблю прохладные подвалы с запахом земли. Хочу селиться надолго, "
            "мешать никому не собираюсь, пугать не планирую."
        ),
        "deadline": (2026, 11, 30),
    },
    {
        "name": "Графиня Эхо",
        "anxiety": 0.7,
        "requirements": {
            "простор": "залы",
            "зеркала": "есть",
        },
        "preferences": (
            "Мне нужен большой зал с хорошим эхом, чтобы голос звучал красиво. "
            "Зеркала обязательны — я привыкла видеть отражение. Парадные лестницы."
        ),
        "deadline": (2026, 12, 20),
    },
    {
        "name": "Тихон Хранитель",
        "anxiety": 0.2,
        "requirements": {
            "тишина": "абсолютная",
            "каменные стены": "есть",
        },
        "preferences": (
            "Мечтаю о склепе или часовне. Хочу полной тишины и одиночества, "
            "чтобы никто не бродил по ночам. Желательно без сквозняков."
        ),
        "deadline": (2026, 11, 15),
    },
    {
        "name": "Вилли Кочерыжка",
        "anxiety": 0.5,
        "requirements": {
            "запах дрожжей": "нужен",
            "темнота": "полная",
        },
        "preferences": (
            "Хочу в погреб пивоварни: запах дрожжей — родной. Свет не переношу "
            "вообще, день провожу в полной темноте. Шуршать бочками — моё любимое."
        ),
        "deadline": (2026, 11, 10),
    },
    {
        "name": "Мадам Скрип",
        "anxiety": 0.4,
        "requirements": {
            "эхо": "гулкое",
            "запах зерна": "есть",
        },
        "preferences": (
            "Обожаю ветряные мельницы: скрип и простор. Нужно много воздуха и "
            "никаких соседей. По вечерам люблю спускаться по жерновам и звенеть."
        ),
        "deadline": (2027, 1, 10),
    },
    {
        "name": "Дядюшка Пыль",
        "anxiety": 0.6,
        "requirements": {
            "пыль": "много",
            "полумрак": "да",
        },
        "preferences": (
            "Дом должен быть давно необитаемым: пыль на всём, паутина в углах. "
            "Полумрак и тишина. Категорически против уборки и ремонта. "
            "Желательно старые доски и рассохшиеся рамы."
        ),
        "deadline": (2026, 12, 5),
    },
    {
        "name": "Полтергейст Окно-Хлоп",
        "anxiety": 0.1,
        "requirements": {
            "сквозняки": "постоянные",
            "простор": "большой",
        },
        "preferences": (
            "Люблю, когда ветер гуляет по комнатам и хлопают ставни. Готов к "
            "любому дому, лишь бы много окон и был чердак. Буду хлопать дверями "
            "и играть со шторами по ночам."
        ),
        "deadline": (2027, 2, 1),
    },
    {
        "name": "Тётя Молчанка",
        "anxiety": 0.8,
        "requirements": {
            "тишина": "абсолютная",
            "температура": "холодно",
            "одиночество": "полное",
        },
        "preferences": (
            "Никого и ничего слышно не должно быть. Только холод и камень. "
            "Даже ветер мне мешает. Хочу жить в полном одиночестве, лучше всего "
            "в склепе или старом каменном подвале."
        ),
        "deadline": (2026, 11, 20),
    },
    {
        "name": "Грызлик Книжный",
        "anxiety": 0.6,
        "requirements": {
            "запах старых книг": "обязателен",
            "полумрак": "да",
        },
        "preferences": (
            "Мне нужна библиотека: книги, воск, кожаные переплёты. Хочу "
            "шелестеть страницами по ночам и перечитывать фолианты. Свет "
            "противопоказан, бумага портится. Сырости избегать."
        ),
        "deadline": (2026, 11, 25),
    },
    {
        "name": "Шепчущий Нерон",
        "anxiety": 0.5,
        "requirements": {
            "подземелья": "есть",
            "тишина": "нужна",
        },
        "preferences": (
            "Ищу подземелье с переходами, чтобы бродить и шептать. Могу ждать "
            "сколько угодно — главное, чтобы место устроило. Вслед не смотрю."
        ),
        "deadline": (2026, 7, 15),
    },
]


def month_num(text: str):
    low = text.strip().lower()
    for i, m in enumerate(MONTHS_FULL, start=1):
        if m.lower() in low:
            return i
    for i, m in enumerate(MONTHS_SHORT, start=1):
        if m.lower() in low:
            return i
    raise AssertionError(f"месяц не распознан: {text!r}")


class Seeder:
    def __init__(self, page):
        self.page = page

    def _field(self, anchor, frame=".form-popup"):
        return self.page.locator(f"{frame} .q-field").filter(has_text=anchor).locator(".q-field__native").first

    def _add_chips(self, frame_cls: str, items: dict[str, str]):
        auto = self.page.locator(f".{frame_cls} .w-56")
        value = self.page.locator(f".{frame_cls} .flex-1")
        plus = self.page.locator(f".{frame_cls} .round-plus")
        for key, val in items.items():
            auto.fill(key)
            value.fill(val)
            plus.click()
            self.page.wait_for_timeout(150)

    def _pick_date(self, field_locator, year: int, month: int, day: int, label: str):
        if not (self.page.locator(".q-date").count() and self.page.locator(".q-date").first.is_visible()):
            field_locator.click()
        self.page.locator(".q-date").first.wait_for(state="visible", timeout=5000)
        nav = self.page.locator(".q-date__navigation .q-btn")
        cur_month = month_num(nav.nth(1).inner_text())
        cur_year = int(nav.nth(4).inner_text())
        steps = (year - cur_year) * 12 + (month - cur_month)
        btn = nav.nth(2) if steps > 0 else nav.nth(0)
        for _ in range(abs(steps)):
            btn.click()
            self.page.wait_for_timeout(700)  # переждать fade-переход Quasar
        day_btns = self.page.locator(".q-date:not([class*='month']) .q-btn:not([class*='nav'])")
        target = day_btns.filter(has_text=re.compile(f"^{day}$")).first
        for attempt in range(6):
            try:
                target.click(timeout=8000)
                break
            except PwTimeoutError:
                if attempt == 5:
                    raise
                self.page.wait_for_timeout(500)
        self.page.wait_for_timeout(250)
        got = field_locator.evaluate("el => el.value")
        assert got == f"{day:02d}/{month:02d}/{year}", f"{label}: ожидал {day:02d}/{month:02d}/{year}, получил {got!r}"

    def _set_anxiety(self, value: float):
        """Кликнуть стрелки спиннера тревожности, чтобы выставить нужное значение (как человек)."""
        field = self.page.locator(".form-popup .q-field--float.w-20 .q-field__native").first
        current = float(field.evaluate("el => el.value") or 0.5)
        steps = round((value - current) / 0.1)
        if steps == 0:
            return
        arrows = self.page.locator(".form-popup .q-field--float.w-20 .spin-arrows .q-btn")
        btn = arrows.nth(0) if steps > 0 else arrows.nth(1)
        for _ in range(abs(steps)):
            btn.click()
            self.page.wait_for_timeout(60)
        got = float(field.evaluate("el => el.value"))
        assert abs(got - value) < 1e-6, f"тревожность: ожидал {value}, получил {got}"

    def _wait_enrich(self, name: str):
        start = time.time()
        self.page.locator(".result-popup-text").filter(has_text="успешно сохранены").wait_for(state="visible", timeout=300000)
        self.page.get_by_role("button", name="ОК").click()
        self.page.wait_for_timeout(300)
        log.info("обогащение карточки «%s» готово (%ds)", name, time.time() - start)

    def add_hotel(self, h: dict):
        self.page.get_by_role("tab", name="HomeDirect").click()
        self.page.wait_for_timeout(350)
        self.page.get_by_role("button", name="Добавить жилище").click()
        self.page.wait_for_timeout(400)
        self._field("Название дома").fill(h["name"])
        self._field("Описание дома").fill(h["description"])
        self._add_chips("chars-frame", h["characteristics"])
        if not h["rooms"]:
            raise AssertionError(f"{h['name']}: пустой список номеров")
        for (iso_date,) in h["rooms"]:
            y, m, d = map(int, iso_date.split("-"))
            self._pick_date(
                self.page.locator(".form-popup .rooms-frame .q-field--readonly .q-field__native").last,
                y, m, d, f"номер {iso_date} дома «{h['name']}»",
            )
            self.page.locator(".form-popup .rooms-frame .round-plus").click()
            self.page.wait_for_timeout(150)
        self._field("Ограничения").fill(h["restrictions"])
        self.page.get_by_role("button", name="Сохранить").first.click()
        self._wait_enrich(h["name"])
        log.info("дом «%s» создан", h["name"])

    def add_ghost(self, g: dict):
        self.page.get_by_role("tab", name="Guest Ghost").click()
        self.page.wait_for_timeout(350)
        self.page.get_by_role("button", name="Добавить заявку").click()
        self.page.wait_for_timeout(400)
        self._field("Имя приведения").fill(g["name"])
        self._set_anxiety(g["anxiety"])
        self._pick_date(
            self.page.locator(".form-popup .q-field--readonly .q-field__native").first,
            *g["deadline"], f"дедлайн «{g['name']}»",
        )
        self._add_chips("req-frame", g["requirements"])
        self._field("Особые пожелания").fill(g["preferences"])
        self.page.get_by_role("button", name="Сохранить").first.click()
        self._wait_enrich(g["name"])
        log.info("заявка «%s» создана", g["name"])


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(URL)
        page.wait_for_timeout(1500)
        seeder = Seeder(page)
        for i, h in enumerate(HOTELS, start=1):
            log.info("--- дом %d/10: %s", i, h["name"])
            seeder.add_hotel(h)
        for i, g in enumerate(GHOSTS, start=1):
            log.info("--- заявка %d/10: %s", i, g["name"])
            seeder.add_ghost(g)
        browser.close()
        log.info("ЗАЛИВКА ЗАВЕРШЕНА: 10 домов + 10 заявок")


if __name__ == "__main__":
    main()
