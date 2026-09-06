"""Каркас приложения (шаг 1: табы; шаг 10: build_chrome — общий каркас для отдельных адресов вкладок).

Табы как папки (горизонтальные, в одну строку), активная соединена с контентом:
  Guest Ghost — заявки на заселение (иконка отчёта после названия)
  HomeDirect  — справочник домов
  DevINFO     — пустая

Шаг 10: у каждой вкладки свой адрес (/guest_ghost, /homedirect, /devinfo);
build_chrome рисует общий каркас (табы-ссылки, попап «Отчеты»), контент
страницы рендерится отдельно в main.py.
"""

import asyncio
import hashlib
import logging
from pathlib import Path

from nicegui import ui

from frontend.api.client import ApiClient
from frontend.ui.widgets import number_spinner, to_display

logger = logging.getLogger(__name__)

CSS_PATH = Path(__file__).parent.parent / "static" / "style.css"

TAB_URLS = {
    "guest_ghost": "/guest_ghost",
    "homedirect": "/homedirect",
    "devinfo": "/devinfo",
}


def _css_version() -> str:
    try:
        return hashlib.md5(CSS_PATH.read_bytes()).hexdigest()[:10]
    except OSError:
        return "0"


def build_chrome(config: dict, active_tab: str, content_builder=None):
    ui.query("body").classes("m-0")
    ui.add_head_html(f'<link rel="stylesheet" href="/static/style.css?v={_css_version()}">')

    api = ApiClient(config.get("app", {}).get("api_url", "http://localhost:8080/api"))

    with ui.column().classes("w-full h-screen root-col").style("gap: 0"):
        with ui.tabs().classes("top-tabs") as tabs:
            with ui.tab(name="guest_ghost", label="").on("click", lambda: ui.navigate.to(TAB_URLS["guest_ghost"])):
                with ui.row().classes("items-center gap-1"):
                    ui.label("Guest Ghost")
                    report_btn = ui.button(icon="description").props("flat round dense").classes("bell-btn")

            # попап «Отчеты» (шаг 8)
            with ui.dialog() as report_dialog, ui.card().classes("form-popup"):
                with ui.column().classes("w-full h-full").style("gap: 0"):
                    with ui.element("div").classes("w-full popup-head"):
                        ui.label("Отчеты").classes("text-h6")

                    with ui.column().classes("w-full flex-1 popup-body").style("gap: 12px"):
                        # первая строка: «Сформировать отчет <выпадашка>: последние <поле> дней. [кругляш]»
                        with ui.row().classes("w-full items-center gap-2").style("gap: 8px"):
                            ui.label("Сформировать отчет").classes("panel-label")
                            report_mode_field = ui.input(label="Выбрать отчет").classes("report-mode-select").props("outlined dense readonly")
                            with report_mode_field:
                                with ui.menu().classes("auto-menu report-mode-menu").props("auto-close no-focus") as report_mode_menu:
                                    pass
                                ui.icon("arrow_drop_down").classes("auto-arrow")
                            ui.label(": последние").classes("panel-label")
                            days_spinner = number_spinner(value=1, min_value=1, max_value=365, step=1, precision=0).classes("w-20")
                            ui.label("дней.").classes("panel-label")
                            report_go_btn = ui.chip(icon="arrow_forward", text="").classes("select-chip report-go")

                        # плашка отчёта: со второй строки до конца формы (flex-1)
                        with ui.column().classes("w-full flex-1 report-panel").style("gap: 8px"):
                            report_area = ui.column().classes("w-full flex-1 report-area").style("gap: 4px")
                            report_empty = ui.icon("insert_chart").classes("panel-empty")

            report_btn.on("click", report_dialog.open)
            report_btn.on("click", None, js_handler="(e) => { e.stopPropagation(); }")
            with ui.tab(name="homedirect", label="").on("click", lambda: ui.navigate.to(TAB_URLS["homedirect"])):
                ui.label("HomeDirect")
            with ui.tab(name="devinfo", label="").on("click", lambda: ui.navigate.to(TAB_URLS["devinfo"])):
                ui.label("DevINFO")

        tabs.value = active_tab

        # контент страницы — ВНУТРИ root-col (шаг 10): иначе выпадает из контейнера
        # и обрезается overflow'ом body; flex-1 — занимает оставшееся место после табов
        if content_builder:
            with ui.element("div").classes("w-full flex-1 content-col"):
                content_builder()

    # ---------- Шаг 8: логика отчёта ----------

    report_mode: str | None = None

    def _open_report_menu():
        report_mode_menu.clear()
        with report_mode_menu:
            ui.item("по заявкам незаселенных на начало периода", on_click=lambda: _pick_report_mode("requests"))
            ui.item("по домам, выбранным за период", on_click=lambda: _pick_report_mode("houses"))
        report_mode_menu.open()

    def _pick_report_mode(mode: str):
        nonlocal report_mode
        report_mode = mode
        report_mode_field.value = "по заявкам незаселенных на начало периода" if mode == "requests" else "по домам, выбранным за период"
        report_mode_field.props(remove="error")
        report_go_btn.enable()
        report_mode_menu.close()

    report_mode_field.on("click", _open_report_menu)

    def _report_link(path: str, text: str, cls: str = "report-cell") -> ui.link:
        """Ссылка-цифра отчёта (шаг 10): открывает страницу с фильтром в новой вкладке."""
        return ui.link(text, path, new_tab=True).classes(cls + " report-link")

    def _render_report_table(data: dict):
        """Таблица отчёта в нашем стиле (кастомная, рядами)."""
        report_area.clear()
        report_empty.set_visibility(False)
        rows = data.get("rows", [])
        period_start = data.get("period_start", "")
        with report_area:
            if data["mode"] == "requests":
                # шапка: уровень 1 — группы, уровень 2 — колонки групп (grid 6 колонок)
                with ui.element("div").classes("w-full report-head report-grid").style("gap: 8px"):
                    ui.label("Дата подачи заявки").classes("report-cell report-cell-head report-cell-center")
                    ui.label("Воронка подбора").classes("report-cell report-cell-head report-cell-group report-cell-funnel report-cell-span3")
                    ui.label("Проблемные заявки").classes("report-cell report-cell-head report-cell-group report-cell-problem report-cell-span2")
                with ui.element("div").classes("w-full report-head report-head-sub report-grid").style("gap: 8px"):
                    ui.label("").classes("report-cell report-cell-head report-cell-empty")
                    for h in ("Ждали заселения", "Подобрано жилье", "Заселены"):
                        ui.label(h).classes("report-cell report-cell-head report-cell-sub report-cell-center report-cell-funnel")
                    for h in ("Нет подходящих дат", "Нет подходящих домов"):
                        ui.label(h).classes("report-cell report-cell-head report-cell-sub report-cell-center report-cell-problem")
                for r in rows:
                    with ui.element("div").classes("w-full report-row report-grid").style("gap: 8px"):
                        ui.label(to_display(r['date'])).classes("report-cell")
                        _report_link(f"/guest_ghost?filter=waiting&date={r['date']}&period_start={period_start}", str(r["waiting"]), "report-cell report-cell-funnel")
                        _report_link(f"/guest_ghost?filter=chosen&date={r['date']}&period_start={period_start}", str(r["chosen"]), "report-cell report-cell-funnel")
                        _report_link(f"/guest_ghost?filter=reserved&date={r['date']}&period_start={period_start}", str(r["reserved"]), "report-cell report-cell-funnel")
                        _report_link(f"/guest_ghost?filter=no_dates&date={r['date']}&period_start={period_start}", str(r["no_dates"]), "report-cell report-cell-problem")
                        _report_link(f"/guest_ghost?filter=no_homes&date={r['date']}&period_start={period_start}", str(r["no_homes"]), "report-cell report-cell-problem")
            else:
                # шапка: уровень 1 — группы, уровень 2 — колонки групп (grid 7 колонок)
                with ui.element("div").classes("w-full report-head report-grid-7").style("gap: 8px"):
                    ui.label("Дом").classes("report-cell report-cell-head report-cell-center")
                    ui.label("Всего мест").classes("report-cell report-cell-head report-cell-center")
                    ui.label("Воронка наполнения").classes("report-cell report-cell-head report-cell-group report-cell-funnel report-cell-span2")
                    ui.label("Аналитика дома").classes("report-cell report-cell-head report-cell-group report-cell-analytics report-cell-span3")
                with ui.element("div").classes("w-full report-head report-head-sub report-grid-7").style("gap: 8px"):
                    ui.label("").classes("report-cell report-cell-head report-cell-empty")
                    ui.label("").classes("report-cell report-cell-head report-cell-empty")
                    for h in ("Свободно на начало", "Свободно на конец"):
                        ui.label(h).classes("report-cell report-cell-head report-cell-sub report-cell-center report-cell-funnel")
                    for h in ("MAX % соответствия", "AVG % соответствия", "Динамика наполнения"):
                        ui.label(h).classes("report-cell report-cell-head report-cell-sub report-cell-center report-cell-analytics")
                for r in rows:
                    with ui.element("div").classes("w-full report-row report-grid-7").style("gap: 8px"):
                        _report_link(f"/guest_ghost?filter=house_dynamics&home_id={r['home_id']}&period_start={period_start}", r["name"], "report-cell")
                        _report_link(f"/guest_ghost?filter=house_dynamics&home_id={r['home_id']}&period_start={period_start}", str(r["total_rooms"]), "report-cell")
                        _report_link(f"/guest_ghost?filter=house_dynamics&home_id={r['home_id']}&period_start={period_start}", str(r["free_start"]), "report-cell report-cell-funnel")
                        _report_link(f"/guest_ghost?filter=house_dynamics&home_id={r['home_id']}&period_start={period_start}", str(r["free_end"]), "report-cell report-cell-funnel")
                        _report_link(f"/guest_ghost?filter=house_dynamics&home_id={r['home_id']}&period_start={period_start}", str(r["max_match"]) if r["max_match"] is not None else "-", "report-cell report-cell-analytics")
                        _report_link(f"/guest_ghost?filter=house_dynamics&home_id={r['home_id']}&period_start={period_start}", str(r["avg_match"]) if r["avg_match"] is not None else "-", "report-cell report-cell-analytics")
                        _report_link(f"/guest_ghost?filter=house_dynamics&home_id={r['home_id']}&period_start={period_start}", f"{r['fill_dynamics']}%", "report-cell report-cell-analytics")

    async def _build_report():
        nonlocal report_mode
        if report_mode is None:
            report_mode_field.props(add="error")
            return
        try:
            days = int(days_spinner.value or 1)
            data = await asyncio.to_thread(api.get_report, report_mode, days)
            logger.info("layout: отчёт сформирован, mode=%s, days=%s, строк=%s", report_mode, days, len(data.get("rows", [])))
        except Exception as e:
            logger.error("layout: ошибка формирования отчёта: %s", e)
            report_area.clear()
            report_empty.set_visibility(True)
            return
        _render_report_table(data)

    report_go_btn.disable()
    report_go_btn.on_click(_build_report)
