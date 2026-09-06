"""Переиспользуемые виджеты.

number_spinner — number-поле с кастомными синими стрелками ▲/▼ вместо браузерного спиннера.
date_picker    — readonly поле даты (дд/мм/гггг) с календарём (русский, серый стиль).

Конвертация: в интерфейсе всегда дд/мм/гггг, в БД всегда ISO гггг-мм-дд.
"""

import asyncio
import logging
from datetime import datetime

from nicegui import ui

logger = logging.getLogger(__name__)


def to_display(iso_date: str | None) -> str:
    """ISO гггг-мм-дд → дд/мм/гггг (для интерфейса)."""
    if not iso_date:
        return ""
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso_date


def to_iso(display_date: str | None) -> str:
    """дд/мм/гггг → ISO гггг-мм-дд (для БД)."""
    if not display_date:
        return ""
    try:
        return datetime.strptime(display_date, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return display_date


def number_spinner(label: str | None = None, *, value: float | None = None,
                   min_value: float | None = None, max_value: float | None = None,
                   precision: int | None = None, step: float | None = None,
                   on_change=None, **kwargs) -> ui.number:
    field = ui.number(label, value=value, min=min_value, max=max_value,
                      precision=precision, step=step, on_change=on_change, **kwargs)

    def _step(delta: int):
        step_size = float(step if step is not None else 1)
        current = field.value if field.value is not None else (value or 0)
        new_value = current + delta * step_size
        if min_value is not None:
            new_value = max(new_value, float(min_value))
        if max_value is not None:
            new_value = min(new_value, float(max_value))
        if precision is not None:
            new_value = round(new_value, precision)
        field.value = new_value

    with field:
        with ui.element("div").classes("spin-arrows"):
            up_btn = ui.button(icon="keyboard_arrow_up").props("flat round dense")
            up_btn.classes("spin-btn")
            up_btn.on("click", lambda: _step(1))
            down_btn = ui.button(icon="keyboard_arrow_down").props("flat round dense")
            down_btn.classes("spin-btn")
            down_btn.on("click", lambda: _step(-1))
    return field


def date_picker(iso_value: str | None = None, *, classes: str = "") -> ui.input:
    """Readonly поле даты с календарём.

    Поле показывает дд/мм/гггг, .value — дд/мм/гггг (интерфейсный формат).
    Для БД конвертировать через to_iso().
    Календарь открывается только по клику на иконку.
    """
    field = ui.input(value=to_display(iso_value)).props("readonly")
    field.classes(classes)

    with field:
        with ui.menu().classes("date-menu").props("no-focus") as menu:
            picker = ui.date(value=field.value or "", mask="DD/MM/YYYY").props("dark no-unset")
            picker.classes("q-date-dark")
            picker.props(
                'locale={"daysShort":["Вс","Пн","Вт","Ср","Чт","Пт","Сб"],'
                '"days":["Воскресенье","Понедельник","Вторник","Среда","Четверг","Пятница","Суббота"],'
                '"monthsShort":["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"],'
                '"months":["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"],'
                '"firstDayOfWeek":1}'
            )
        date_icon = ui.icon("event").classes("date-icon")

    def _set_date(value: str):
        field.value = value
        menu.close()

    picker.on("update:model-value", lambda e: _set_date(e.args[0] if isinstance(e.args, list) else e.args))

    def _open_menu():
        menu.open()
        field.run_method("focus")

    field.on("click", _open_menu)
    date_icon.on("click", _open_menu)
    return field


class AutocompleteInput:
    """Поле ввода с выпадающим меню автокомплита (тёмная тема).

    options — список вариантов (подгружается внешне, например через asyncio.to_thread).
    excluded — набор строк, которые скрываются из меню (уже выбранные).
    При выборе пункта меню подставляет значение в поле и вызывает on_pick.
    """

    def __init__(self, *, classes: str = "", on_pick=None):
        self._options: list[str] = []
        self._excluded: set[str] = set()
        self.on_pick = on_pick
        self.input = ui.input().classes(classes)
        with self.input:
            with ui.menu().classes("auto-menu").props("auto-close no-focus") as self.menu:
                pass
            self.arrow = ui.icon("arrow_drop_down").classes("auto-arrow")

        self.input.on("click", lambda: self._render(open_menu=True))
        self.input.on("keyup", lambda: self._render(open_menu=False))

    @property
    def value(self) -> str:
        return self.input.value or ""

    def set_options(self, options: list[str]):
        self._options = options

    def set_excluded(self, excluded: set[str]):
        self._excluded = excluded

    def pick(self, name: str):
        """Внешнее заполнение значения (например, после клика по чипу)."""
        self.input.value = name

    def _render(self, open_menu: bool):
        text = self.value.strip().lower()
        available = [o for o in self._options if o not in self._excluded]
        matches = [o for o in available if text in o.lower()]
        self.menu.clear()
        with self.menu:
            if matches:
                for opt in matches:
                    ui.item(opt, on_click=lambda o=opt: self._pick(o))
            else:
                ui.item("Нет совпадений").props("disabled")
        if open_menu:
            self.menu.open()
            self.input.run_method("focus")

    def _pick(self, name: str):
        self.input.value = name
        self.menu.close()
        self.input.run_method("focus")
        if self.on_pick:
            self.on_pick(name)


class ChipGroup:
    """Группа «поле + значение + кнопка +» для набора пар ключ:значение.

    items — словарь ключ → значение (хранится в UI, чипы строятся из него).
    on_add — вызывается после добавления новой пары; on_remove — после удаления.

    Структура зависит от контекста: сам компонент создаёт только содержимое
    панели (поле, значение, кнопку, чипы, иконку пустоты) в текущем контексте.
    Родитель сам раскладывает их по фреймам: заголовок и панель чипов.
    """

    def __init__(self, *, value_label: str = "со значением", on_add=None, on_remove=None):
        self.items: dict[str, str] = {}
        self.on_add = on_add
        self.on_remove = on_remove
        self.error = False
        self.autocomplete = AutocompleteInput(classes="w-56 chip-field")
        self.value_label = ui.label(value_label).classes("panel-label")
        self.value_input = ui.input().classes("flex-1 chip-field")
        self.add_btn = ui.button(icon="add").props("flat round dense").classes("round-plus")

        self.add_btn.on("click", self._add)
        self.value_input.on("mousedown", self._focus_value)
        self.autocomplete.input.on("keyup", lambda: self.autocomplete.input.props(remove="error"))
        self.value_input.on("keyup", lambda: self.value_input.props(remove="error"))

    def _focus_value(self):
        """Фокус в поле значения с первого клика: закрыть меню автокомплита (если открыто) и поставить фокус.

        mousedown срабатывает до того, как Quasar-меню перехватит клик (auto-close),
        иначе первый клик «съедается» закрытием меню и фокус встаёт только со второго.
        """
        self.autocomplete.menu.close()
        self.value_input.run_method("focus")

    def _add(self):
        key = self.autocomplete.value.strip()
        value = (self.value_input.value or "").strip()
        if not key:
            self.autocomplete.input.props(add="error")
        if not value:
            self.value_input.props(add="error")
        if not key or not value:
            return
        self.items[key] = value
        self.autocomplete.input.value = ""
        self.value_input.value = ""
        self.refresh()

    def _remove(self, key: str):
        self.items.pop(key, None)
        self.refresh()

    def build_area(self):
        """Создать контейнер для чипов и иконку пустоты (панель-бокс)."""
        self.chips_row = ui.row().classes("w-full panel-area")
        self.empty_icon = ui.icon("label").classes("panel-empty")
        # родительский panel-box запомнить для подсветки ошибки
        parent_slot = self.chips_row.parent_slot
        self.chips_box = parent_slot.parent if parent_slot else None
        return self

    def set_error(self, on: bool):
        """Включить/выключить красную подсветку поля чипов (рамка + иконка)."""
        self.error = on
        if hasattr(self, "chips_box"):
            if on:
                self.chips_box.classes(add="error")
            else:
                self.chips_box.classes(remove="error")

    def refresh(self):
        """Перестроить чипы и обновить исключённые варианты автокомплита."""
        self.autocomplete.set_excluded(set(self.items.keys()))
        if hasattr(self, "chips_row"):
            self.chips_row.clear()
            self.empty_icon.set_visibility(not self.items)
            if self.error and self.items:
                self.set_error(False)
            with self.chips_row:
                for key, value in self.items.items():
                    ui.chip(f"{key}: {value}", removable=True).on("remove", lambda k=key: self._remove(k))
        if self.on_add:
            self.on_add()

    def clear(self):
        self.items.clear()
        self.refresh()


class ResultPopup:
    """Компактный попап результата (по центру экрана): текст + кнопка «ОК».

    Используется для уведомлений после обогащения карточек (success / LLM error).
    """

    def __init__(self, *, text: str = "", ok_label: str = "ОК"):
        self.dialog = ui.dialog()
        with self.dialog, ui.card().classes("result-popup"):
            with ui.column().classes("w-full items-center").style("gap: 12px"):
                self.label = ui.label(text).classes("result-popup-text")
                self.ok_btn = ui.button(ok_label).props("no-caps flat").classes("page-btn")
        self.ok_btn.on("click", lambda: self.close())

    @property
    def text(self) -> str:
        return self.label.text

    @text.setter
    def text(self, value: str):
        self.label.text = value

    def open(self):
        self.dialog.open()

    def close(self):
        self.dialog.close()


class GhostLoader:
    """Прелоадер-облачко для списков (заявки/дома).

    Виден с первого кадра: попадает в начальный HTML страницы (серверный
    рендеринг NiceGUI), пока идёт первичная загрузка данных. Скрывается
    серверным set_visibility(False) после отрисовки списка.
    """

    def __init__(self, *, text: str = "Загружаем..."):
        self._container = ui.column().classes("w-full ghost-loader").style("gap: 0")
        with self._container:
            with ui.element("div").classes("ghost-loader-cloud"):
                ui.element("div").classes("ghost-puff ghost-puff-1")
                ui.element("div").classes("ghost-puff ghost-puff-2")
                ui.element("div").classes("ghost-puff ghost-puff-3")
                ui.element("div").classes("ghost-puff ghost-puff-4")
            ui.label(text).classes("ghost-loader-text")

    def hide(self):
        if not self._container.is_deleted:
            self._container.set_visibility(False)
