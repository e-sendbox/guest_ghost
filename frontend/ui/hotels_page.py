"""Вкладка HomeDirect (шаг 1: справочник домов; шаг 2: попап «Добавить жилище»; шаг 9: сетка карточек; шаг 10: фильтр from_request).

3 фрейма по ширине окна:
  - верхний: полоска с заголовком «Карточки домов» (+ [из заявки N] слева, шаг 10)
  - основной: сетка карточек домов (адаптивная, пересборка при открытии вкладки)
  - нижний: панель кнопок (кнопка «Добавить жилище» открывает попап)
"""

import asyncio
import logging
from datetime import date

from nicegui import app, ui

from frontend.api.client import ApiClient
from frontend.ui.widgets import ChipGroup, GhostLoader, ResultPopup, date_picker, number_spinner, to_display, to_iso

logger = logging.getLogger(__name__)


def build_hotels_page(config: dict, filters: dict | None = None):
    filters = filters or {}
    api = ApiClient(config.get("app", {}).get("api_url", "http://localhost:8080/api"))

    rooms = []

    with ui.column().classes("w-full h-full").style("gap: 0") as page:
        with ui.element("div").classes("w-full page-header"):
            with ui.row().classes("items-center").style("gap: 8px"):
                ui.label("Карточки домов").classes("text-h6")
                if filters.get("filter") == "from_request":
                    ui.label(f"[из заявки {filters.get('request_id', '')}]").classes("page-filter-tag")
                with ui.row().classes("local-filters").style("gap: 6px"):
                    search_input = ui.input(label="Поиск по подстроке").classes("lfilter-search").props("outlined dense")
                    fill_btn = ui.button("Доля занятых мест").props("flat dense no-caps").classes("lfilter-btn fill-btn")
                    with fill_btn:
                        with ui.menu().classes("lfilter-menu").props("no-focus") as fill_menu:
                            pass
                    reset_btn = ui.button(icon="filter_alt_off").props("flat round dense").classes("lfilter-btn").tooltip("Сбросить фильтры")
        with ui.element("div").classes("w-full flex-1 page-body hotels-grid-area"):
            hotels_area = ui.element("div").classes("w-full hotels-grid")
            hotels_empty = ui.label("Список домов пуст.").classes("page-empty")
            loader = GhostLoader(text="Призываем дома...")
        with ui.element("div").classes("w-full page-footer"):
            with ui.row().classes("w-full items-center gap-2"):
                add_btn = ui.button("Добавить жилище").props("no-caps flat").classes("page-btn")

    with ui.dialog() as dialog, ui.card().classes("form-popup"):
        with ui.column().classes("w-full h-full").style("gap: 0"):
            with ui.element("div").classes("w-full popup-head"):
                ui.label("Добавить жилище").classes("text-h6")

            with ui.column().classes("w-full flex-1 popup-body").style("gap: 12px"):
                name_input = ui.input("Название дома (обязательно)").classes("w-full")
                desc_input = ui.textarea("Описание дома (обязательно)").classes("w-full tall-field").props("rows=3")

                with ui.column().classes("w-full panel-frame chars-frame").style("gap: 8px"):
                    with ui.row().classes("w-full items-center gap-2 panel-header"):
                        ui.label("Добавить характеристику").classes("panel-label")
                        chip_group = ChipGroup()
                    with ui.column().classes("w-full panel-box").style("gap: 6px"):
                        chip_group.build_area()

                restrictions_input = ui.textarea("Ограничения через запятую").classes("w-full tall-field").props("rows=3")

                with ui.column().classes("w-full panel-frame rooms-frame").style("gap: 8px"):
                    with ui.row().classes("w-full items-center gap-2 panel-header"):
                        ui.label("Добавить в номерной фонд").classes("panel-label")
                        rooms_count = number_spinner(value=1, min_value=1, precision=0).classes("w-20")
                        ui.label("место с ближайшей датой заселения").classes("panel-label")
                        rooms_date = date_picker(iso_value=date.today().isoformat(), classes="w-36")
                        rooms_add_btn = ui.button(icon="add").props("flat round dense").classes("round-plus")

                    with ui.column().classes("w-full panel-box").style("gap: 6px") as rooms_box:
                        rooms_area = ui.row().classes("w-full panel-area")
                        rooms_empty = ui.icon("meeting_room").classes("panel-empty")

            error_label = ui.label("").classes("popup-error")
            with ui.element("div").classes("w-full popup-footer"):
                save_btn = ui.button("Сохранить").props("no-caps flat").classes("page-btn save-btn")

    def _add_rooms():
        count = int(rooms_count.value or 1)
        free_date = to_iso(rooms_date.value)
        for _ in range(count):
            rooms.append({"free_date": free_date})
        rooms_box.classes(remove="error")
        _refresh_rooms()

    def _remove_room(idx: int):
        rooms.pop(idx)
        _refresh_rooms()

    def _refresh_rooms():
        rooms_area.clear()
        rooms_empty.set_visibility(not rooms)
        with rooms_area:
            for idx, room in enumerate(rooms):
                with ui.card().classes("room-card"):
                    with ui.column().classes("w-full items-center").style("gap: 2px"):
                        ui.label(f"Номер {idx + 1}").classes("room-title")
                        ui.label(to_display(room["free_date"])).classes("room-date")
                        ui.icon("close").classes("room-close").on("click", lambda i=idx: _remove_room(i))

    async def _save():
        error_label.text = ""
        fields = [
            (name_input, "Название дома"),
            (desc_input, "Описание дома"),
            (rooms_date, "Дата заселения"),
        ]
        has_empty = False
        for field, _ in fields:
            field.props(remove="error")
        for field, _ in fields:
            if not (field.value or "").strip():
                field.props(add="error")
                has_empty = True
        if not chip_group.items:
            chip_group.set_error(True)
            has_empty = True
        else:
            chip_group.set_error(False)
        if not rooms:
            rooms_box.classes(add="error")
            has_empty = True
        else:
            rooms_box.classes(remove="error")
        if has_empty:
            return
        data = {
            "name": name_input.value,
            "description": desc_input.value,
            "characteristics": chip_group.items,
            "restrictions": [r.strip() for r in (restrictions_input.value or "").split(",") if r.strip()],
            "rooms": rooms,
        }
        try:
            result = await asyncio.to_thread(api.create_hotel, data)
        except ValueError as e:
            error_label.text = str(e)
            return
        await _enrich_and_notify(result["id"], data)

    async def _enrich_and_notify(card_id: int, data: dict):
        """Обогащение карточки дома после сохранения метаданных, до закрытия формы."""
        saving_dialog.open()
        logger.info("hotels_page: старт обогащения, card_id=%s", card_id)
        status = await asyncio.to_thread(api.enrich, "hotel", card_id, data)
        saving_dialog.close()
        logger.info("hotels_page: обогащение завершено, status=%s", status)
        dialog.close()
        _reset_form()
        if status == "success":
            success_popup.text = "Данные карточки успешно сохранены"
            success_popup.open()
        else:
            success_popup.text = "Карточку дома не удалось обогатить, LLM не отвечает. Дом не доступен для заселения, но сохранен в базу данных. Передайте администратору id карточки дома для восстановления карточки."
            success_popup.open()

    # попап-спиннер «осмысление данных» — компактный
    with ui.dialog().props("persistent") as saving_dialog, ui.card().classes("result-popup"):
        with ui.column().classes("w-full items-center").style("gap: 12px"):
            ui.spinner("dots", size="32px").classes("text-primary")
            ui.label("Осмысление введённых данных...").classes("result-popup-text")

    success_popup = ResultPopup()

    def _reset_form():
        name_input.value = ""
        desc_input.value = ""
        chip_group.clear()
        restrictions_input.value = ""
        rooms.clear()
        rooms_date.value = date.today().strftime("%d/%m/%Y")
        rooms_count.value = 1
        _refresh_rooms()

    def _load_characteristics():
        try:
            options = api.get_characteristics()
            chip_group.autocomplete.set_options(options)
            logger.info("hotels_page: каталог характеристик подгружен, count=%s", len(options))
        except Exception as e:
            logger.error("hotels_page: не удалось подгрузить каталог характеристик: %s", e)

    def _open_dialog():
        dialog.open()
        chip_group.refresh()
        asyncio.create_task(asyncio.to_thread(_load_characteristics))

    # ---------- Шаг 9: сетка карточек домов ----------

    def _render_hotels(hotels: list[dict]):
        hotels_area.clear()
        hotels_empty.set_visibility(not hotels)
        if not hotels:
            return
        with hotels_area:
            for h in hotels:
                with ui.card().classes("hotel-card"):
                    with ui.column().classes("w-full").style("gap: 8px"):
                        ui.label(h["name"]).classes("hotel-card-name")
                        ui.label(h["description"]).classes("hotel-card-text")
                        if h["characteristics"]:
                            chars = ", ".join(f"{k}: {v}" for k, v in h["characteristics"].items())
                            with ui.row().classes("w-full items-baseline").style("gap: 4px"):
                                ui.label("•").classes("hotel-card-bullet-dot")
                                ui.label("Характеристики: ").classes("hotel-card-label")
                                ui.label(chars).classes("hotel-card-text")
                        if h["restrictions"]:
                            restrictions = ", ".join(h["restrictions"])
                            with ui.row().classes("w-full items-baseline").style("gap: 4px"):
                                ui.label("•").classes("hotel-card-bullet-dot")
                                ui.label("Ограничения: ").classes("hotel-card-label")
                                ui.label(restrictions).classes("hotel-card-text")
                        with ui.row().classes("w-full items-center").style("gap: 4px"):
                            ui.chip(f"Вместимость: {h['total_rooms']}").classes("hotel-chip")
                            ui.chip(f"Доступно мест: {h['free_rooms']}").classes("hotel-chip")

    _all_hotels: list[dict] = []

    _local = app.storage.user.get("hd_filters") or {}
    _local_fill: str | None = _local.get("fill")
    _local_search: str = _local.get("search") or ""

    FILL_OPTIONS = [
        ("100", "занято 100%"),
        ("50-99", "занято 50%-99%"),
        ("1-49", "занято 1%-49%"),
        ("0", "занято 0%"),
    ]

    def _save_local():
        app.storage.user["hd_filters"] = {"fill": _local_fill, "search": _local_search}

    def _hotel_text(h: dict) -> str:
        parts = [str(h.get("name") or ""), str(h.get("description") or "")]
        chars = h.get("characteristics") or {}
        if isinstance(chars, dict):
            parts.append(", ".join(f"{k}: {v}" for k, v in chars.items()))
        restr = h.get("restrictions") or []
        if isinstance(restr, list):
            parts.append(", ".join(str(x) for x in restr))
        return " ".join(parts).lower()

    def _occupied_percent(h: dict) -> int:
        total = h.get("total_rooms") or 0
        free = h.get("free_rooms") or 0
        if total <= 0:
            return 0
        return round((total - free) / total * 100)

    def _fill_matches(pct: int, key: str) -> bool:
        if key == "100":
            return pct == 100
        if key == "50-99":
            return 50 <= pct <= 99
        if key == "1-49":
            return 1 <= pct <= 49
        if key == "0":
            return pct == 0
        return False

    def _apply_local(hotels: list[dict]) -> list[dict]:
        result = hotels
        if _local_fill is not None:
            result = [h for h in result if _fill_matches(_occupied_percent(h), _local_fill)]
        if _local_search:
            needle = _local_search.lower()
            result = [h for h in result if needle in _hotel_text(h)]
        return result

    def _fetch_hotels() -> list[dict]:
        return api.get_hotels(
            filter=filters.get("filter"),
            request_id=int(filters["request_id"]) if filters.get("request_id") else None,
        )

    def _refresh_hotels():
        try:
            hotels = _fetch_hotels()
            _all_hotels[:] = hotels
            _render_hotels(_apply_local(hotels))
            logger.info("hotels_page: список домов подгружен, count=%s", len(hotels))
        except Exception as e:
            logger.error("hotels_page: не удалось загрузить список домов: %s", e)

    def _update_fill_btn():
        fill_btn.classes(remove="active")
        if _local_fill is not None:
            fill_btn.set_text(dict(FILL_OPTIONS).get(_local_fill, _local_fill))
            fill_btn.classes(add="active")
        else:
            fill_btn.set_text("Доля занятых мест")

    def _rebuild_fill_menu():
        fill_menu.clear()
        with fill_menu:
            for key, label in FILL_OPTIONS:
                with ui.item().props("dense").classes("fill-item" + (" active" if key == _local_fill else "")):
                    ui.label(label).on("click", lambda _key=key: _pick_fill(_key))

    def _pick_fill(key: str):
        nonlocal _local_fill
        _local_fill = key
        _save_local()
        _update_fill_btn()
        _render_hotels(_apply_local(_all_hotels))
        fill_menu.close()

    def _on_search_change(e):
        nonlocal _local_search
        _local_search = (e.value or "").strip()
        _save_local()
        _render_hotels(_apply_local(_all_hotels))

    def _reset_local():
        nonlocal _local_fill, _local_search
        _local_fill = None
        _local_search = ""
        _save_local()
        _update_fill_btn()
        search_input.value = ""
        _render_hotels(_apply_local(_all_hotels))

    def _open_fill_menu():
        _rebuild_fill_menu()
        fill_menu.open()

    search_input.on_value_change(_on_search_change)
    fill_btn.on("click", _open_fill_menu)
    reset_btn.on("click", _reset_local)
    _update_fill_btn()
    if _local_search:
        search_input.value = _local_search

    add_btn.on("click", _open_dialog)
    rooms_add_btn.on("click", _add_rooms)
    save_btn.on("click", _save)

    _refresh_rooms()
    chip_group.refresh()
    # первичная загрузка списка при открытии страницы
    async def _initial_load():
        try:
            hotels = await asyncio.to_thread(_fetch_hotels)
            _all_hotels[:] = hotels
            _render_hotels(_apply_local(hotels))
            logger.info("hotels_page: список домов подгружен, count=%s", len(hotels))
        except Exception as e:
            logger.error("hotels_page: не удалось загрузить список домов: %s", e)
        finally:
            loader.hide()

    asyncio.create_task(_initial_load())
    return page
