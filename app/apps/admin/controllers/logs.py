"""操作日志控制器。"""

from __future__ import annotations

from typing import Any, Mapping

from fastapi import APIRouter, HTTPException, Request, Response

from app.apps.admin.rendering import (
    base_context,
    build_pagination,
    jinja,
    parse_positive_int,
    read_request_values,
    set_hx_swap_headers,
)
from app.services import config_service, log_service, permission_decorator

router = APIRouter(prefix="/admin")

LOG_PAGE_SIZE = 15

LOG_SORT_OPTIONS: dict[str, str] = {
    "created_desc": "最新优先",
    "created_asc": "最早优先",
}


def parse_log_filters(values: Mapping[str, Any]) -> tuple[dict[str, str], int]:
    """解析并清洗日志筛选条件。"""

    search_q = str(values.get("search_q") or values.get("q") or "").strip()
    search_action = str(values.get("search_action") or "").strip().lower()
    if search_action not in set(config_service.AUDIT_ACTION_ORDER):
        search_action = ""

    search_module = str(values.get("search_module") or "").strip()
    if search_module not in log_service.MODULE_LABELS:
        search_module = ""

    search_sort = str(values.get("search_sort") or "created_desc").strip()
    if search_sort not in LOG_SORT_OPTIONS:
        search_sort = "created_desc"

    page = parse_positive_int(values.get("page"), default=1)
    return (
        {
            "search_q": search_q,
            "search_action": search_action,
            "search_module": search_module,
            "search_sort": search_sort,
        },
        page,
    )


async def build_log_table_context(
    request: Request,
    filters: dict[str, str],
    page: int,
) -> dict[str, Any]:
    """构建日志表格上下文。"""

    items, total = await log_service.list_logs(filters, page, LOG_PAGE_SIZE)
    pagination = build_pagination(total, page, LOG_PAGE_SIZE)

    return {
        **base_context(request),
        "items": items,
        "filters": filters,
        "pagination": pagination,
        "action_labels": config_service.AUDIT_ACTION_LABELS,
        "module_labels": log_service.MODULE_LABELS,
    }


@router.get("/logs")
@jinja.page("pages/logs.html")
async def logs_page(request: Request) -> dict[str, Any]:
    """日志页面。"""

    filters, page = parse_log_filters(request.query_params)
    context = await build_log_table_context(request, filters, page)
    context["log_sort_options"] = LOG_SORT_OPTIONS
    context["log_action_order"] = config_service.AUDIT_ACTION_ORDER
    context["module_options"] = log_service.MODULE_LABELS
    await log_service.record_request(
        request,
        action="read",
        module="logs",
        target="操作日志",
        detail="访问操作日志页面",
    )
    return context


@router.get("/logs/table")
@jinja.page("partials/logs_table.html")
async def logs_table(request: Request) -> dict[str, Any]:
    """日志表格 partial。"""

    filters, page = parse_log_filters(request.query_params)
    return await build_log_table_context(request, filters, page)


@router.delete("/logs/{log_id}")
@permission_decorator.permission_meta("operation_logs", "delete")
@jinja.hx("partials/logs_table.html", no_data=True)
async def logs_delete(request: Request, response: Response, log_id: str) -> dict[str, Any]:
    """删除单条操作日志。"""

    request_values = await read_request_values(request)
    filters, page = parse_log_filters(request_values)

    item = await log_service.get_log(log_id)
    if not item:
        raise HTTPException(status_code=404, detail="日志不存在")

    await log_service.delete_log(item)
    await log_service.record_request(
        request,
        action="delete",
        module="logs",
        target="操作日志",
        target_id=log_id,
        detail=f"删除日志 {log_id}",
    )

    set_hx_swap_headers(
        response,
        target="#logs-table",
        trigger={
            "rbac-toast": {
                "title": "已删除",
                "message": "日志记录已删除",
                "variant": "warning",
            }
        },
    )
    return await build_log_table_context(request, filters, page)


@router.post("/logs/bulk-delete")
@permission_decorator.permission_meta("operation_logs", "delete")
@jinja.hx("partials/logs_table.html", no_data=True)
async def logs_bulk_delete(request: Request, response: Response) -> dict[str, Any]:
    """批量删除操作日志。"""

    request_values = await read_request_values(request)
    filters, page = parse_log_filters(request_values)
    form_data = await request.form()
    selected_ids = [str(item).strip() for item in form_data.getlist("selected_ids") if str(item).strip()]
    selected_ids = list(dict.fromkeys(selected_ids))

    deleted_count = 0
    skipped_count = 0
    for log_id in selected_ids:
        item = await log_service.get_log(log_id)
        if not item:
            skipped_count += 1
            continue
        await log_service.delete_log(item)
        deleted_count += 1

    if deleted_count > 0:
        await log_service.record_request(
            request,
            action="delete",
            module="logs",
            target="操作日志",
            detail=f"批量删除日志 {deleted_count} 条",
        )

    if deleted_count == 0:
        toast_message = "未删除任何日志，请先勾选记录"
    elif skipped_count > 0:
        toast_message = f"已删除 {deleted_count} 条，跳过 {skipped_count} 条"
    else:
        toast_message = f"已批量删除 {deleted_count} 条日志"

    set_hx_swap_headers(
        response,
        target="#logs-table",
        trigger={
            "rbac-toast": {
                "title": "批量删除完成",
                "message": toast_message,
                "variant": "warning",
            }
        },
    )
    return await build_log_table_context(request, filters, page)
