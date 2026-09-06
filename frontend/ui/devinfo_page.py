"""Вкладка DevINFO (шаг 13): фрейм с PLAN.md (дерево-аккордеон), кнопки «Свернуть/Развернуть все»,
нижняя панель «Обнулить БД» / «Предзаполнить» + persistent-попапы процесса и результата.
"""

import asyncio
import logging
import re
from pathlib import Path

from nicegui import ui

from frontend.api.client import ApiClient

logger = logging.getLogger(__name__)

PLAN_PATH = Path(__file__).parent.parent.parent / "PLAN.md"


def _parse_plan(text: str) -> list[dict]:
    """Разобрать PLAN.md в дерево секций по заголовкам #/##/###.

    Каждый узел: {"level", "title", "children", "body", "code_body"}.
    body — обычный текст секции, code_body — строки код-блоков (``` ```).
    """
    root: list[dict] = []
    stack: list[dict] = []
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m and not in_code:
            level = len(m.group(1))
            node = {"level": level, "title": m.group(2).strip(), "children": [], "body": [], "code_body": []}
            while stack and stack[-1]["level"] >= level:
                stack.pop()
            if stack:
                stack[-1]["children"].append(node)
            else:
                root.append(node)
            stack.append(node)
            continue
        if not stack:
            continue
        if in_code:
            stack[-1]["code_body"].append(line)
        else:
            stack[-1]["body"].append(line)
    return root


