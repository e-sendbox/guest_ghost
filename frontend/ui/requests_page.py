"""Вкладка Guest Ghost (шаг 1: заявки; шаг 3: попап «Добавить заявку»; шаг 10: фильтры из отчётов).

3 фрейма по ширине окна:
  - верхний: полоска с заголовком «Заявки на заселение» (+ [фильтр] слева, шаг 10)
  - основной: список заявок (карточки)
  - нижний: панель кнопок (кнопка «Добавить заявку» открывает попап)
"""

import asyncio
import logging
from datetime import date

from nicegui import app, ui
from nicegui.element import Element

from frontend.api.client import ApiClient
from frontend.ui.widgets import ChipGroup, GhostLoader, ResultPopup, date_picker, number_spinner, to_display, to_iso

logger = logging.getLogger(__name__)

FILTER_TITLES = {
    "waiting": "ждали заселения в период с {date}",
    "chosen": "подобрано жилье в период с {date}",
    "reserved": "заселены в период с {date}",
    "no_dates": "нет жилья с искомой датой в период с {date}",
    "no_homes": "нет подходящего жилья в период с {date}",
    "house_dynamics": "динамика заселения дома {home} в период с {date}",
}


def _filter_title(filters: dict) -> str | None:
    """Название фильтра для плашки (шаг 10); None — фильтра нет."""
    f = filters.get("filter")
    if not f:
        return None
    d = to_display(filters.get("period_start", "")[:10])
    home = filters.get("home_name") or filters.get("home_id") or ""
    tpl = FILTER_TITLES.get(f)
    if not tpl:
        return None
    return tpl.format(date=d, home=home)


