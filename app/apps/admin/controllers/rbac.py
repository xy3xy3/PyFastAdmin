"""Admin RBAC 控制器。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

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
    roles = await role_service.list_roles()
    stats = {
        "total": len(roles),
        "enabled": sum(1 for item in roles if item.status == "enabled"),
        "disabled": sum(1 for item in roles if item.status == "disabled"),
        "latest": fmt_dt(roles[0].updated_at) if roles else None,
    }
    context = {
        **base_context(request),
        "roles": roles,
        "stats": stats,
        "status_meta": STATUS_META,
        "action_labels": ACTION_LABELS,
    }
    return templates.TemplateResponse("pages/rbac.html", context)


@router.get("/rbac/roles/table", response_class=HTMLResponse)
async def role_table(request: Request) -> HTMLResponse:
    roles = await role_service.list_roles()
    context = {**base_context(request), "roles": roles, "status_meta": STATUS_META}
    return templates.TemplateResponse("partials/role_table.html", context)


@router.get("/rbac/roles/new", response_class=HTMLResponse)
async def role_new(request: Request) -> HTMLResponse:
    form = build_role_form({})
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
    }
    return templates.TemplateResponse("partials/role_form.html", context)


@router.post("/rbac/roles", response_class=HTMLResponse)
async def role_create(
    request: Request,
) -> HTMLResponse:
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
        }
        return templates.TemplateResponse("partials/role_form.html", context, status_code=422)

    owner = request.session.get("admin_name") or "system"
    form["permissions"] = build_permissions(form_data, owner)
    await role_service.create_role(form)
    roles = await role_service.list_roles()
    context = {**base_context(request), "roles": roles, "status_meta": STATUS_META}
    response = templates.TemplateResponse("partials/role_table.html", context)
    response.headers["HX-Trigger"] = (
        '{"rbac-toast": {"title": "已创建", "message": "角色已保存"}, "rbac-close": true}'
    )
    return response


@router.post("/rbac/roles/{slug}", response_class=HTMLResponse)
async def role_update(
    request: Request,
    slug: str,
) -> HTMLResponse:
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
        }
        return templates.TemplateResponse("partials/role_form.html", context, status_code=422)

    owner = request.session.get("admin_name") or "system"
    form["permissions"] = build_permissions(form_data, owner)
    await role_service.update_role(role, form)
    roles = await role_service.list_roles()
    context = {**base_context(request), "roles": roles, "status_meta": STATUS_META}
    response = templates.TemplateResponse("partials/role_table.html", context)
    response.headers["HX-Trigger"] = (
        '{"rbac-toast": {"title": "已更新", "message": "角色已修改"}, "rbac-close": true}'
    )
    return response


@router.delete("/rbac/roles/{slug}", response_class=HTMLResponse)
async def role_delete(request: Request, slug: str) -> HTMLResponse:
    role = await role_service.get_role_by_slug(slug)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    await role_service.delete_role(role)
    roles = await role_service.list_roles()
    context = {**base_context(request), "roles": roles, "status_meta": STATUS_META}
    response = templates.TemplateResponse("partials/role_table.html", context)
    response.headers["HX-Trigger"] = (
        '{"rbac-toast": {"title": "已删除", "message": "角色已移除"}}'
    )
    return response
