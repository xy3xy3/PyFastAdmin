"""Admin RBAC 控制器。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from beanie import PydanticObjectId
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.apps.admin.registry import ADMIN_TREE, iter_leaf_nodes
from app.services import permission_service, role_service

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

PRIORITY_META = {
    1: "低",
    2: "较低",
    3: "常规",
    4: "高",
    5: "紧急",
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


def build_perm_form(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "resource": values.get("resource", ""),
        "action": values.get("action", ""),
        "priority": int(values.get("priority", 3)),
        "status": values.get("status", "enabled"),
        "owner": values.get("owner", ""),
        "tags": values.get("tags", ""),
        "description": values.get("description", ""),
    }


def parse_tags(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def role_errors(values: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if len(values.get("name", "")) < 2:
        errors.append("角色名称至少 2 个字符")
    if len(values.get("slug", "")) < 2:
        errors.append("角色标识至少 2 个字符")
    if values.get("status") not in STATUS_META:
        errors.append("状态不合法")
    return errors


def perm_errors(values: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if len(values.get("resource", "")) < 2:
        errors.append("资源至少 2 个字符")
    if len(values.get("action", "")) < 2:
        errors.append("动作至少 2 个字符")
    if values.get("status") not in STATUS_META:
        errors.append("状态不合法")
    priority = int(values.get("priority", 3))
    if priority not in PRIORITY_META:
        errors.append("优先级不合法")
    return errors


@router.get("/", response_class=HTMLResponse)
async def admin_root() -> RedirectResponse:
    return RedirectResponse(url="/admin/rbac", status_code=302)


@router.get("/rbac", response_class=HTMLResponse)
async def rbac_page(request: Request, role: str | None = None) -> HTMLResponse:
    roles = await role_service.list_roles()
    current_role = role or (roles[0].slug if roles else "")
    permissions = await permission_service.list_permissions(current_role) if current_role else []
    stats = {
        "total": len(permissions),
        "enabled": sum(1 for item in permissions if item.status == "enabled"),
        "disabled": sum(1 for item in permissions if item.status == "disabled"),
        "latest": fmt_dt(permissions[0].updated_at) if permissions else None,
    }
    role_map = {item.slug: item.name for item in roles}
    context = {
        **base_context(request),
        "roles": roles,
        "role_map": role_map,
        "current_role": current_role,
        "items": permissions,
        "stats": stats,
        "status_meta": STATUS_META,
        "priority_meta": PRIORITY_META,
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
    }
    return templates.TemplateResponse("partials/role_form.html", context)


@router.get("/rbac/roles/{slug}/edit", response_class=HTMLResponse)
async def role_edit(request: Request, slug: str) -> HTMLResponse:
    role = await role_service.get_role_by_slug(slug)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

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
    }
    return templates.TemplateResponse("partials/role_form.html", context)


@router.post("/rbac/roles", response_class=HTMLResponse)
async def role_create(
    request: Request,
    name: str = Form(""),
    slug: str = Form(""),
    status: str = Form("enabled"),
    description: str = Form(""),
) -> HTMLResponse:
    form = build_role_form(
        {
            "name": name.strip(),
            "slug": slug.strip(),
            "status": status,
            "description": description.strip(),
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
        }
        return templates.TemplateResponse("partials/role_form.html", context, status_code=422)

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
    name: str = Form(""),
    status: str = Form("enabled"),
    description: str = Form(""),
) -> HTMLResponse:
    role = await role_service.get_role_by_slug(slug)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    form = build_role_form(
        {
            "name": name.strip(),
            "slug": role.slug,
            "status": status,
            "description": description.strip(),
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
        }
        return templates.TemplateResponse("partials/role_form.html", context, status_code=422)

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


@router.get("/rbac/permissions/table", response_class=HTMLResponse)
async def permission_table(request: Request, role: str) -> HTMLResponse:
    items = await permission_service.list_permissions(role)
    context = {
        **base_context(request),
        "items": items,
        "status_meta": STATUS_META,
        "priority_meta": PRIORITY_META,
        "current_role": role,
    }
    return templates.TemplateResponse("partials/rbac_table.html", context)


@router.get("/rbac/permissions/new", response_class=HTMLResponse)
async def permission_new(request: Request, role: str) -> HTMLResponse:
    form = build_perm_form({})
    context = {
        **base_context(request),
        "mode": "create",
        "action": "/admin/rbac/permissions",
        "form": form,
        "role_slug": role,
        "errors": [],
        "status_meta": STATUS_META,
        "priority_meta": PRIORITY_META,
        "tree": ADMIN_TREE,
        "action_labels": ACTION_LABELS,
    }
    return templates.TemplateResponse("partials/rbac_form.html", context)


@router.get("/rbac/permissions/{item_id}/edit", response_class=HTMLResponse)
async def permission_edit(request: Request, item_id: PydanticObjectId) -> HTMLResponse:
    item = await permission_service.get_permission(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="权限不存在")

    form = build_perm_form(
        {
            "resource": item.resource,
            "action": item.action,
            "priority": item.priority,
            "status": item.status,
            "owner": item.owner,
            "tags": ", ".join(item.tags),
            "description": item.description,
        }
    )
    context = {
        **base_context(request),
        "mode": "edit",
        "action": f"/admin/rbac/permissions/{item_id}",
        "form": form,
        "role_slug": item.role_slug,
        "errors": [],
        "status_meta": STATUS_META,
        "priority_meta": PRIORITY_META,
        "tree": ADMIN_TREE,
        "action_labels": ACTION_LABELS,
    }
    return templates.TemplateResponse("partials/rbac_form.html", context)


@router.post("/rbac/permissions", response_class=HTMLResponse)
async def permission_create(
    request: Request,
    role_slug: str = Form(""),
    resource: str = Form(""),
    action: str = Form(""),
    priority: int = Form(3),
    status: str = Form("enabled"),
    owner: str = Form(""),
    tags: str = Form(""),
    description: str = Form(""),
) -> HTMLResponse:
    form = build_perm_form(
        {
            "resource": resource.strip(),
            "action": action.strip(),
            "priority": priority,
            "status": status,
            "owner": owner.strip(),
            "tags": tags,
            "description": description.strip(),
        }
    )
    errors = perm_errors(form)
    if errors:
        context = {
            **base_context(request),
            "mode": "create",
            "action": "/admin/rbac/permissions",
            "form": form,
            "role_slug": role_slug,
            "errors": errors,
            "status_meta": STATUS_META,
            "priority_meta": PRIORITY_META,
            "tree": ADMIN_TREE,
            "action_labels": ACTION_LABELS,
        }
        return templates.TemplateResponse("partials/rbac_form.html", context, status_code=422)

    payload = {
        **form,
        "role_slug": role_slug,
        "tags": parse_tags(form["tags"]),
    }
    await permission_service.create_permission(payload)

    items = await permission_service.list_permissions(role_slug)
    context = {
        **base_context(request),
        "items": items,
        "status_meta": STATUS_META,
        "priority_meta": PRIORITY_META,
        "current_role": role_slug,
    }
    response = templates.TemplateResponse("partials/rbac_table.html", context)
    response.headers["HX-Trigger"] = (
        '{"rbac-toast": {"title": "已创建", "message": "权限已保存"}, "rbac-close": true}'
    )
    return response


@router.post("/rbac/permissions/{item_id}", response_class=HTMLResponse)
async def permission_update(
    request: Request,
    item_id: PydanticObjectId,
    role_slug: str = Form(""),
    resource: str = Form(""),
    action: str = Form(""),
    priority: int = Form(3),
    status: str = Form("enabled"),
    owner: str = Form(""),
    tags: str = Form(""),
    description: str = Form(""),
) -> HTMLResponse:
    item = await permission_service.get_permission(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="权限不存在")

    form = build_perm_form(
        {
            "resource": resource.strip(),
            "action": action.strip(),
            "priority": priority,
            "status": status,
            "owner": owner.strip(),
            "tags": tags,
            "description": description.strip(),
        }
    )
    errors = perm_errors(form)
    if errors:
        context = {
            **base_context(request),
            "mode": "edit",
            "action": f"/admin/rbac/permissions/{item_id}",
            "form": form,
            "role_slug": role_slug,
            "errors": errors,
            "status_meta": STATUS_META,
            "priority_meta": PRIORITY_META,
            "tree": ADMIN_TREE,
            "action_labels": ACTION_LABELS,
        }
        return templates.TemplateResponse("partials/rbac_form.html", context, status_code=422)

    payload = {
        **form,
        "tags": parse_tags(form["tags"]),
    }
    await permission_service.update_permission(item, payload)

    items = await permission_service.list_permissions(role_slug)
    context = {
        **base_context(request),
        "items": items,
        "status_meta": STATUS_META,
        "priority_meta": PRIORITY_META,
        "current_role": role_slug,
    }
    response = templates.TemplateResponse("partials/rbac_table.html", context)
    response.headers["HX-Trigger"] = (
        '{"rbac-toast": {"title": "已更新", "message": "权限已修改"}, "rbac-close": true}'
    )
    return response


@router.delete("/rbac/permissions/{item_id}", response_class=HTMLResponse)
async def permission_delete(request: Request, item_id: PydanticObjectId) -> HTMLResponse:
    item = await permission_service.get_permission(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="权限不存在")

    await permission_service.delete_permission(item)
    items = await permission_service.list_permissions(item.role_slug)
    context = {
        **base_context(request),
        "items": items,
        "status_meta": STATUS_META,
        "priority_meta": PRIORITY_META,
        "current_role": item.role_slug,
    }
    response = templates.TemplateResponse("partials/rbac_table.html", context)
    response.headers["HX-Trigger"] = (
        '{"rbac-toast": {"title": "已删除", "message": "权限已移除"}}'
    )
    return response


@router.get("/rbac/permissions/tree", response_class=HTMLResponse)
async def permission_tree(request: Request, role: str) -> HTMLResponse:
    checked_map = await permission_service.get_role_permissions_map(role)
    context = {
        **base_context(request),
        "tree": ADMIN_TREE,
        "checked_map": checked_map,
        "action_labels": ACTION_LABELS,
        "role_slug": role,
        "saved": False,
    }
    return templates.TemplateResponse("partials/rbac_tree_form.html", context)


@router.post("/rbac/permissions/tree", response_class=HTMLResponse)
async def permission_tree_save(request: Request) -> HTMLResponse:
    form = await request.form()
    role_slug = str(form.get("role_slug", "")).strip()
    if not role_slug:
        context = {
            **base_context(request),
            "tree": ADMIN_TREE,
            "checked_map": {},
            "action_labels": ACTION_LABELS,
            "role_slug": "",
            "saved": False,
            "error": "角色标识不能为空。",
        }
        return templates.TemplateResponse("partials/rbac_tree_form.html", context, status_code=422)

    owner = request.session.get("admin_name") or "system"
    permissions: list[tuple[str, str, str]] = []
    for node in iter_leaf_nodes(ADMIN_TREE):
        actions = form.getlist(f"perm_{node['key']}")
        for action in actions:
            description = f"{node['name']} | {node['url']}"
            permissions.append((node["key"], action, description))

    await permission_service.save_tree_permissions(role_slug, permissions, owner)
    checked_map = await permission_service.get_role_permissions_map(role_slug)
    context = {
        **base_context(request),
        "tree": ADMIN_TREE,
        "checked_map": checked_map,
        "action_labels": ACTION_LABELS,
        "role_slug": role_slug,
        "saved": True,
    }
    return templates.TemplateResponse("partials/rbac_tree_form.html", context)