def build_requests_page(config: dict, filters: dict | None = None):
    filters = filters or {}
    api = ApiClient(config.get("app", {}).get("api_url", "http://localhost:8080/api"))

    with ui.column().classes("w-full h-full").style("gap: 0") as page:
        with ui.element("div").classes("w-full page-header"):
            with ui.row().classes("items-center").style("gap: 8px"):
                ui.label("Заявки на заселение").classes("text-h6")
                ftitle = _filter_title(filters)
                if ftitle:
                    ui.label(f"[{ftitle}]").classes("page-filter-tag")
                with ui.row().classes("lfilter-groups"):
                    with ui.row().classes("local-filters").style("gap: 6px"):
                        expand_all_btn = ui.button(icon="unfold_more").props("flat round dense").classes("lfilter-btn").tooltip("Развернуть все")
                        collapse_all_btn = ui.button(icon="unfold_less").props("flat round dense").classes("lfilter-btn").tooltip("Свернуть все")
                    with ui.row().classes("local-filters").style("gap: 6px"):
                        status_btn = ui.button(icon="flag").props("flat round dense").classes("lfilter-btn oval").tooltip("Фильтр: статус заявки")
                        with status_btn:
                            with ui.menu().classes("lfilter-menu").props("no-focus") as status_menu:
                                pass
                        id_btn = ui.button(icon="tag").props("flat round dense").classes("lfilter-btn oval").tooltip("Фильтр: номер заявки")
                        with id_btn:
                            with ui.menu().classes("lfilter-menu").props("no-focus") as id_menu:
                                pass
                        sort_btn = ui.button().props("flat round dense").classes("lfilter-btn oval").tooltip("Сортировка: по соответствию выбранного дома")
                        with sort_btn:
                            sort_icon = ui.icon("fact_check").classes("sort-main-icon")
                            sort_arrow = ui.icon("arrow_upward").classes("sort-arrow")
                        reset_btn = ui.button(icon="filter_alt_off").props("flat round dense").classes("lfilter-btn").tooltip("Сбросить фильтры")
        with ui.column().classes("w-full flex-1 page-body requests-list").style("gap: 8px") as list_area:
            cards_container = ui.column().classes("w-full").style("gap: 8px")
            empty_label = ui.label("Список заявок пуст.").classes("page-empty")
            loader = GhostLoader(text="Собираем приведений...")
        with ui.element("div").classes("w-full page-footer"):
            with ui.row().classes("w-full items-center gap-2"):
                add_btn = ui.button("Добавить заявку").props("no-caps flat").classes("page-btn")
                search_btn = ui.button("Подобрать жилье").props("no-caps flat").classes("page-btn")
                book_btn = ui.button("Заселить в подобранное").props("no-caps flat").classes("page-btn")

    with ui.dialog() as dialog, ui.card().classes("form-popup"):
        with ui.column().classes("w-full h-full").style("gap: 0"):
            with ui.element("div").classes("w-full popup-head"):
                ui.label("Добавить заявку").classes("text-h6")

            with ui.column().classes("w-full flex-1 popup-body").style("gap: 12px"):
                name_input = ui.input("Имя приведения (обязательно)").classes("w-full")

                with ui.row().classes("w-full items-center gap-2 panel-header"):
                    ui.label("Приведение тревожно на").classes("panel-label")
                    anxiety_spinner = number_spinner(value=0.5, min_value=0, max_value=1, step=0.1, precision=1).classes("w-20")
                    ui.label("должно заселиться до").classes("panel-label")
                    deadline_picker = date_picker(iso_value=date.today().isoformat(), classes="w-36")
                    ui.label("включительно").classes("panel-label")

                with ui.column().classes("w-full panel-frame req-frame").style("gap: 8px"):
                    with ui.row().classes("w-full items-center gap-2 panel-header"):
                        ui.label("Добавить требование приведения").classes("panel-label")
                        chip_group = ChipGroup()
                    with ui.column().classes("w-full panel-box").style("gap: 6px"):
                        chip_group.build_area()

                preferences_input = ui.textarea("Особые пожелания").classes("w-full tall-field").props("rows=3")

            error_label = ui.label("").classes("popup-error")
            with ui.element("div").classes("w-full popup-footer"):
                save_btn = ui.button("Сохранить").props("no-caps flat").classes("page-btn save-btn")

    async def _save():
        error_label.text = ""
        fields = [
            (name_input, "Имя приведения"),
            (anxiety_spinner, "Тревожность"),
            (deadline_picker, "Дата заселения"),
        ]
        has_empty = False
        for field, _ in fields:
            field.props(remove="error")
        for field, _ in fields:
            if field.value is None or str(field.value).strip() == "":
                field.props(add="error")
                has_empty = True
        if not chip_group.items:
            chip_group.set_error(True)
            has_empty = True
        else:
            chip_group.set_error(False)
        if has_empty:
            return
        data = {
            "name": name_input.value,
            "anxiety": float(anxiety_spinner.value),
            "requirements": chip_group.items,
            "preferences": preferences_input.value,
            "deadline_date": to_iso(deadline_picker.value),
        }
        try:
            result = await asyncio.to_thread(api.create_request, data)
        except ValueError as e:
            error_label.text = str(e)
            return
        await _enrich_and_notify(result["id"], data)

    async def _enrich_and_notify(card_id: int, data: dict):
        """Обогащение карточки заявки после сохранения метаданных, до закрытия формы."""
        saving_dialog.open()
        logger.info("requests_page: старт обогащения, card_id=%s", card_id)
        status = await asyncio.to_thread(api.enrich, "ghost", card_id, data)
        saving_dialog.close()
        logger.info("requests_page: обогащение завершено, status=%s", status)
        dialog.close()
        _reset_form()
        if status == "success":
            success_popup.text = "Данные карточки успешно сохранены"
            success_popup.open()
        else:
            success_popup.text = "Заявку не удалось обогатить, LLM не отвечает. Заявка недоступна для обработки, но сохранена в базу данных. Передайте администратору id карточки заявки для восстановления карточки."
            success_popup.open()
        await asyncio.to_thread(_refresh_list)

    # попап-спиннер «осмысление данных» — компактный
    with ui.dialog().props("persistent") as saving_dialog, ui.card().classes("result-popup"):
        with ui.column().classes("w-full items-center").style("gap: 12px"):
            ui.spinner("dots", size="32px").classes("text-primary")
            ui.label("Осмысление введённых данных...").classes("result-popup-text")

    # попап-спиннер «подбор жилья» — компактный
    with ui.dialog().props("persistent") as searching_dialog, ui.card().classes("result-popup"):
        with ui.column().classes("w-full items-center").style("gap: 12px"):
            ui.spinner("dots", size="32px").classes("text-primary")
            ui.label("Подбор жилья...").classes("result-popup-text")

    # попап «Лист бронирования» (шаг 7)
    booking_dialog = ui.dialog()
    with booking_dialog, ui.card().classes("form-popup"):
        with ui.column().classes("w-full h-full").style("gap: 0"):
            with ui.element("div").classes("w-full popup-head"):
                ui.label("Лист бронирования").classes("text-h6")

            booking_body = ui.column().classes("w-full flex-1 popup-body").style("gap: 12px")

            with ui.element("div").classes("w-full popup-footer"):
                with ui.row().classes("w-full items-center").style("gap: 8px"):
                    book_save_btn = ui.button("Заселить").props("no-caps flat").classes("page-btn save-btn flex-1")

    success_popup = ResultPopup()

    def _reset_form():
        name_input.value = ""
        anxiety_spinner.value = 0.5
        deadline_picker.value = date.today().strftime("%d/%m/%Y")
        chip_group.clear()
        preferences_input.value = ""

    def _load_requirements():
        try:
            options = api.get_requirements()
            chip_group.autocomplete.set_options(options)
            logger.info("requests_page: каталог требований подгружен, count=%s", len(options))
        except Exception as e:
            logger.error("requests_page: не удалось подгрузить каталог требований: %s", e)

    def _status_line(req: dict) -> tuple[str, str]:
        """Возвращает (текст, css-класс цвета) для строки статуса."""
        if req.get("status") == "reserved":
            return "заселен", "status-green"
        if req.get("status") == "chosen":
            return "подобран дом", "status-orange"
        return "не заселен", "status-red"

    def _variants_line(req: dict) -> tuple[str, bool]:
        """(текст, is_error) для лейбла «Найдено домов:».

        N = количество ВСЕХ домов в selection_hotel (прошедших фильтр дат,
        независимо от match_percent). При N=0 и непустом comment —
        «0 - comment» красным (случай «нет подходящих дат»); при пустом
        comment — «не подобрано».
        """
        selection = req.get("selection_hotel") or "[]"
        try:
            import json as _json
            items = _json.loads(selection) if isinstance(selection, str) else selection
        except Exception:
            items = []
        comment = (req.get("comment") or "").strip()
        n = len(items)
        if n > 0:
            return str(n), False
        if comment:
            return f"0 - {comment}", True
        return "не подобрано", False

    def _best_line(req: dict) -> str:
        """Значение для лейбла «Соответствие:» — «X%» или «не определен»."""
        match = req.get("match_percent")
        if match is None or match == "":
            return "не определен"
        return f"{match}%"

    _expanded: set[int] = set()
    _card_elems: dict[int, Element] = {}
    _all_requests: list[dict] = []

    _local = app.storage.user.get("gg_filters") or {}
    _local_statuses: set[str] = set(_local.get("statuses") or [])
    _local_ids: set[int] = set(_local.get("ids") or [])
    _local_sort: str | None = _local.get("sort")

    def _save_local():
        app.storage.user["gg_filters"] = {
            "statuses": sorted(_local_statuses),
            "ids": sorted(_local_ids),
            "sort": _local_sort,
        }

    def _apply_local(requests: list[dict]) -> list[dict]:
        result = requests
        if _local_statuses:
            result = [r for r in result if r.get("status") in _local_statuses]
        if _local_ids:
            result = [r for r in result if r["id"] in _local_ids]
        if _local_sort == "desc":
            result = sorted(result, key=lambda r: (r.get("match_percent") is None, -(r.get("match_percent") or 0), r["id"]))
        elif _local_sort == "asc":
            result = sorted(result, key=lambda r: (r.get("match_percent") is not None, r.get("match_percent") or 0, r["id"]))
        return result

    def _render_requests(requests: list[dict]):
        cards_container.clear()
        _card_elems.clear()
        empty_label.set_visibility(not requests)
        if not requests:
            return
        with cards_container:
            for req in requests:
                with ui.column().classes("w-full request-card").style("gap: 0") as request_card:
                    _card_elems[req["id"]] = request_card
                    has_houses = bool(_sel_items(req))
                    # лицевая плашка: раскрывашка+id | имя | данные
                    with ui.row().classes("w-full request-card-face").style("gap: 0") as face:
                        # ячейка: раскрывашка + id (в одну строку)
                        with ui.row().classes("request-id-cell items-center").style("gap: 2px"):
                            if has_houses:
                                expand_icon = ui.icon("chevron_right").classes("request-expand-arrow")
                            else:
                                expand_icon = ui.icon("chevron_right").classes("request-expand-arrow disabled")
                            ui.label(str(req["id"])).classes("request-id")
                        # ячейка: имя
                        with ui.element("div").classes("request-name-cell"):
                            ui.label(str(req["name"])).classes("request-name")
                        # ячейка: информация и статусы (одна строка с переносом, разделители «•»)
                        status_text, status_cls = _status_line(req)
                        with ui.row().classes("request-info-cell items-center request-info-row").style("gap: 8px"):
                            ui.label(f"Тревожность приведения: ").classes("request-meta")
                            ui.label(str(req['anxiety'])).classes("request-meta request-value")
                            ui.label("•").classes("request-sep")
                            ui.label("Дедлайн приведения: ").classes("request-meta")
                            ui.label(to_display(req.get('deadline_date'))).classes("request-meta request-value")
                            ui.label("•").classes("request-sep")
                            ui.label("Статус заселения: ").classes("request-meta")
                            ui.label(status_text).classes(f"request-meta request-value {status_cls}")
                            ui.label("•").classes("request-sep")
                            ui.label("Найдено домов: ").classes("request-meta")
                            vi, vi_error = _variants_line(req)
                            ui.label(vi).classes(f"request-meta request-value{' status-red' if vi_error else ''}")
                            ui.label("•").classes("request-sep")
                            ui.label("Выбран: ").classes("request-meta")
                            ui.label(req.get("hotel_name") or "нет").classes("request-meta request-value")
                            ui.label("•").classes("request-sep")
                            ui.label("Соответствие: ").classes("request-meta")
                            bi = _best_line(req)
                            match = req.get("match_percent")
                            zero_cls = " status-red" if match is not None and str(match) != "" and int(match) == 0 else ""
                            ui.label(bi).classes(f"request-meta request-value{zero_cls}")
                    # дочерний фрейм (развернутый вид) — только если есть дома
                    detail = None
                    if has_houses:
                        detail = ui.element("div").classes("w-full request-card-detail")
                        detail.set_visibility(False)
                        if req["id"] in _expanded:
                            detail.set_visibility(True)
                            expand_icon.set_name("arrow_drop_down")
                        with detail:
                            with ui.column().classes("w-full items-center").style("gap: 8px"):
                                # шапка: теги приведения + кругляш «никуда не заселять»
                                with ui.column().classes("w-full").style("gap: 6px"):
                                    tags = req.get("tags") or "[]"
                                    try:
                                        import json as _json
                                        tags_list = _json.loads(tags) if isinstance(tags, str) else tags
                                        tags_text = ", ".join(tags_list) if tags_list else "нет"
                                    except Exception:
                                        tags_text = "нет"
                                    with ui.row().classes("items-center").style("gap: 4px"):
                                        ui.label("Требования приведения: ").classes("selection-props selection-props-bold")
                                        ui.label(tags_text).classes("selection-props")
                                    if req.get("status") != "reserved":
                                        with ui.row().classes("items-center").style("gap: 6px"):
                                            nohome_chip = ui.chip(icon="block", text="").classes("select-chip nohome")
                                            ui.label("никуда не заселять: исключить заявку из подобранных, обнулить выборку домов, вернуть в статус free (попадет в следующую подборку жилья)").classes("select-label nohome")
                                            nohome_chip.on_click(lambda _rid=req["id"]: asyncio.create_task(_reset_request(_rid)))
                                items = _sel_items(req)
                                for item in items:
                                    is_best = item.get("home_id") == req.get("home_id")
                                    with ui.row().classes("w-full selection-item" + (" best" if is_best else "")).style("gap: 0"):
                                        # колонка 1: название (серым) + чип выбора
                                        with ui.column().classes("selection-name-cell").style("gap: 6px"):
                                            ui.link(str(item.get("name", "дом")), f"/homedirect?filter=from_request&request_id={req['id']}", new_tab=True).classes("request-hotel-link")
                                            is_selected = item.get("home_id") == req.get("home_id")
                                            match = item.get("match_percent") or 0
                                            with ui.row().classes("items-center").style("gap: 6px"):
                                                if req.get("status") == "reserved":
                                                    ui.chip(text=f"{match}%").classes("select-chip" + ("" if is_selected else " unselected"))
                                                else:
                                                    if is_selected:
                                                        select_chip = ui.chip(text=f"{match}%").classes("select-chip")
                                                        select_label = ui.label("выбран для заселения").classes("select-label")
                                                    else:
                                                        select_chip = ui.chip(text=f"{match}%").classes("select-chip unselected")
                                                        select_label = ui.label("выбрать для заселения").classes("select-label")
                                                    select_chip.on_click(lambda _rid=req["id"], _hid=item.get("home_id"): asyncio.create_task(_select_home(_rid, _hid)))
                                                    select_label.on("click", lambda _rid=req["id"], _hid=item.get("home_id"): asyncio.create_task(_select_home(_rid, _hid)))
                                        # колонка 2: 3 строки
                                        with ui.column().classes("selection-info-cell").style("gap: 4px"):
                                            with ui.row().classes("items-center gap-2").style("gap: 8px"):
                                                ui.label("Ближайшая дата заселения: ").classes("request-meta selection-props-bold")
                                                ui.label(to_display(item.get('free_date'))).classes("request-meta")
                                            tags = item.get("tags") or "[]"
                                            try:
                                                import json as _json
                                                tags_list = _json.loads(tags) if isinstance(tags, str) else tags
                                                tags_text = ", ".join(tags_list) if tags_list else "нет"
                                            except Exception:
                                                tags_text = "нет"
                                            with ui.row().classes("items-center").style("gap: 4px"):
                                                ui.label("Свойства дома: ").classes("selection-props selection-props-bold")
                                                ui.label(tags_text).classes("selection-props")
                                            with ui.row().classes("items-center").style("gap: 4px"):
                                                ui.label("Резолюция о соответствии: ").classes("selection-comment selection-props-bold")
                                                ui.label(item.get('comment', '')).classes("selection-comment")

                    def _toggle(_icon=expand_icon, _detail=detail, _req_id=req["id"]):
                        if _detail.visible:
                            _icon.set_name("chevron_right")
                            _detail.set_visibility(False)
                            _expanded.discard(_req_id)
                        else:
                            _icon.set_name("arrow_drop_down")
                            _detail.set_visibility(True)
                            _expanded.add(_req_id)

                    if has_houses:
                        face.on("click", _toggle)

    def _sel_items(req: dict):
        import json as _json
        selection = req.get("selection_hotel") or "[]"
        try:
            return _json.loads(selection) if isinstance(selection, str) else selection
        except Exception:
            return []

    def _fetch_requests() -> list[dict]:
        return api.get_requests(
            filter=filters.get("filter"),
            date=filters.get("date"),
            period_start=filters.get("period_start"),
            home_id=int(filters["home_id"]) if filters.get("home_id") else None,
        )

    def _refresh_list():
        try:
            requests = _fetch_requests()
            _all_requests[:] = requests
            _render_requests(_apply_local(requests))
        except Exception as e:
            logger.error("requests_page: не удалось загрузить список заявок: %s", e)

    async def _run_search():
        search_btn.disable()
        searching_dialog.open()
        try:
            result = await asyncio.to_thread(api.run_search)
            logger.info("requests_page: подбор завершён, result=%s", result)
            if result.get("no_requests"):
                logger.info("requests_page: открываю попап «не найдено»")
                no_requests_popup.open()
        except Exception as e:
            logger.error("requests_page: ошибка подбора: %s", e)
        finally:
            searching_dialog.close()
            search_btn.enable()
        await asyncio.to_thread(_refresh_list)

    async def _capture_scroll() -> int:
        """scrollTop контейнера списка до пересборки (0 — если не удалось)."""
        try:
            response = await ui.context.client.run_javascript(
                "document.querySelector('.requests-list') ? document.querySelector('.requests-list').scrollTop : 0"
            )
            return int(response) if response is not None else 0
        except Exception:
            return 0

    def _restore_scroll(pos: int):
        """Вернуть scrollTop контейнера списка после пересборки."""
        if pos:
            ui.run_javascript(
                f"document.querySelector('.requests-list').scrollTop = {pos}"
            )

    async def _select_home(request_id: int, home_id: int):
        try:
            await asyncio.to_thread(api.select_home, request_id, home_id)
            logger.info("requests_page: перевыбор дома, request_id=%s, home_id=%s", request_id, home_id)
        except Exception as e:
            logger.error("requests_page: ошибка перевыбора дома: %s", e)
        pos = await _capture_scroll()
        await asyncio.to_thread(_refresh_list)
        _restore_scroll(pos)
        _focus_card(request_id)

    async def _reset_request(request_id: int):
        try:
            await asyncio.to_thread(api.reset_request, request_id)
            logger.info("requests_page: сброс заявки, request_id=%s", request_id)
        except Exception as e:
            logger.error("requests_page: ошибка сброса заявки: %s", e)
        pos = await _capture_scroll()
        await asyncio.to_thread(_refresh_list)
        _restore_scroll(pos)
        _focus_card(request_id)

    def _focus_card(request_id: int):
        """Вернуть прокрутку на карточку заявки после пересборки списка."""
        card = _card_elems.get(request_id)
        if card is not None:
            ui.run_javascript(f"document.getElementById('{card.id}').scrollIntoView({{block: 'nearest'}})")

    # ---------- Шаг 7: Лист бронирования ----------

    booking_state: dict[int, int] = {}      # request_id -> room_id (выбранные номера)
    room_pickers: dict[int, dict] = {}      # request_id -> {field, menu}
    included_requests: list[int] = []       # request_id, оставшиеся в листе
    _booking_raw_candidates: list[dict] = []
    _booking_rooms: dict[int, list[dict]] = {}

    def _room_label(room: dict) -> str:
        return f"Место {room['id']} • {to_display(room['free_date'])}"

    def _render_booking_form(candidates: list[dict]):
        """Построить содержимое формы «Лист бронирования» по кандидатам."""
        booking_state.clear()
        room_pickers.clear()
        included_requests.clear()
        booking_body.clear()

        with booking_body:
            for group in candidates:
                with ui.column().classes("w-full").style("gap: 8px"):
                    ui.label(group["name"]).classes("booking-hotel-name")
                    with ui.column().classes("w-full booking-ghosts").style("gap: 8px"):
                        for req in group["requests"]:
                            req_id = req["id"]
                            included_requests.append(req_id)
                            with ui.row().classes("w-full booking-face items-center").style("gap: 0"):
                                # колонка 1: имя приведения
                                with ui.element("div").classes("booking-name-cell"):
                                    ui.label(req["name"]).classes("booking-ghost-name")
                                # колонка 2: данные (одна строка, перенос по лейблам)
                                with ui.element("div").classes("booking-info-cell"):
                                    with ui.row().classes("items-center booking-info-row").style("gap: 8px"):
                                        ui.label(f"Тревожность: {req['anxiety']}").classes("request-meta")
                                        ui.label("•").classes("request-sep")
                                        ui.label(f"Дедлайн приведения: {to_display(req['deadline_date'])}").classes("request-meta")
                                        ui.label("•").classes("request-sep")
                                        match = req.get("match_percent")
                                        ui.label(f"Соответствие дома: {match}%" if match is not None else "Соответствие дома: не определен").classes("request-meta")
                                # колонка 3: кнопки (выпадашка + кругляш)
                                with ui.element("div").classes("booking-actions-cell"):
                                    with ui.row().classes("items-center").style("gap: 8px"):
                                        room_pickers[req_id] = _make_room_picker(req_id)
                                        nohome_chip = ui.chip(icon="block", text="").classes("select-chip nohome")
                                        with nohome_chip:
                                            ui.tooltip("Исключить из листа бронирования (вернуть в заявки)")
                                        nohome_chip.on_click(lambda _rid=req_id: _exclude_from_booking(_rid))

        _refresh_room_pickers()

    def _make_room_picker(req_id: int) -> dict:
        """Поле «Выбрать номер» с выпадающим меню (в стиле AutocompleteInput)."""
        field = ui.input(label="Выбрать место").classes("booking-room-select").props("outlined dense readonly")
        with field:
            with ui.menu().classes("auto-menu booking-room-menu").props("auto-close no-focus") as menu:
                pass
            ui.icon("arrow_drop_down").classes("auto-arrow")

        def _open_menu():
            menu.clear()
            taken: set[int] = set(booking_state.values())
            room_list = _booking_rooms.get(req_id, [])
            available = [r for r in room_list if r["id"] not in taken]
            with menu:
                if req_id in booking_state:
                    ui.item("Очистить выбор", on_click=_clear_selection).props("separator")
                if available:
                    for room in available:
                        ui.item(_room_label(room), on_click=lambda r=room: _pick(r))
                else:
                    ui.item("Нет свободных мест").props("disabled")
            menu.open()

        def _clear_selection():
            booking_state.pop(req_id, None)
            field.value = ""
            menu.close()
            _refresh_room_pickers()

        def _pick(room: dict):
            booking_state[req_id] = room["id"]
            field.value = _room_label(room)
            field.props(remove="error")
            menu.close()
            _refresh_room_pickers()

        field.on("click", _open_menu)
        return {"field": field, "menu": menu}

    def _refresh_room_pickers():
        """Обновить все поля: показать выбранный номер, снять занятые, сбросить конфликты.

        Антиконфликт на уровне UI: номер, выбранный другой заявкой, не предлагается
        в меню (см. _open_menu); если заявка выбрала номер, занятый другой
        заявкой (не может случиться через UI), — значение сбрасывается.
        """
        for req_id, picker in room_pickers.items():
            field = picker["field"]
            room_id = booking_state.get(req_id)
            if room_id is None:
                field.value = ""
                continue
            room_list = _booking_rooms.get(req_id, [])
            room = next((r for r in room_list if r["id"] == room_id), None)
            if room is None:
                booking_state.pop(req_id, None)
                field.value = ""
            else:
                field.value = _room_label(room)

    def _on_room_picked(req_id: int, room_id: int):
        booking_state[req_id] = room_id
        _refresh_room_pickers()

    def _exclude_from_booking(req_id: int):
        """Крестик: убрать заявку из листа (БД не трогаем)."""
        if req_id in included_requests:
            included_requests.remove(req_id)
        booking_state.pop(req_id, None)
        room_pickers.pop(req_id, None)
        _render_booking_form_with_state()

    def _render_booking_form_with_state():
        """Перестроить форму по сохранённым кандидатам (после исключения заявки).

        Сохраняем выборы мест остальных заявок и восстанавливаем их после
        перерисовки (иначе _render_booking_form сбрасывает booking_state).
        """
        filtered = []
        for group in list(_booking_raw_candidates):
            group_req = [r for r in group["requests"] if r["id"] in included_requests]
            if group_req:
                filtered.append({"home_id": group["home_id"], "name": group["name"], "requests": group_req})
        if filtered:
            saved_state = dict(booking_state)
            _render_booking_form(filtered)
            booking_state.update(saved_state)
            _refresh_room_pickers()

    async def _open_booking():
        """Кнопка «Заселить в подобранное»."""
        nonlocal _booking_raw_candidates, _booking_rooms
        try:
            candidates = await asyncio.to_thread(api.get_booking_candidates)
        except Exception as e:
            logger.error("requests_page: не удалось загрузить кандидатов: %s", e)
            return
        if not candidates:
            no_booking_popup.open()
            return
        _booking_raw_candidates = candidates
        _booking_rooms = {}
        for group in candidates:
            for r in group["requests"]:
                _booking_rooms[r["id"]] = r["rooms"]
        _render_booking_form(candidates)
        booking_dialog.open()

    async def _confirm_booking():
        """Кнопка «Заселить»: валидация → POST /booking → попап успеха."""
        missing = [rid for rid in included_requests if rid not in booking_state]
        for picker in room_pickers.values():
            picker["field"].props(remove="error")
        for rid in missing:
            picker = room_pickers.get(rid)
            if picker:
                picker["field"].props(add="error")
        if missing:
            return
        bookings = [{"request_id": rid, "room_id": booking_state[rid]} for rid in included_requests]
        try:
            result = await asyncio.to_thread(api.book, bookings)
            logger.info("requests_page: бронь выполнена, result=%s", result)
        except Exception as e:
            logger.error("requests_page: ошибка брони: %s", e)
            error_popup.text = f"Не удалось заселить: {e}"
            error_popup.open()
            return
        booking_dialog.close()
        booked_popup.open()
        await asyncio.to_thread(_refresh_list)

    no_booking_popup = ResultPopup(text="Заселять некого, сначала подберите жилье")
    booked_popup = ResultPopup(text="Приведения заселены")
    error_popup = ResultPopup()

    book_btn.on("click", _open_booking)
    book_save_btn.on("click", _confirm_booking)

    def _open_dialog():
        dialog.open()
        chip_group.refresh()
        asyncio.create_task(asyncio.to_thread(_load_requirements))

    # ---------- Шаг 11: локальные фильтры ----------

    def _rebuild_local_menus():
        status_menu.clear()
        id_menu.clear()
        base = _all_requests
        if _local_ids:
            base = [r for r in base if r["id"] in _local_ids]
        statuses = [st for st in STATUS_ORDER if st in {r.get("status") for r in base}]
        with status_menu:
            for st in statuses:
                with ui.item().props("dense"):
                    ui.checkbox(STATUS_RU.get(st, st), value=st in _local_statuses).on_value_change(
                        lambda e, _st=st: _toggle_status(_st, e.value)
                    )
        base2 = _all_requests
        if _local_statuses:
            base2 = [r for r in base2 if r.get("status") in _local_statuses]
        ids = sorted(r["id"] for r in base2)
        with id_menu:
            for rid in ids:
                with ui.item().props("dense"):
                    req = next((r for r in base2 if r["id"] == rid), None)
                    label = f"{rid} • {req['name']}" if req else str(rid)
                    ui.checkbox(label, value=rid in _local_ids).on_value_change(
                        lambda e, _rid=rid: _toggle_id(_rid, e.value)
                    )

    def _toggle_status(status: str, checked: bool):
        if checked:
            _local_statuses.add(status)
        else:
            _local_statuses.discard(status)
        _save_local()
        _update_filter_btns()
        _render_requests(_apply_local(_all_requests))
        _rebuild_local_menus()

    STATUS_RU = {"free": "не заселен", "chosen": "подобран дом", "reserved": "заселен"}
    STATUS_ORDER = ["free", "chosen", "reserved"]

    def _toggle_id(rid: int, checked: bool):
        if checked:
            _local_ids.add(rid)
        else:
            _local_ids.discard(rid)
        _save_local()
        _update_filter_btns()
        _render_requests(_apply_local(_all_requests))
        _rebuild_local_menus()

    def _update_filter_btns():
        status_btn.classes(remove="active")
        id_btn.classes(remove="active")
        sort_btn.classes(remove="active")
        if _local_statuses:
            status_btn.classes(add="active")
        if _local_ids:
            id_btn.classes(add="active")
        if _local_sort:
            sort_btn.classes(add="active")

    def _update_sort_icon():
        if _local_sort == "desc":
            sort_arrow.set_name("arrow_upward")
            sort_arrow.set_visibility(True)
        elif _local_sort == "asc":
            sort_arrow.set_name("arrow_downward")
            sort_arrow.set_visibility(True)
        else:
            sort_arrow.set_visibility(False)

    def _cycle_sort():
        nonlocal _local_sort
        if _local_sort is None:
            _local_sort = "desc"
        elif _local_sort == "desc":
            _local_sort = "asc"
        else:
            _local_sort = None
        _save_local()
        _update_filter_btns()
        _update_sort_icon()
        _render_requests(_apply_local(_all_requests))

    def _expand_all():
        visible = _apply_local(_all_requests)
        _expanded.clear()
        for r in visible:
            if _sel_items(r):
                _expanded.add(r["id"])
        _render_requests(visible)

    def _collapse_all():
        visible = _apply_local(_all_requests)
        _expanded.clear()
        _render_requests(visible)

    def _reset_local():
        nonlocal _local_sort
        _local_statuses.clear()
        _local_ids.clear()
        _local_sort = None
        _save_local()
        _update_filter_btns()
        _update_sort_icon()
        _render_requests(_apply_local(_all_requests))
        _rebuild_local_menus()

    def _open_status_menu():
        _rebuild_local_menus()
        status_menu.open()

    def _open_id_menu():
        _rebuild_local_menus()
        id_menu.open()

    expand_all_btn.on("click", _expand_all)
    collapse_all_btn.on("click", _collapse_all)
    sort_btn.on("click", _cycle_sort)
    reset_btn.on("click", _reset_local)
    status_btn.on("click", _open_status_menu)
    id_btn.on("click", _open_id_menu)
    _update_filter_btns()
    _update_sort_icon()

    no_requests_popup = ResultPopup(text="Жилье для всех уже подобрано")

    add_btn.on("click", _open_dialog)
    save_btn.on("click", _save)
    search_btn.on("click", _run_search)

    # первичная загрузка списка при открытии страницы
    async def _initial_load():
        try:
            requests = await asyncio.to_thread(_fetch_requests)
            _all_requests[:] = requests
            _render_requests(_apply_local(requests))
        except Exception as e:
            logger.error("requests_page: не удалось загрузить список заявок: %s", e)
        finally:
            loader.hide()

    asyncio.create_task(_initial_load())
    chip_group.refresh()
    return page
