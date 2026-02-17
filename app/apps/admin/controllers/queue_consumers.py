"""队列消费者监控控制器。"""

from __future__ import annotations

from typing import Any, Mapping

from fastapi import APIRouter, Request

from app.apps.admin.rendering import base_context, build_pagination, jinja, parse_positive_int
from app.services import log_service, permission_decorator, queue_consumers_service

router = APIRouter(prefix="/admin")
PAGE_SIZE = 10


def parse_filters(values: Mapping[str, Any]) -> tuple[dict[str, str], int]:
    """解析消费者列表筛选参数。"""

    search_q = str(values.get("search_q") or values.get("q") or "").strip()
    tab = str(values.get("tab") or "all").strip() or "all"
    page = parse_positive_int(values.get("page"), default=1)
    return {"search_q": search_q, "tab": tab}, page


async def build_table_context(request: Request, filters: dict[str, str], page: int) -> dict[str, Any]:
    """构建队列消费者表格上下文。"""

    payload = await queue_consumers_service.build_consumer_table_payload(filters)
    pagination = build_pagination(len(payload["rows"]), page, PAGE_SIZE)
    start = (pagination["page"] - 1) * PAGE_SIZE

    return {
        **base_context(request),
        "filters": {
            "search_q": filters["search_q"],
            "tab": payload["selected_tab"],
        },
        "tabs": payload["tabs"],
        "columns": payload["columns"],
        "rows": payload["rows"][start : start + PAGE_SIZE],
        "pagination": pagination,
    }


@router.get("/queue_consumers")
@permission_decorator.permission_meta("queue_consumers", "read")
@jinja.page("pages/queue_consumers.html")
async def queue_consumers_page(request: Request) -> dict[str, Any]:
    """队列消费者监控页面。"""

    filters, page = parse_filters(request.query_params)
    context = await build_table_context(request, filters, page)
    await log_service.record_request(
        request,
        action="read",
        module="queue_consumers",
        target="队列消费",
        detail=f"访问队列消费页面（tab={context['filters']['tab']}）",
    )
    return context


@router.get("/queue_consumers/table")
@permission_decorator.permission_meta("queue_consumers", "read")
@jinja.page("partials/queue_consumers_table.html")
async def queue_consumers_table(request: Request) -> dict[str, Any]:
    """队列消费者表格 partial。"""

    filters, page = parse_filters(request.query_params)
    context = await build_table_context(request, filters, page)
    await log_service.record_request(
        request,
        action="read",
        module="queue_consumers",
        target="队列消费",
        detail=f"筛选队列消费列表（tab={context['filters']['tab']}，q={context['filters']['search_q'] or '-'}）",
    )
    return context
