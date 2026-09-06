"""Диагностика: пошаговое состояние календаря при кликах по полю."""

from playwright.sync_api import sync_playwright

URL = "http://localhost:8080"


def show(page, tag):
    date_vis = page.locator(".q-date").first.is_visible() if page.locator(".q-date").count() else False
    nav_cnt = page.locator(".q-date__navigation .q-btn").count() if date_vis else -1
    print(f"[{tag}] q-date виден: {date_vis}, nav кнопок: {nav_cnt}")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(URL)
    page.wait_for_timeout(1500)
    page.get_by_role("tab", name="HomeDirect").click()
    page.wait_for_timeout(350)
    page.get_by_role("button", name="Добавить жилище").click()
    page.wait_for_timeout(400)
    field = page.locator(".form-popup .rooms-frame .q-field--readonly .q-field__native").first
    show(page, "старт")
    field.click()
    page.wait_for_timeout(300)
    show(page, "клик1 (без ожидания видимости)")
    field.click()
    page.wait_for_timeout(300)
    show(page, "клик2")
    page.wait_for_timeout(1000)
    show(page, "+1с")
    browser.close()