def build_devinfo_page(config: dict):
    api = ApiClient(config.get("app", {}).get("api_url", "http://localhost:8080/api"))

    with ui.column().classes("w-full h-full").style("gap: 0") as page:
        with ui.element("div").classes("w-full page-header"):
            with ui.row().classes("items-center").style("gap: 8px"):
                ui.label("DevINFO").classes("text-h6")
                with ui.row().classes("lfilter-groups"):
                    with ui.row().classes("local-filters").style("gap: 6px"):
                        expand_all_btn = ui.button(icon="unfold_more").props("flat round dense").classes("lfilter-btn").tooltip("Развернуть все")
                        collapse_all_btn = ui.button(icon="unfold_less").props("flat round dense").classes("lfilter-btn").tooltip("Свернуть все")

        with ui.element("div").classes("w-full flex-1 page-body"):
            with ui.column().classes("w-full h-full report-panel").style("gap: 8px"):
                plan_area = ui.column().classes("w-full flex-1 report-area").style("gap: 2px")

        with ui.element("div").classes("w-full page-footer"):
            with ui.row().classes("w-full items-center gap-2"):
                reset_btn = ui.button("Обнулить БД").props("no-caps flat").classes("page-btn")
                seed_btn = ui.button("Предзаполнить").props("no-caps flat").classes("page-btn")

    # persistent-попапы процесса и результата
    with ui.dialog().props("persistent") as process_dialog, ui.card().classes("result-popup"):
        with ui.column().classes("w-full items-center").style("gap: 12px"):
            ui.spinner("dots", size="32px").classes("text-primary")
            process_label = ui.label("").classes("result-popup-text")

    result_popup = ui.dialog()
    with result_popup, ui.card().classes("result-popup"):
        with ui.column().classes("w-full items-center").style("gap: 12px"):
            result_label = ui.label("").classes("result-popup-text")
            ok_btn = ui.button("ОК").props("no-caps flat").classes("page-btn")
    ok_btn.on("click", result_popup.close)

    # ---------- дерево PLAN.md ----------

    _expanded: set[int] = set()
    _nodes: list[dict] = []
    _node_ids: dict[int, dict] = {}

    def _render_tree():
        plan_area.clear()
        if not _nodes:
            with plan_area:
                ui.label("PLAN.md не найден.").classes("page-empty")
            return
        with plan_area:
            for node in _nodes:
                _render_node(node, 0)

    def _render_body_line(line: str, container=None):
        """Вывести строку body с markdown-метками: **жирный** → жирный, `код` → моноширинный.

        Безопасный способ: разбиваем строку на фрагменты и собираем из ui.label с классами
        (HTML-теги в тексте PLAN.md не исполняются). Если container передан — рендерим в него
        (для буллета: буллет и текст в одном ряду), иначе создаём свой row.
        """
        parts = re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", line)
        if container is None:
            container = ui.row().classes("w-full plan-body-row").style("gap: 4px")
        with container:
            for part in parts:
                if not part:
                    continue
                if part.startswith("**") and part.endswith("**"):
                    ui.label(part[2:-2]).classes("plan-body plan-bold")
                elif part.startswith("`") and part.endswith("`"):
                    ui.label(part[1:-1]).classes("plan-body plan-inline-code")
                else:
                    ui.label(part).classes("plan-body")

    def _render_node(node: dict, depth: int):
        node_id = id(node)
        _node_ids[node_id] = node
        expanded = node_id in _expanded
        with ui.column().classes("w-full plan-node").style("gap: 0"):
            with ui.row().classes("w-full plan-head items-center").style("gap: 6px").on(
                "click", lambda _nid=node_id: _toggle_node(_nid)
            ):
                icon = ui.icon("arrow_drop_down" if expanded else "chevron_right").classes("plan-arrow")
                ui.label(node["title"]).classes("plan-title")
            if expanded:
                if node["body"]:
                    for line in node["body"]:
                        if line.strip().startswith("- "):
                            with ui.row().classes("w-full plan-body-row").style("gap: 4px") as bullet_row:
                                ui.label("•").classes("plan-body plan-bullet")
                                _render_body_line(line.strip()[2:], container=bullet_row)
                        else:
                            m = re.match(r"^(\d+)\.\s+(.*)$", line.strip())
                            if m:
                                with ui.row().classes("w-full plan-body-row").style("gap: 4px") as num_row:
                                    ui.label(f"{m.group(1)}.").classes("plan-body plan-number")
                                    _render_body_line(m.group(2), container=num_row)
                            else:
                                _render_body_line(line)
                if node["code_body"]:
                    ui.label("\n".join(node["code_body"])).classes("plan-code")
                if node["children"]:
                    with ui.column().classes("w-full plan-children").style("gap: 0"):
                        for child in node["children"]:
                            _render_node(child, depth + 1)

    def _toggle_node(node_id: int):
        if node_id in _expanded:
            _expanded.discard(node_id)
        else:
            _expanded.add(node_id)
        _render_tree()

    def _expand_all():
        _expanded.clear()
        for node in _nodes:
            _collect_ids(node)
        _render_tree()

    def _collapse_all():
        _expanded.clear()
        _render_tree()

    def _collect_ids(node: dict):
        _expanded.add(id(node))
        for child in node["children"]:
            _collect_ids(child)

    expand_all_btn.on("click", _expand_all)
    collapse_all_btn.on("click", _collapse_all)

    # ---------- нижняя панель ----------

    async def _run_process(action: str, label: str):
        process_label.text = label
        process_dialog.open()
        try:
            if action == "reset":
                result = await asyncio.to_thread(api.reset_db)
                result_label.text = f"База данных обнулена: {result.get('status', 'ok')}"
            else:
                result = await asyncio.to_thread(api.seed_demo)
                result_label.text = (f"Предзаполнено: домов={result.get('hotels', 0)}, "
                                     f"заявок={result.get('ghosts', 0)}, ошибок={result.get('errors', 0)}")
        except Exception as e:
            logger.error("devinfo: %s: %s", action, e)
            result_label.text = f"Ошибка: {e}"
        finally:
            process_dialog.close()
            result_popup.open()

    reset_btn.on("click", lambda: asyncio.create_task(_run_process("reset", "Обнуление базы данных...")))
    seed_btn.on("click", lambda: asyncio.create_task(_run_process("seed", "Предзаполнение базы данных...")))

    # первичная загрузка PLAN.md
    try:
        _nodes = _parse_plan(PLAN_PATH.read_text(encoding="utf-8"))
        logger.info("devinfo: PLAN.md загружен, секций=%s", len(_nodes))
    except OSError as e:
        logger.error("devinfo: не удалось прочитать PLAN.md: %s", e)
        _nodes = []
    _render_tree()

    return page
