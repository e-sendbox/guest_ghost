"""Разовый пилот: полный флоу 1 дом + 1 заявка, отладка селекторов календаря, чипов, попапов."""

import time
import re
from playwright.sync_api import sync_playwright

URL = "http://localhost:8080"

MONTHS_SHORT = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
MONTHS_FULL = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]


def month_num(text: str):
    low = text.strip().lower()
    for i, m in enumerate(MONTHS_FULL, start=1):
        if m.lower() in low:
            return i
    for i, m in enumerate(MONTHS_SHORT, start=1):
        if m.lower() in low:
            return i
    return None


def pick_date(page, field_locator, target: str, year: int, month: int, day: int, label=""):
    field_locator.click()
    page.locator(".q-date").first.wait_for(state="visible", timeout=5000)
    nav = page.locator(".q-date__navigation .q-btn")
    cur_month = month_num(nav.nth(1).inner_text())
    cur_year = int(nav.nth(4).inner_text().split()[-1])
    print(f"[probe] {label} сейчас в календаре: {cur_month}.{cur_year}")
    steps = (year - cur_year) * 12 + (month - cur_month)
    btn = nav.nth(2) if steps > 0 else nav.nth(0)
    for _ in range(abs(steps)):
        btn.click()
    page.wait_for_timeout(200)
    day_btns = page.locator(".q-date:not([class*='month']) .q-btn:not([class*='nav'])")
    day_btn = day_btns.filter(has_text=re.compile(f"^{day}$")).first
    day_btn.click()
    page.wait_for_timeout(300)
    print(f"[probe] {label} значение поля после выбора: {field_locator.evaluate('el => el.value')!r}")
    assert field_locator.evaluate("el => el.value") == f"{day:02d}/{month:02d}/{year}", "дата не применилась"


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(URL)
    page.wait_for_timeout(1200)

    # ---------- ДОМ ----------
    page.get_by_role("tab", name="HomeDirect").click()
    page.wait_for_timeout(500)
    page.get_by_role("button", name="Добавить жилище").click()
    page.wait_for_timeout(800)

    def fld(anchor, frame=".form-popup"):
        return page.locator(f"{frame} .q-field").filter(has_text=anchor).locator(".q-field__native")

    fld("Название дома").fill("Пилотный Замок Мрак")
    fld("Описание дома").fill("Старинный замок в глухом лесу, где веками царит сырость и плесень.")

    page.locator(".chars-frame .w-56").fill("освещение")
    page.locator(".chars-frame .flex-1").fill("светло")
    page.locator(".chars-frame .round-plus").click()
    page.wait_for_timeout(200)
    print("[probe] чипов в chars-frame:", page.locator(".chars-frame .q-chip").count())

    page.locator(".chars-frame .w-56").fill("уровень шума")
    page.locator(".chars-frame .flex-1").fill("низкий")
    page.locator(".chars-frame .round-plus").click()
    page.wait_for_timeout(200)
    print("[probe] чипов в chars-frame:", page.locator(".chars-frame .q-chip").count())

    fld("Ограничения").fill("без живых людей, без котов")

    page.locator(".rooms-frame .round-plus").click()
    page.wait_for_timeout(200)
    print("[probe] комнат:", page.locator(".rooms-frame .room-card").count())

    pick_date(page, page.locator(".form-popup .rooms-frame .q-field--readonly .q-field__native"), target="rooms", year=2026, month=10, day=15, label="Дата номера")

    page.get_by_role("button", name="Сохранить").first.click()
    print("[probe] Сохранить нажат, жду результат (LLM может быть долгим)...")
    start = time.time()
    page.locator(".result-popup-text").filter(has_text="успешно сохранены").wait_for(state="visible", timeout=300000)
    print(f"[probe] попап успеха через {time.time()-start:.0f}с")
    page.get_by_role("button", name="ОК").click()
    page.wait_for_timeout(400)

    # ---------- ПРИВЕДЕНИЕ ----------
    page.get_by_role("tab", name="Guest Ghost").click()
    page.wait_for_timeout(500)
    page.get_by_role("button", name="Добавить заявку").click()
    page.wait_for_timeout(800)

    fld("Имя приведения").fill("Пилотный Дух")
    pick_date(page, page.locator(".form-popup .q-field--readonly .q-field__native").first, target="deadline", year=2026, month=6, day=20, label="Дедлайн")

    page.locator(".req-frame .w-56").fill("сырость")
    page.locator(".req-frame .flex-1").fill("нужна")
    page.locator(".req-frame .round-plus").click()
    page.wait_for_timeout(200)
    print("[probe] чипов в req-frame:", page.locator(".req-frame .q-chip").count())

    fld("Особые пожелания").fill("Полная темнота и ни одного живого существа поблизости.")

    page.get_by_role("button", name="Сохранить").first.click()
    print("[probe] Сохранить нажат, жду результат...")
    start = time.time()
    page.locator(".result-popup-text").filter(has_text="успешно сохранены").wait_for(state="visible", timeout=300000)
    print(f"[probe] попап успеха через {time.time()-start:.0f}с")
    page.get_by_role("button", name="ОК").click()
    page.wait_for_timeout(400)

    browser.close()
    print("[probe] ПИЛОТ ЗАВЕРШЁН")
