"""Admin RBAC 控制器。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.apps.admin.registry import ADMIN_TREE, iter_leaf_nodes
from app.services import role_service

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter(prefix="/admin")


def fmt_dt(value: datetime | None) -> str:
    if not value:
        return ""
    if value.tzinfo is None:
        return value.strftime("%Y-%m-%d %H:%M")
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


templates.env.filters["fmt_dt"] = fmt_dt

STATUS_META: dict[str, dict[str, str]] = {
    "enabled": {"label": "启用", "color": "#2f855a"},
    "disabled": {"label": "禁用", "color": "#b7791f"},
}

ROLE_SORT_OPTIONS: dict[str, str] = {
    "updated_desc": "最近更新",
    "updated_asc": "最早更新",
    "slug_asc": "标识 A-Z",
}

ROLE_PAGE_SIZE = 10

ACTION_LABELS = {
    "create": "新增",
    "read": "查看",
    "update": "编辑",
    "delete": "删除",
}


def base_context(request: Request) -> dict[str, Any]:
    return {
        "request": request,
        "current_admin": request.session.get("admin_name"),
    }


def build_role_form(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": values.get("name", ""),
        "slug": values.get("slug", ""),
        "status": values.get("status", "enabled"),
        "description": values.get("description", ""),
    }


def parse_positive_int(value: Any, default: int = 1) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def parse_role_filters(values: Mapping[str, Any]) -> tuple[dict[str, str], int]:
    search_q = str(values.get("search_q") or values.get("q") or "").strip()
    search_status = str(values.get("search_status") or "").strip()
    if search_status not in STATUS_META:
        search_status = ""

    search_sort = str(values.get("search_sort") or "updated_desc").strip()
    if search_sort not in ROLE_SORT_OPTIONS:
        search_sort = "updated_desc"

    page = parse_positive_int(values.get("page"), default=1)
    return (
        {
            "search_q": search_q,
            "search_status": search_status,
            "search_sort": search_sort,
        },
        page,
    )


def build_pagination(total: int, page: int, page_size: int) -> dict[str, Any]:
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


def filter_roles(roles: list[Any], filters: dict[str, str]) -> list[Any]:
    filtered = roles
    if filters["search_q"]:
        keyword = filters["search_q"].lower()
        filtered = [
            item
            for item in filtered
            if keyword in item.slug.lower()
            or keyword in item.name.lower()
            or keyword in (item.description or "").lower()
        ]
    if filters["search_status"]:
        filtered = [item for item in filtered if item.status == filters["search_status"]]

    sort_key = filters["search_sort"]
    if sort_key == "updated_asc":
        filtered = sorted(filtered, key=lambda item: item.updated_at)
    elif sort_key == "slug_asc":
        filtered = sorted(filtered, key=lambda item: item.slug.lower())
    else:
        filtered = sorted(filtered, key=lambda item: item.updated_at, reverse=True)
    return filtered


async def read_request_values(request: Request) -> dict[str, str]:
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


async def build_role_table_context(
    request: Request,
    filters: dict[str, str],
    page: int,
) -> dict[str, Any]:
    roles = await role_service.list_roles()
    filtered_roles = filter_roles(roles, filters)
    pagination = build_pagination(len(filtered_roles), page, ROLE_PAGE_SIZE)
    start = (pagination["page"] - 1) * ROLE_PAGE_SIZE
    paged_roles = filtered_roles[start : start + ROLE_PAGE_SIZE]

    return {
        **base_context(request),
        "roles": paged_roles,
        "status_meta": STATUS_META,
        "filters": filters,
        "pagination": pagination,
    }

def build_checked_map(form_data) -> dict[str, set[str]]:
    checked_map: dict[str, set[str]] = {}
    for node in iter_leaf_nodes(ADMIN_TREE):
        actions = form_data.getlist(f"perm_{node['key']}")
        if actions:
            checked_map[node["key"]] = set(actions)
    return checked_map


def build_permissions(form_data, owner: str) -> list[dict[str, Any]]:
    permissions: list[dict[str, Any]] = []
    for node in iter_leaf_nodes(ADMIN_TREE):
        actions = form_data.getlist(f"perm_{node['key']}")
        for action in actions:
            description = f"{node['name']} | {node['url']}"
            permissions.append(
                {
                    "resource": node["key"],
                    "action": action,
                    "priority": 3,
                    "status": "enabled",
                    "owner": owner,
                    "tags": [],
                    "description": description,
                }
            )
    return permissions


def build_checked_map_from_permissions(permissions: list[Any]) -> dict[str, set[str]]:
    checked_map: dict[str, set[str]] = {}
    for item in permissions:
        resource = getattr(item, "resource", None) or item.get("resource")
        action = getattr(item, "action", None) or item.get("action")
        if not resource or not action:
            continue
        checked_map.setdefault(resource, set()).add(action)
    return checked_map


def role_errors(values: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if len(values.get("name", "")) < 2:
        errors.append("角色名称至少 2 个字符")
    if len(values.get("slug", "")) < 2:
        errors.append("角色标识至少 2 个字符")
    if values.get("status") not in STATUS_META:
        errors.append("状态不合法")
    return errors


@router.get("/", response_class=HTMLResponse)
async def admin_root() -> RedirectResponse:
    return RedirectResponse(url="/admin/rbac", status_code=302)


@router.get("/rbac", response_class=HTMLResponse)
async def rbac_page(request: Request) -> HTMLResponse:
    filters, page = parse_role_filters(request.query_params)
    context = await build_role_table_context(request, filters, page)
    context["action_labels"] = ACTION_LABELS
    context["role_sort_options"] = ROLE_SORT_OPTIONS
    return templates.TemplateResponse("pages/rbac.html", context)


@router.get("/rbac/roles/table", response_class=HTMLResponse)
async def role_table(request: Request) -> HTMLResponse:
    filters, page = parse_role_filters(request.query_params)
    context = await build_role_table_context(request, filters, page)
    return templates.TemplateResponse("partials/role_table.html", context)


@router.get("/rbac/roles/new", response_class=HTMLResponse)
async def role_new(request: Request) -> HTMLResponse:
    form = build_role_form({})
    filters, page = parse_role_filters(request.query_params)
    context = {
        **base_context(request),
        "mode": "create",
        "action": "/admin/rbac/roles",
        "form": form,
        "errors": [],
        "status_meta": STATUS_META,
        "tree": ADMIN_TREE,
        "checked_map": {},
        "action_labels": ACTION_LABELS,
        "filters": filters,
        "page": page,
    }
    return templates.TemplateResponse("partials/role_form.html", context)


@router.get("/rbac/roles/{slug}/edit", response_class=HTMLResponse)
async def role_edit(request: Request, slug: str) -> HTMLResponse:
    role = await role_service.get_role_by_slug(slug)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    checked_map = build_checked_map_from_permissions(role.permissions or [])
    form = build_role_form(
        {
            "name": role.name,
            "slug": role.slug,
            "status": role.status,
            "description": role.description,
        }
    )
    filters, page = parse_role_filters(request.query_params)
    context = {
        **base_context(request),
        "mode": "edit",
        "action": f"/admin/rbac/roles/{slug}",
        "form": form,
        "errors": [],
        "status_meta": STATUS_META,
        "tree": ADMIN_TREE,
        "checked_map": checked_map,
        "action_labels": ACTION_LABELS,
        "filters": filters,
        "page": page,
    }
    return templates.TemplateResponse("partials/role_form.html", context)


@router.post("/rbac/roles", response_class=HTMLResponse)
async def role_create(
    request: Request,
) -> HTMLResponse:
    request_values = await read_request_values(request)
    filters, page = parse_role_filters(request_values)
    form_data = await request.form()
    form = build_role_form(
        {
            "name": str(form_data.get("name", "")).strip(),
            "slug": str(form_data.get("slug", "")).strip(),
            "status": str(form_data.get("status", "enabled")),
            "description": str(form_data.get("description", "")).strip(),
        }
    )
    errors = role_errors(form)
    if await role_service.get_role_by_slug(form["slug"]):
        errors.append("角色标识已存在")
    if errors:
        context = {
            **base_context(request),
            "mode": "create",
            "action": "/admin/rbac/roles",
            "form": form,
            "errors": errors,
            "status_meta": STATUS_META,
            "tree": ADMIN_TREE,
            "checked_map": build_checked_map(form_data),
            "action_labels": ACTION_LABELS,
            "filters": filters,
            "page": page,
        }
        return templates.TemplateResponse("partials/role_form.html", context, status_code=422)

    owner = request.session.get("admin_name") or "system"
    form["permissions"] = build_permissions(form_data, owner)
    await role_service.create_role(form)
    context = await build_role_table_context(request, filters, page)
    response = templates.TemplateResponse("partials/role_table.html", context)
    response.headers["HX-Trigger"] = json.dumps(
        {
            "rbac-toast": {"title": "已创建", "message": "角色已保存", "variant": "success"},
            "rbac-close": True,
        },
        ensure_ascii=True,
    )
    return response


@router.post("/rbac/roles/{slug}", response_class=HTMLResponse)
async def role_update(
    request: Request,
    slug: str,
) -> HTMLResponse:
    request_values = await read_request_values(request)
    filters, page = parse_role_filters(request_values)
    role = await role_service.get_role_by_slug(slug)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    form_data = await request.form()
    form = build_role_form(
        {
            "name": str(form_data.get("name", "")).strip(),
            "slug": role.slug,
            "status": str(form_data.get("status", "enabled")),
            "description": str(form_data.get("description", "")).strip(),
        }
    )
    errors = role_errors(form)
    if errors:
        context = {
            **base_context(request),
            "mode": "edit",
            "action": f"/admin/rbac/roles/{slug}",
            "form": form,
            "errors": errors,
            "status_meta": STATUS_META,
            "tree": ADMIN_TREE,
            "checked_map": build_checked_map(form_data),
            "action_labels": ACTION_LABELS,
            "filters": filters,
            "page": page,
        }
        return templates.TemplateResponse("partials/role_form.html", context, status_code=422)

    owner = request.session.get("admin_name") or "system"
    form["permissions"] = build_permissions(form_data, owner)
    await role_service.update_role(role, form)
    context = await build_role_table_context(request, filters, page)
    response = templates.TemplateResponse("partials/role_table.html", context)
    response.headers["HX-Trigger"] = json.dumps(
        {
            "rbac-toast": {"title": "已更新", "message": "角色已修改", "variant": "success"},
            "rbac-close": True,
        },
        ensure_ascii=True,
    )
    return response


@router.delete("/rbac/roles/{slug}", response_class=HTMLResponse)
async def role_delete(request: Request, slug: str) -> HTMLResponse:
    request_values = await read_request_values(request)
    filters, page = parse_role_filters(request_values)
    role = await role_service.get_role_by_slug(slug)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    await role_service.delete_role(role)
    context = await build_role_table_context(request, filters, page)
    response = templates.TemplateResponse("partials/role_table.html", context)
    response.headers["HX-Trigger"] = json.dumps(
        {"rbac-toast": {"title": "已删除", "message": "角色已移除", "variant": "warning"}},
        ensure_ascii=True,
    )
    return response
