"""Admin 渲染与 HTMX 公共工具。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Mapping

from fasthx.jinja import Jinja
from fastapi import Request, Response
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
jinja = Jinja(templates)


def fmt_dt(value: datetime | None) -> str:
    """格式化日期时间，统一页面展示精度。"""

    if not value:
        return ""
    if value.tzinfo is None:
        return value.strftime("%Y-%m-%d %H:%M")
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


templates.env.filters["fmt_dt"] = fmt_dt


@dataclass(frozen=True, slots=True)
class TemplatePayload:
    """动态模板渲染载体。"""

    template: str
    context: dict[str, Any]


def render_template_payload(
    result: TemplatePayload,
    *,
    context: dict[str, Any],
    request: Request,
) -> str:
    """根据 payload 指定的模板和上下文渲染 HTML。"""

    rendered = templates.TemplateResponse(
        name=result.template,
        context=result.context,
        request=request,
    )
    return bytes(rendered.body).decode(rendered.charset)


def base_context(request: Request) -> dict[str, Any]:
    """构建 Admin 页面的基础上下文。"""

    return {
        "request": request,
        "current_admin": request.session.get("admin_name"),
    }


def is_htmx_request(request: Request) -> bool:
    """判断请求是否来自 HTMX。"""

    return request.headers.get("hx-request", "").strip().lower() == "true"


def set_form_error_status(response: Response, request: Request) -> None:
    """统一设置表单校验失败时的状态码策略。"""

    response.status_code = 200 if is_htmx_request(request) else 422


def parse_positive_int(value: Any, default: int = 1) -> int:
    """安全解析正整数参数，非法值回退到默认值。"""

    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


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


def set_hx_swap_headers(
    response: Response,
    *,
    target: str,
    trigger: Mapping[str, Any] | None = None,
    reswap: str = "outerHTML",
) -> None:
    """统一写入 HTMX 刷新和事件头。"""

    response.headers["HX-Retarget"] = target
    response.headers["HX-Reswap"] = reswap
    if trigger is not None:
        response.headers["HX-Trigger"] = json.dumps(trigger, ensure_ascii=True)
