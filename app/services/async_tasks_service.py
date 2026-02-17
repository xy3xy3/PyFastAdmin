"""异步周期任务页面服务。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services import task_monitor_service
from app.services.task_registry import list_periodic_tasks, resolve_display_values
from app.tasks import load_builtin_tasks


@dataclass(frozen=True, slots=True)
class TaskTableColumn:
    """任务页面表格列。"""

    key: str
    label: str


_BASE_COLUMNS = [
    TaskTableColumn(key="key", label="任务 Key"),
    TaskTableColumn(key="name", label="任务名称"),
    TaskTableColumn(key="tags", label="标签"),
    TaskTableColumn(key="last_status", label="最近状态"),
    TaskTableColumn(key="last_finished_at", label="最近完成时间"),
    TaskTableColumn(key="last_duration_ms", label="耗时(ms)"),
    TaskTableColumn(key="success_count", label="成功次数"),
    TaskTableColumn(key="failure_count", label="失败次数"),
    TaskTableColumn(key="worker_id", label="最近 Worker"),
]


def _normalize_status(raw_status: str) -> str:
    """规范化状态文案。"""

    status = str(raw_status).strip().lower()
    if status == "success":
        return "success"
    if status == "failed":
        return "failed"
    if status == "running":
        return "running"
    return "idle"


def _build_tabs(tags: list[str]) -> list[dict[str, str]]:
    """根据标签构建 Tab。"""

    tabs = [{"key": "all", "name": "全部"}]
    for tag in tags:
        tabs.append({"key": tag, "name": tag})
    return tabs


def _match_query(row: dict[str, str], search_q: str) -> bool:
    """判断行数据是否匹配关键词。"""

    if not search_q:
        return True
    values = [
        row.get("key", ""),
        row.get("name", ""),
        row.get("tags", ""),
        row.get("last_status", ""),
    ]
    keyword = search_q.lower()
    return any(keyword in value.lower() for value in values)


async def build_task_table_payload(filters: dict[str, str]) -> dict[str, Any]:
    """构建周期任务列表页面数据。"""

    load_builtin_tasks()
    definitions = list_periodic_tasks()

    dynamic_columns: dict[str, TaskTableColumn] = {}
    tag_values: list[str] = []
    rows: list[dict[str, Any]] = []

    for definition in definitions:
        monitor = await task_monitor_service.get_periodic_monitor(definition.key)
        display_values = await resolve_display_values(definition.display_values_provider)

        for column in definition.display_columns:
            if column.key not in dynamic_columns:
                dynamic_columns[column.key] = TaskTableColumn(key=column.key, label=column.label)

        row_values = {
            "key": definition.key,
            "name": definition.name,
            "tags": ", ".join(definition.tags) if definition.tags else "-",
            "last_status": _normalize_status(monitor.get("last_status", "")),
            "last_finished_at": monitor.get("last_finished_at", "-"),
            "last_duration_ms": monitor.get("last_duration_ms", "-"),
            "success_count": monitor.get("success_count", "0"),
            "failure_count": monitor.get("failure_count", "0"),
            "worker_id": monitor.get("worker_id", "-"),
        }

        for column in dynamic_columns.values():
            row_values.setdefault(column.key, "-")
        for key, value in display_values.items():
            row_values[str(key)] = str(value)

        for tag in definition.tags:
            if tag not in tag_values:
                tag_values.append(tag)

        rows.append(
            {
                "key": definition.key,
                "tags": definition.tags,
                "values": row_values,
            }
        )

    selected_tab = str(filters.get("tab") or "all").strip() or "all"
    if selected_tab != "all" and selected_tab not in set(tag_values):
        selected_tab = "all"

    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        if selected_tab != "all" and selected_tab not in row["tags"]:
            continue
        if not _match_query(row["values"], str(filters.get("search_q") or "")):
            continue
        filtered_rows.append(row)

    return {
        "tabs": _build_tabs(tag_values),
        "selected_tab": selected_tab,
        "columns": [*_BASE_COLUMNS, *dynamic_columns.values()],
        "rows": filtered_rows,
    }
