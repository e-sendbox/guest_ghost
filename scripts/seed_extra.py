"""Разовый скрипт заливки дополнительных демо-данных через интерфейс (Playwright).

Создан на базе scripts/seed_demo.py — тот же Seeder, новые данные:
  - 10 домов, номера свободны с октября 2026 (все min(free_date) >= 2026-10-01)
  - 10 приведений с дедлайнами ноябрь 2026 — февраль 2027 (пересечение с датами домов)
  - тревожность приведений — все виды: 0.0 (совсем не тревожный), 0.1, 0.5, 0.9, 1.0 (максимально)

Запуск: python3 scripts/seed_extra.py (сервер main.py должен быть поднят)
  - без флагов: 10 домов + 10 заявок
  - --ghosts-only: только заявки (без подбора жилья — заявки остаются в статусе free)
"""

import logging
import re
import time

from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PwTimeoutError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_extra")

URL = "http://localhost:8080"

MONTHS_SHORT = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
MONTHS_FULL = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]

HOTELS = [
    {
        "name": "Гостиница «Полуночный Экспресс»",
        "description": (
            "Старая железнодорожная гостиница у вокзала, где останавливались ещё "
            "кондукторы позапрошлого века. Коридоры длинные, лампы мигают сами собой, "
            "в номерах пахнет угольной пылью и старыми газетами. Поезда грохочут "
            "за окнами до самого рассвета."
        ),
        "characteristics": {
            "шум поездов": "постоянный",
            "запах угля": "стойкий",
            "освещение": "мигающее",
            "сквозняки": "умеренные",
        },
        "restrictions": "без живых постояльцев, без свистков",
        "rooms": [("2026-10-03",), ("2026-11-12",), ("2026-12-08",)],
    },
    {
        "name": "Колокольня Святого Уныния",
        "description": (
            "Высокая колокольня при заброшенной церкви, колокола сняли ещё при "
            "советской власти, но по ночам кто-то всё равно звонит. Винтовая лестница "
            "скрипит на каждом витке, наверху гнездо совы и вид на всё кладбище. "
            "Ветер гудит в проёмах, как орган."
        ),
        "characteristics": {
            "эхо": "гулкое",
            "высота": "большая",
            "ветер": "постоянный",
            "одиночество": "полное",
        },
        "restrictions": "без колоколов, без туристов",
        "rooms": [("2026-10-07",), ("2026-11-18",)],
    },
    {
        "name": "Типография Мёртвых Газет",
        "description": (
            "Подвал бывшей типографии: печатные станки стоят под чехлами, в ящиках "
            "наборные шрифты, на полу — стопки пожелтевших газет столетней давности. "
            "Пахнет свинцом и бумагой. По ночам станки будто сами делают один оборот."
        ),
        "characteristics": {
            "запах бумаги": "стойкий",
            "запах свинца": "есть",
            "тишина": "частичная",
            "пыль": "много",
        },
        "restrictions": "без огня, без читателей",
        "rooms": [("2026-10-11",), ("2026-12-02",), ("2026-12-22",)],
    },
    {
        "name": "Оранжерея Забытых Орхидей",
        "description": (
            "Стеклянная оранжерея в парке усадьбы, крыша давно провалилась, но "
            "орхидеи выжили и разрослись по всем стенам. Внутри влажно и душно, "
            "капли стекают по стёклам, в воздухе — сладкий гнилостный запах цветов. "
            "Ночью оранжерея светится изнутри бледным светом."
        ),
        "characteristics": {
            "влажность": "высокая",
            "запах цветов": "сладкий",
            "освещение": "лунный",
            "температура": "тепло",
        },
        "restrictions": "без садовников, без секаторов",
        "rooms": [("2026-10-14",), ("2026-11-22",)],
    },
    {
        "name": "Каюта «Летучего Голландца»",
        "description": (
            "Списана с парусника, который так и не вернулся в порт: каюта с "
            "иллюминатором, койкой и медным рундуком. Стены качаются, хотя корабля "
            "давно нет, пол пахнет солью и дёгтем. Слышно, как за бортом плещется "
            "вода, которой не существует."
        ),
        "characteristics": {
            "запах соли": "стойкий",
            "качка": "лёгкая",
            "теснота": "уютная",
            "сырость": "высокая",
        },
        "restrictions": "без моряков, без компасов",
        "rooms": [("2026-10-19",), ("2026-11-28",), ("2026-12-15",)],
    },
    {
        "name": "Чердак Астронома",
        "description": (
            "Чердак городского особняка, где жил чудаковатый астроном: в куполе "
            "прорезано круглое окно, под ним — ржавый телескоп на треноге. Пахнет "
            "машинным маслом и старыми картами звёздного неба. По ночам сквозь окно "
            "видно все созвездия, даже в пасмурную погоду."
        ),
        "characteristics": {
            "звёзды": "видно",
            "запах масла": "есть",
            "тишина": "полная",
            "освещение": "звёздное",
        },
        "restrictions": "без телескопов, без астрологов",
        "rooms": [("2026-10-22",), ("2026-12-05",)],
    },
    {
        "name": "Прачечная Призрачных Простыней",
        "description": (
            "Подвал бывшей прачечной: чугунные ванны, каменные столы для стирки, "
            "на верёвках висят простыни, которые никто не снимал полвека. Пар "
            "поднимается от пола даже зимой, пахнет мылом и мокрым бельём. "
            "Простыни иногда колышутся, хотя сквозняков нет."
        ),
        "characteristics": {
            "пар": "постоянный",
            "запах мыла": "стойкий",
            "влажность": "высокая",
            "тишина": "частичная",
        },
        "restrictions": "без стирки, без мыла",
        "rooms": [("2026-10-26",), ("2026-11-30",), ("2026-12-18",)],
    },
    {
        "name": "Сторожка Кладбищенского Сторожа",
        "description": (
            "Маленький домик у ворот кладбища: одна комната, печка, стол у окна. "
            "Сторож ушёл в 1973 году, но чайник на печке до сих пор тёплый. Пахнет "
            "сушёными травами и табаком. Из окна видно все аллеи — никто не пройдёт "
            "незамеченным."
        ),
        "characteristics": {
            "запах трав": "стойкий",
            "тепло": "остаточное",
            "обзор": "полный",
            "тишина": "абсолютная",
        },
        "restrictions": "без посетителей, без лопат",
        "rooms": [("2026-10-29",), ("2026-12-10",)],
    },
    {
        "name": "Бальный Зал Разбитых Зеркал",
        "description": (
            "Парадный зал усадьбы, где когда-то давали балы: паркет вытерт до "
            "блеска, люстры в паутине, вдоль стен — зеркала, каждое с трещиной. "
            "Пахнет воском и пылью. Если встать в центр и прислушаться, слышно "
            "далёкую музыку и шорох платьев."
        ),
        "characteristics": {
            "эхо": "богатое",
            "зеркала": "треснувшие",
            "простор": "большой",
            "запах воска": "есть",
        },
        "restrictions": "без музыки, без танцев",
        "rooms": [("2026-11-02",), ("2026-12-12",), ("2026-12-28",)],
    },
    {
        "name": "Погреб Винодела",
        "description": (
            "Старинный винный погреб: бочки в ряд, бутылки в пыльных нишах, "
            "своды кирпичные. Пахнет дубом и виноградом, хотя виноградник давно "
            "зарос. Температура ровная круглый год, темно, хоть глаз выколи. "
            "Иногда из дальней бочки слышно бульканье."
        ),
        "characteristics": {
            "запах вина": "стойкий",
            "температура": "ровная",
            "темнота": "полная",
            "тишина": "полная",
        },
        "restrictions": "без дегустаций, без пробок",
        "rooms": [("2026-11-05",), ("2026-12-20",)],
    },
]

