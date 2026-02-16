"""操作日志控制器。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from fasthx.jinja import Jinja
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.templating import Jinja2Templates

from app.services import config_service, log_service, permission_decorator

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
jinja = Jinja(templates)
router = APIRouter(prefix="/admin")

LOG_PAGE_SIZE = 15

LOG_SORT_OPTIONS: dict[str, str] = {
    "created_desc": "最新优先",
    "created_asc": "最早优先",
}


def fmt_dt(value: datetime | None) -> str:
    """格式化日期时间，统一页面展示精度。"""

    if not value:
        return ""
    if value.tzinfo is None:
        return value.strftime("%Y-%m-%d %H:%M")
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


templates.env.filters["fmt_dt"] = fmt_dt


def base_context(request: Request) -> dict[str, Any]:
    """构建日志模块模板基础上下文。"""

    return {
        "request": request,
        "current_admin": request.session.get("admin_name"),
    }


def parse_positive_int(value: Any, default: int = 1) -> int:
    """安全解析正整数参数，非法值回退到默认值。"""

    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


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


def build_pagination(total: int, page: int, page_size: int) -> dict[str, Any]:
    """构建分页数据，供模板渲染页码和统计信息。"""

    total_pages = max((total + page_size - 1) // page_size, 1)
    current = min(max(page, 1), total_pages)
    start_page = max(current - 2, 1)
    end_page = min(start_page + 4, total_pages)
    start_page = max(end_page - 4, 1)

    if total == 0:
        start_item = 0
        end_item = 0
    else:
        start_item = (current - 1) * page_size + 1
        end_item = min(current * page_size, total)

    return {
        "page": current,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_prev": current > 1,
        "has_next": current < total_pages,
        "prev_page": current - 1,
        "next_page": current + 1,
        "pages": list(range(start_page, end_page + 1)),
        "start_item": start_item,
        "end_item": end_item,
    }


async def read_request_values(request: Request) -> dict[str, str]:
    """统一读取 Query + Form 参数，兼容 HTMX 请求。"""

    values: dict[str, str] = {key: value for key, value in request.query_params.items()}
    if request.method == "GET":
        return values

    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" not in content_type and "multipart/form-data" not in content_type:
        return values

    form_data = await request.form()
    for key, value in form_data.items():
        if isinstance(value, str):
            values[key] = value
    return values


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

    response.headers["HX-Retarget"] = "#logs-table"
    response.headers["HX-Reswap"] = "outerHTML"
    response.headers["HX-Trigger"] = json.dumps(
        {
            "rbac-toast": {
                "title": "已删除",
                "message": "日志记录已删除",
                "variant": "warning",
            }
        },
        ensure_ascii=True,
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

    response.headers["HX-Retarget"] = "#logs-table"
    response.headers["HX-Reswap"] = "outerHTML"

    if deleted_count == 0:
        toast_message = "未删除任何日志，请先勾选记录"
    elif skipped_count > 0:
        toast_message = f"已删除 {deleted_count} 条，跳过 {skipped_count} 条"
    else:
        toast_message = f"已批量删除 {deleted_count} 条日志"

    response.headers["HX-Trigger"] = json.dumps(
        {
            "rbac-toast": {
                "title": "批量删除完成",
                "message": toast_message,
                "variant": "warning",
            }
        },
        ensure_ascii=True,
    )
    return await build_log_table_context(request, filters, page)
