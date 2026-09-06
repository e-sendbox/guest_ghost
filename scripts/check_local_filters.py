"""Playwright-проверка шага 11: локальные фильтры на обеих страницах.

Запуск: python3 scripts/check_local_filters.py (сервер main.py должен быть поднят)
"""

import logging
import re
import sys

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("check_lf")

URL = "http://localhost:8080"
PASS = 0
FAIL = 0


def check(name: str, cond: bool, extra: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        log.info("PASS: %s %s", name, extra)
    else:
        FAIL += 1
        log.error("FAIL: %s %s", name, extra)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(URL)
        page.wait_for_timeout(2000)

        # ---------- Страница заявок ----------
        page.get_by_role("tab", name="Guest Ghost").click()
        page.wait_for_timeout(3000)
        page.locator(".request-card").first.wait_for(state="visible", timeout=10000)

        cards = page.locator(".request-card")
        total = cards.count()
        check("заявки загружены", total == 20, f"count={total}")

        # панель локальных фильтров
        lf_wrap = page.locator(".lfilter-groups")
        lf_groups = page.locator(".local-filters")
        check("панель фильтров видна", lf_wrap.is_visible())
        header = page.locator(".page-header").first
        lf_box = lf_wrap.bounding_box()
        hd_box = header.bounding_box()
        check("панель прижата к правому краю",
              lf_box is not None and hd_box is not None and lf_box["x"] + lf_box["width"] > hd_box["x"] + hd_box["width"] - 30)
        check("панель на одной строке с заголовком",
              lf_box is not None and hd_box is not None and abs(lf_box["y"] - hd_box["y"]) < 20)
        check("две группы кнопок", lf_groups.count() == 2)
        check("вертикальная черта слева", "1px" in lf_groups.nth(0).evaluate("el => getComputedStyle(el).borderLeftWidth")
              and "1px" in lf_groups.nth(1).evaluate("el => getComputedStyle(el).borderLeftWidth"))

        # кнопки панели
        check("кнопка «Развернуть все»", page.locator(".lfilter-btn").nth(0).is_visible())
        check("кнопка «Свернуть все»", page.locator(".lfilter-btn").nth(1).is_visible())
        check("кнопка «Фильтр: статус заявки»", page.locator(".lfilter-btn").nth(2).is_visible())
        check("кнопка «Фильтр: номер заявки»", page.locator(".lfilter-btn").nth(3).is_visible())
        check("кнопка сортировки", page.locator(".lfilter-btn").nth(4).is_visible())
        check("кнопка сортировки овальная", "oval" in page.locator(".lfilter-btn").nth(4).get_attribute("class"))
        check("кнопка сброса", page.locator(".lfilter-btn").nth(5).is_visible())
        page.locator(".lfilter-btn").nth(0).hover()
        page.wait_for_timeout(500)
        check("tooltip у кнопок", page.locator(".q-tooltip:visible").count() > 0)
        page.locator(".lfilter-btn").nth(2).hover()
        page.wait_for_timeout(500)
        check("tooltip «Фильтр: статус заявки»", page.locator(".q-tooltip:visible").filter(has_text="Фильтр: статус заявки").count() > 0)
        page.locator(".lfilter-btn").nth(3).hover()
        page.wait_for_timeout(500)
        check("tooltip «Фильтр: номер заявки»", page.locator(".q-tooltip:visible").filter(has_text="Фильтр: номер заявки").count() > 0)
        page.locator(".lfilter-btn").nth(4).hover()
        page.wait_for_timeout(500)
        check("tooltip «Сортировка: по соответствию»", page.locator(".q-tooltip:visible").filter(has_text="Сортировка: по соответствию выбранного дома").count() > 0)

        # выпадашки
        check("кнопка «Статус заявки»", page.locator(".lfilter-btn").nth(2).is_visible())
        check("кнопка «№ заявки»", page.locator(".lfilter-btn").nth(3).is_visible())

        # --- Развернуть все / Свернуть все ---
        page.mouse.move(0, 0)  # убрать hover, чтобы tooltip не перекрывал кнопку
        page.wait_for_timeout(300)
        expanded_before = page.locator(".request-card-detail:visible").count()
        page.locator(".lfilter-btn").nth(0).click(force=True)  # unfold_more
        page.wait_for_timeout(1500)
        expanded_after = page.locator(".request-card-detail:visible").count()
        check("«Развернуть все» раскрыл карточки", expanded_after > expanded_before,
              f"before={expanded_before} after={expanded_after}")
        check("раскрыты только карточки с домами", expanded_after == 14, f"count={expanded_after}")

        page.mouse.move(0, 0)  # убрать hover, чтобы tooltip не перекрывал кнопку
        page.wait_for_timeout(300)
        page.locator(".lfilter-btn").nth(1).click(force=True)  # unfold_less
        page.wait_for_timeout(1500)
        expanded_after2 = page.locator(".request-card-detail:visible").count()
        check("«Свернуть все» свернул карточки", expanded_after2 == 0, f"count={expanded_after2}")

        # --- Фильтр «Статус заявки» ---
        check("статус выкл: кнопка не подсвечена", "active" not in page.locator(".lfilter-btn").nth(2).get_attribute("class"))
        check("номер выкл: кнопка не подсвечена", "active" not in page.locator(".lfilter-btn").nth(3).get_attribute("class"))
        page.locator(".lfilter-btn").nth(2).click()  # статус
        page.wait_for_timeout(500)
        menu = page.locator(".lfilter-menu:visible")
        check("меню статусов открылось", menu.count() > 0)
        check("чекбоксы статусов: free/chosen/reserved",
              menu.locator(".q-checkbox").count() == 3, f"count={menu.locator('.q-checkbox').count()}")
        status_texts = [menu.locator(".q-checkbox").nth(i).inner_text() for i in range(3)]
        check("статусы на русском по порядку", status_texts == ["не заселен", "подобран дом", "заселен"], str(status_texts))
        # выберем только free
        free_cb = menu.locator(".q-checkbox").filter(has_text="не заселен")
        free_cb.click()
        page.wait_for_timeout(600)
        visible_cards = page.locator(".request-card:visible").count()
        check("фильтр по статусу free: 6 заявок", visible_cards == 6, f"count={visible_cards}")
        check("статус включён: кнопка подсвечена", "active" in page.locator(".lfilter-btn").nth(2).get_attribute("class"))
        # проверим, что это именно free
        free_names = [page.locator(".request-card:visible .request-name").nth(i).inner_text() for i in range(visible_cards)]
        check("видимые заявки — free", all(n in ("Шепчущий Нерон", "Граф Полуночный", "Шёпотунья", "Дворецкий Молчаливый", "Плакальщица", "Хранитель Идеала") for n in free_names), str(free_names))

        # --- Взаимное уменьшение: «№ заявки» при выбранном free ---
        page.locator(".lfilter-btn").nth(3).click()  # № заявки
        page.wait_for_timeout(500)
        id_menu = page.locator(".lfilter-menu:visible")
        id_items = id_menu.locator(".q-checkbox").count()
        check("«№ заявки» сужен до free-заявок (6)", id_items == 6, f"count={id_items}")
        check("«Номер • Имя приведения»", "•" in id_menu.locator(".q-checkbox").nth(0).inner_text()
              and id_menu.locator(".q-checkbox").nth(0).inner_text().strip()[:1].isdigit())
        # выберем одну заявку
        id_menu.locator(".q-checkbox").nth(0).click()
        page.wait_for_timeout(600)
        visible_cards2 = page.locator(".request-card:visible").count()
        check("фильтр по № заявки: 1 заявка", visible_cards2 == 1, f"count={visible_cards2}")
        check("номер включён: кнопка подсвечена", "active" in page.locator(".lfilter-btn").nth(3).get_attribute("class"))

        # --- Сортировка ---
        # выкл: стрелка скрыта, только иконка соответствия
        check("сортировка выкл: стрелка скрыта", not page.locator(".sort-arrow").is_visible())
        page.mouse.move(0, 0)
        page.wait_for_timeout(300)
        page.locator(".lfilter-btn").nth(4).click(force=True)  # sort desc
        page.wait_for_timeout(600)
        check("сортировка: кнопка активна", "active" in page.locator(".lfilter-btn").nth(4).get_attribute("class"))
        check("сортировка desc: стрелка вверх", page.locator(".sort-arrow").is_visible()
              and page.locator(".sort-arrow").inner_text() == "arrow_upward")
        # сбросим фильтры, чтобы проверить сортировку на полном списке
        page.keyboard.press("Escape")  # закрыть меню, если открыто
        page.wait_for_timeout(300)
        page.mouse.move(0, 0)
        page.wait_for_timeout(300)
        page.locator(".lfilter-btn").nth(5).click(force=True)  # reset
        page.wait_for_timeout(600)
        visible_cards3 = page.locator(".request-card:visible").count()
        check("сброс фильтров: все 20 заявок", visible_cards3 == 20, f"count={visible_cards3}")
        check("сброс: кнопки фильтров не подсвечены",
              "active" not in page.locator(".lfilter-btn").nth(2).get_attribute("class")
              and "active" not in page.locator(".lfilter-btn").nth(3).get_attribute("class")
              and "active" not in page.locator(".lfilter-btn").nth(4).get_attribute("class"))
        check("сброс: стрелка скрыта", not page.locator(".sort-arrow").is_visible())
        # сортировка по убыванию: первая — с макс match_percent (Грызлик 85)
        page.mouse.move(0, 0)
        page.wait_for_timeout(300)
        page.locator(".lfilter-btn").nth(4).click(force=True)
        page.wait_for_timeout(600)
        first_name = page.locator(".request-card:visible .request-name").first.inner_text()
        check("сортировка по убыванию: первая — Грызлик (85%)", first_name == "Грызлик Книжный", first_name)
        # по возрастанию: free-заявки в начале
        page.mouse.move(0, 0)
        page.wait_for_timeout(300)
        page.locator(".lfilter-btn").nth(4).click(force=True)
        page.wait_for_timeout(600)
        check("сортировка asc: стрелка вниз", page.locator(".sort-arrow").is_visible()
              and page.locator(".sort-arrow").inner_text() == "arrow_downward")
        first_name2 = page.locator(".request-card:visible .request-name").first.inner_text()
        check("сортировка по возрастанию: free в начале", first_name2 in ("Шепчущий Нерон", "Граф Полуночный", "Шёпотунья", "Дворецкий Молчаливый", "Плакальщица", "Хранитель Идеала"), first_name2)
        # сброс сортировки
        page.mouse.move(0, 0)
        page.wait_for_timeout(300)
        page.locator(".lfilter-btn").nth(4).click(force=True)
        page.wait_for_timeout(600)
        check("сортировка выкл после цикла: стрелка скрыта", not page.locator(".sort-arrow").is_visible())
        first_name3 = page.locator(".request-card:visible .request-name").first.inner_text()
        check("сброс сортировки: по id (Сэм)", first_name3 == "Сэм Блуждающий", first_name3)

        # --- Персистентность: перезагрузка страницы ---
        page.locator(".lfilter-btn").nth(2).click()
        page.wait_for_timeout(500)
        page.locator(".lfilter-menu:visible .q-checkbox").filter(has_text="подобран дом").click()
        page.wait_for_timeout(600)
        visible_cards4 = page.locator(".request-card:visible").count()
        check("фильтр chosen: 7 заявок", visible_cards4 == 7, f"count={visible_cards4}")
        page.reload()
        page.wait_for_timeout(2000)
        visible_cards5 = page.locator(".request-card:visible").count()
        check("фильтр восстановлен после перезагрузки (chosen: 7)", visible_cards5 == 7, f"count={visible_cards5}")
        # сбросим для чистоты
        page.locator(".lfilter-btn").nth(5).click()
        page.wait_for_timeout(600)

        # ---------- Страница домов ----------
        page.get_by_role("tab", name="HomeDirect").click()
        page.wait_for_timeout(1500)

        hotel_cards = page.locator(".hotel-card")
        total_h = hotel_cards.count()
        check("дома загружены", total_h == 20, f"count={total_h}")

        lf2 = page.locator(".local-filters")
        check("панель фильтров на HomeDirect видна", lf2.is_visible())
        header2 = page.locator(".page-header").first
        lf2_box = lf2.bounding_box()
        hd2_box = header2.bounding_box()
        check("панель HomeDirect прижата к правому краю",
              lf2_box is not None and hd2_box is not None and lf2_box["x"] + lf2_box["width"] > hd2_box["x"] + hd2_box["width"] - 30)
        check("панель HomeDirect на одной строке с заголовком",
              lf2_box is not None and hd2_box is not None and abs(lf2_box["y"] - hd2_box["y"]) < 20)
        check("поле «Поиск по подстроке»", page.locator(".lfilter-search").is_visible())
        check("кнопка «Доля занятых мест»", page.locator(".fill-btn").is_visible())
        check("кнопка сброса на HomeDirect", page.locator(".lfilter-btn").count() == 2)

        # --- размеры: поиск 220x28, кнопка 28px высотой ---
        s_box = page.locator(".lfilter-search").bounding_box()
        check("поиск: ширина ~220px", s_box is not None and abs(s_box["width"] - 220) < 10, f"w={s_box['width'] if s_box else '?'}")
        check("поиск: высота ~28px", s_box is not None and abs(s_box["height"] - 28) < 4, f"h={s_box['height'] if s_box else '?'}")
        f_box = page.locator(".fill-btn").bounding_box()
        check("кнопка занятости: высота ~28px", f_box is not None and abs(f_box["height"] - 28) < 4, f"h={f_box['height'] if f_box else '?'}")
        check("кнопка занятости: фикс. ширина ~150px", f_box is not None and abs(f_box["width"] - 150) < 10, f"w={f_box['width'] if f_box else '?'}")

        # --- Фильтр занятости ---
        fb = page.locator(".fill-btn")
        check("кнопка выключена: текст «Доля занятых мест»", fb.inner_text() == "Доля занятых мест")
        check("кнопка выключена: без active", "active" not in fb.get_attribute("class"))
        fb.click()
        page.wait_for_timeout(600)
        fmenu = page.locator(".lfilter-menu:visible").first
        check("меню занятости: 4 пункта", fmenu.locator(".q-item").count() == 4,
              f"count={fmenu.locator('.q-item').count()}")
        fmenu.locator(".q-item").filter(has_text="50%-99%").click()
        page.wait_for_timeout(600)
        visible_h = page.locator(".hotel-card:visible").count()
        check("«занято 50%-99%»: 5 домов", visible_h == 5, f"count={visible_h}")
        check("кнопка: текст «занято 50%-99%»", fb.inner_text() == "занято 50%-99%")
        check("кнопка: active", "active" in fb.get_attribute("class"))
        # 0%
        fb.click()
        page.wait_for_timeout(600)
        page.locator(".lfilter-menu:visible .q-item").filter(has_text="занято 0%").click()
        page.wait_for_timeout(600)
        visible_h0 = page.locator(".hotel-card:visible").count()
        check("«занято 0%»: 15 домов", visible_h0 == 15, f"count={visible_h0}")
        check("кнопка: текст «занято 0%»", fb.inner_text() == "занято 0%")
        # 100% — нет таких
        fb.click()
        page.wait_for_timeout(600)
        page.locator(".lfilter-menu:visible .q-item").filter(has_text="занято 100%").click()
        page.wait_for_timeout(600)
        visible_h100 = page.locator(".hotel-card:visible").count()
        check("«занято 100%»: 0 домов", visible_h100 == 0, f"count={visible_h100}")
        # сбросим фильтр занятости перед поиском
        page.locator(".lfilter-btn").last.click()
        page.wait_for_timeout(600)

        # --- Поиск по подстроке ---
        search_input = page.locator(".lfilter-search")
        search_input.fill("библиотека")
        page.wait_for_timeout(600)
        visible_h2 = page.locator(".hotel-card:visible").count()
        check("поиск «библиотека»: 1 дом", visible_h2 == 1, f"count={visible_h2}")
        if visible_h2 == 1:
            name2 = page.locator(".hotel-card:visible .hotel-card-name").first.inner_text()
            check("это Библиотека Призрачного Смотрителя", name2 == "Библиотека Призрачного Смотрителя", name2)

        # поиск по характеристике (ключ: значение)
        search_input.fill("сырость: высокая")
        page.wait_for_timeout(600)
        visible_h3 = page.locator(".hotel-card:visible").count()
        check("поиск по характеристике «сырость: высокая»: 3 дома", visible_h3 == 3, f"count={visible_h3}")

        # --- Сброс ---
        page.locator(".lfilter-btn").last.click()
        page.wait_for_timeout(600)
        visible_h4 = page.locator(".hotel-card:visible").count()
        check("сброс фильтров домов: все 20", visible_h4 == 20, f"count={visible_h4}")
        check("сброс: кнопка «Доля занятых мест»", fb.inner_text() == "Доля занятых мест")
        check("сброс: без active", "active" not in fb.get_attribute("class"))

        # --- Персистентность домов ---
        search_input.fill("мельница")
        page.wait_for_timeout(600)
        page.reload()
        page.wait_for_timeout(2000)
        visible_h5 = page.locator(".hotel-card:visible").count()
        check("поиск домов восстановлен после перезагрузки (1)", visible_h5 == 1, f"count={visible_h5}")
        page.locator(".lfilter-btn").last.click()
        page.wait_for_timeout(600)

        browser.close()

    log.info("ИТОГ: PASS=%d FAIL=%d", PASS, FAIL)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