GHOSTS = [
    {
        "name": "Баронесса фон Шорох",
        "anxiety": 0.0,
        "requirements": {
            "простор": "залы",
            "эхо": "богатое",
        },
        "preferences": (
            "Мне нужен большой зал, где шорох платья разносится по всем углам. "
            "Зеркала приветствуются — я привыкла видеть своё отражение. "
            "Согласна на любой дом, лишь бы было где развернуться."
        ),
        "deadline": (2026, 11, 20),
    },
    {
        "name": "Джек-Фонарщик",
        "anxiety": 0.1,
        "requirements": {
            "освещение": "мигающее",
            "шум поездов": "постоянный",
        },
        "preferences": (
            "Обожаю, когда свет мигает и что-то грохочет за окном. Готов жить "
            "где угодно, лишь бы было шумно и неспокойно. Лампы зажигать — моё "
            "любимое занятие."
        ),
        "deadline": (2026, 12, 5),
    },
    {
        "name": "Монахиня Безмолвия",
        "anxiety": 0.5,
        "requirements": {
            "тишина": "абсолютная",
            "одиночество": "полное",
        },
        "preferences": (
            "Мне нужна полная тишина и одиночество. Хочу высокое место, откуда "
            "видно всё вокруг, но никто не видит меня. Ветер и колокола не мешают, "
            "лишь бы не было людей."
        ),
        "deadline": (2026, 12, 20),
    },
    {
        "name": "Горничная Сырых Простыней",
        "anxiety": 0.9,
        "requirements": {
            "пар": "постоянный",
            "запах мыла": "стойкий",
            "влажность": "высокая",
        },
        "preferences": (
            "Мне нужен именно подвал с паром и запахом мыла. Всё должно быть "
            "влажным и тёплым, как в прачечной. Никаких сквозняков и сухости — "
            "я этого не переношу. Простыни должны колыхаться."
        ),
        "deadline": (2027, 1, 15),
    },
    {
        "name": "Смотритель Звёздного Чердака",
        "anxiety": 1.0,
        "requirements": {
            "звёзды": "видно",
            "тишина": "полная",
            "освещение": "звёздное",
        },
        "preferences": (
            "Только чердак с круглым окном, из которого видно звёзды. Только "
            "полная тишина. Только запах машинного масла и старых карт. "
            "Ничего другого я не приму — идеальное совпадение или ничего."
        ),
        "deadline": (2027, 2, 1),
    },
    {
        "name": "Граф Полуночный",
        "anxiety": 0.0,
        "requirements": {
            "простор": "залы",
            "эхо": "гулкое",
        },
        "preferences": (
            "Мне нужен просторный зал с хорошим эхом, чтобы голос звучал "
            "торжественно. Согласен на любой дом, лишь бы было где развернуться "
            "и постучать тростью по паркету."
        ),
        "deadline": (2026, 11, 25),
    },
    {
        "name": "Шёпотунья",
        "anxiety": 0.1,
        "requirements": {
            "тишина": "полная",
            "пыль": "много",
        },
        "preferences": (
            "Люблю тихие пыльные места, где можно шептать и никто не услышит. "
            "Готова жить почти где угодно, лишь бы было пыльно и безлюдно. "
            "Шелестеть страницами — моё любимое."
        ),
        "deadline": (2026, 12, 10),
    },
    {
        "name": "Дворецкий Молчаливый",
        "anxiety": 0.5,
        "requirements": {
            "запах воска": "есть",
            "зеркала": "есть",
        },
        "preferences": (
            "Мне нужен дом с парадными залами, зеркалами и запахом воска. "
            "Хочу следить за порядком, как в старые времена. Люди не мешают, "
            "но и не нужны."
        ),
        "deadline": (2026, 12, 25),
    },
    {
        "name": "Плакальщица",
        "anxiety": 0.9,
        "requirements": {
            "сырость": "высокая",
            "темнота": "полная",
            "тишина": "абсолютная",
        },
        "preferences": (
            "Мне нужен сырой тёмный подвал в полной тишине. Никакого света, "
            "никаких звуков, только камень и влага. Если хоть что-то не "
            "совпадёт — я не соглашусь."
        ),
        "deadline": (2027, 1, 20),
    },
    {
        "name": "Хранитель Идеала",
        "anxiety": 1.0,
        "requirements": {
            "звёзды": "видно",
            "тишина": "полная",
            "одиночество": "полное",
        },
        "preferences": (
            "Только идеальное совпадение: чердак со звёздами, полная тишина "
            "и одиночество. Ничего меньше я не приму. Лучше ждать вечность, "
            "чем согласиться на несовершенное место."
        ),
        "deadline": (2027, 2, 10),
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
    import sys
    ghosts_only = "--ghosts-only" in sys.argv
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(URL)
        page.wait_for_timeout(1500)
        seeder = Seeder(page)
        if not ghosts_only:
            for i, h in enumerate(HOTELS, start=1):
                log.info("--- дом %d/10: %s", i, h["name"])
                seeder.add_hotel(h)
        for i, g in enumerate(GHOSTS, start=1):
            log.info("--- заявка %d/%d: %s (тревожность %s)", i, len(GHOSTS), g["name"], g["anxiety"])
            seeder.add_ghost(g)
        browser.close()
        if ghosts_only:
            log.info("ЗАЛИВКА ЗАВЕРШЕНА: %d заявок (без подбора жилья)", len(GHOSTS))
        else:
            log.info("ЗАЛИВКА ЗАВЕРШЕНА: 10 домов + %d заявок", len(GHOSTS))


if __name__ == "__main__":
    main()
