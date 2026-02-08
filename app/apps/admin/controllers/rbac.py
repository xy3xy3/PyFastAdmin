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
from app.services import rbac_service

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
    "archived": {"label": "归档", "color": "#4a5568"},
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

ROLE_CHOICES = [
    {"key": "super", "name": "超级管理员"},
    {"key": "admin", "name": "管理员"},
    {"key": "viewer", "name": "只读"},
]


def base_context(request: Request) -> dict[str, Any]:
    return {
        "request": request,
        "current_admin": request.session.get("admin_name"),
    }


def build_form_data(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "role_key": values.get("role_key", ""),
        "role_name": values.get("role_name", ""),
        "resource": values.get("resource", ""),
        "action": values.get("action", ""),
        "owner": values.get("owner", ""),
        "priority": int(values.get("priority", 3)),
        "status": values.get("status", "enabled"),
        "tags": values.get("tags", ""),
        "description": values.get("description", ""),
    }


def parse_tags(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def form_errors(values: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if len(values.get("role_key", "")) < 2:
        errors.append("角色标识至少 2 个字符")
    if len(values.get("role_name", "")) < 2:
        errors.append("角色名称至少 2 个字符")
    if len(values.get("resource", "")) < 2:
        errors.append("资源至少 2 个字符")
    if len(values.get("action", "")) < 2:
        errors.append("动作至少 2 个字符")
    if len(values.get("owner", "")) < 2:
        errors.append("负责人至少 2 个字符")
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
async def rbac_page(request: Request) -> HTMLResponse:
    items = await rbac_service.list_policies()
    stats = {
        "total": len(items),
        "enabled": sum(1 for item in items if item.status == "enabled"),
        "disabled": sum(1 for item in items if item.status == "disabled"),
        "archived": sum(1 for item in items if item.status == "archived"),
        "latest": fmt_dt(items[0].updated_at) if items else None,
    }
    context = {
        **base_context(request),
        "items": items,
        "stats": stats,
        "status_meta": STATUS_META,
        "priority_meta": PRIORITY_META,
    }
    return templates.TemplateResponse("pages/rbac.html", context)


@router.get("/rbac/table", response_class=HTMLResponse)
async def rbac_table(request: Request, q: str | None = None) -> HTMLResponse:
    items = await rbac_service.list_policies(q)
    context = {
        **base_context(request),
        "items": items,
        "status_meta": STATUS_META,
        "priority_meta": PRIORITY_META,
    }
    return templates.TemplateResponse("partials/rbac_table.html", context)


@router.get("/rbac/new", response_class=HTMLResponse)
async def rbac_new(request: Request) -> HTMLResponse:
    form = build_form_data({})
    context = {
        **base_context(request),
        "mode": "create",
        "action": "/admin/rbac",
        "form": form,
        "errors": [],
        "status_meta": STATUS_META,
        "priority_meta": PRIORITY_META,
    }
    return templates.TemplateResponse("partials/rbac_form.html", context)


@router.get("/rbac/permissions", response_class=HTMLResponse)
async def rbac_permissions_page(
    request: Request, role_key: str = "admin", role_name: str | None = None
) -> HTMLResponse:
    checked_map = await rbac_service.get_role_permissions_map(role_key)
    display_name = role_name
    if not display_name:
        display_name = next(
            (item["name"] for item in ROLE_CHOICES if item["key"] == role_key),
            role_key,
        )
    context = {
        **base_context(request),
        "tree": ADMIN_TREE,
        "checked_map": checked_map,
        "action_labels": ACTION_LABELS,
        "role_key": role_key,
        "role_name": display_name,
        "role_choices": ROLE_CHOICES,
        "saved": False,
    }
    return templates.TemplateResponse("pages/rbac_permissions.html", context)


@router.post("/rbac/permissions", response_class=HTMLResponse)
async def rbac_permissions_save(request: Request) -> HTMLResponse:
    form = await request.form()
    role_key = str(form.get("role_key", "")).strip()
    role_name = str(form.get("role_name", "")).strip()
    if not role_name:
        role_name = next(
            (item["name"] for item in ROLE_CHOICES if item["key"] == role_key),
            role_key,
        )
    if not role_key:
        checked_map = {}
        context = {
            **base_context(request),
            "tree": ADMIN_TREE,
            "checked_map": checked_map,
            "action_labels": ACTION_LABELS,
            "role_key": "",
            "role_name": "",
            "role_choices": ROLE_CHOICES,
            "saved": False,
            "error": "角色标识不能为空。",
        }
        return templates.TemplateResponse("pages/rbac_permissions.html", context, status_code=422)

    owner = request.session.get("admin_name") or "system"
    permissions: list[tuple[str, str, str]] = []
    for node in iter_leaf_nodes(ADMIN_TREE):
        actions = form.getlist(f"perm_{node['key']}")
        for action in actions:
            description = f"{node['name']} | {node['url']}"
            permissions.append((node["key"], action, description))

    await rbac_service.save_role_permissions(role_key, role_name, owner, permissions)
    checked_map = await rbac_service.get_role_permissions_map(role_key)
    context = {
        **base_context(request),
        "tree": ADMIN_TREE,
        "checked_map": checked_map,
        "action_labels": ACTION_LABELS,
        "role_key": role_key,
        "role_name": role_name,
        "role_choices": ROLE_CHOICES,
        "saved": True,
    }
    return templates.TemplateResponse("pages/rbac_permissions.html", context)


@router.get("/rbac/{item_id}/edit", response_class=HTMLResponse)
async def rbac_edit(request: Request, item_id: PydanticObjectId) -> HTMLResponse:
    item = await rbac_service.get_policy(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")

    form = build_form_data(
        {
            "role_key": item.role_key,
            "role_name": item.role_name,
            "resource": item.resource,
            "action": item.action,
            "owner": item.owner,
            "priority": item.priority,
            "status": item.status,
            "tags": ", ".join(item.tags),
            "description": item.description,
        }
    )
    context = {
        **base_context(request),
        "mode": "edit",
        "action": f"/admin/rbac/{item_id}",
        "form": form,
        "errors": [],
        "status_meta": STATUS_META,
        "priority_meta": PRIORITY_META,
    }
    return templates.TemplateResponse("partials/rbac_form.html", context)


@router.post("/rbac", response_class=HTMLResponse)
async def rbac_create(
    request: Request,
    role_key: str = Form(""),
    role_name: str = Form(""),
    resource: str = Form(""),
    action: str = Form(""),
    owner: str = Form(""),
    priority: int = Form(3),
    status: str = Form("enabled"),
    tags: str = Form(""),
    description: str = Form(""),
) -> HTMLResponse:
    form = build_form_data(
        {
            "role_key": role_key.strip(),
            "role_name": role_name.strip(),
            "resource": resource.strip(),
            "action": action.strip(),
            "owner": owner.strip(),
            "priority": priority,
            "status": status,
            "tags": tags,
            "description": description.strip(),
        }
    )

    errors = form_errors(form)
    if errors:
        context = {
            **base_context(request),
            "mode": "create",
            "action": "/admin/rbac",
            "form": form,
            "errors": errors,
            "status_meta": STATUS_META,
            "priority_meta": PRIORITY_META,
        }
        return templates.TemplateResponse(
            "partials/rbac_form.html", context, status_code=422
        )

    payload = {
        **form,
        "tags": parse_tags(form["tags"]),
    }
    await rbac_service.create_policy(payload)

    items = await rbac_service.list_policies()
    context = {
        **base_context(request),
        "items": items,
        "status_meta": STATUS_META,
        "priority_meta": PRIORITY_META,
    }
    response = templates.TemplateResponse("partials/rbac_table.html", context)
    response.headers["HX-Trigger"] = (
        '{"rbac-toast": {"title": "已创建", "message": "RBAC 权限已保存"}, "rbac-close": true}'
    )
    return response


@router.post("/rbac/{item_id}", response_class=HTMLResponse)
async def rbac_update(
    request: Request,
    item_id: PydanticObjectId,
    role_key: str = Form(""),
    role_name: str = Form(""),
    resource: str = Form(""),
    action: str = Form(""),
    owner: str = Form(""),
    priority: int = Form(3),
    status: str = Form("enabled"),
    tags: str = Form(""),
    description: str = Form(""),
) -> HTMLResponse:
    item = await rbac_service.get_policy(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")

    form = build_form_data(
        {
            "role_key": role_key.strip(),
            "role_name": role_name.strip(),
            "resource": resource.strip(),
            "action": action.strip(),
            "owner": owner.strip(),
            "priority": priority,
            "status": status,
            "tags": tags,
            "description": description.strip(),
        }
    )

    errors = form_errors(form)
    if errors:
        context = {
            **base_context(request),
            "mode": "edit",
            "action": f"/admin/rbac/{item_id}",
            "form": form,
            "errors": errors,
            "status_meta": STATUS_META,
            "priority_meta": PRIORITY_META,
        }
        return templates.TemplateResponse(
            "partials/rbac_form.html", context, status_code=422
        )

    payload = {
        **form,
        "tags": parse_tags(form["tags"]),
    }
    await rbac_service.update_policy(item, payload)

    items = await rbac_service.list_policies()
    context = {
        **base_context(request),
        "items": items,
        "status_meta": STATUS_META,
        "priority_meta": PRIORITY_META,
    }
    response = templates.TemplateResponse("partials/rbac_table.html", context)
    response.headers["HX-Trigger"] = (
        '{"rbac-toast": {"title": "已更新", "message": "RBAC 权限已修改"}, "rbac-close": true}'
    )
    return response


@router.delete("/rbac/{item_id}", response_class=HTMLResponse)
async def rbac_delete(request: Request, item_id: PydanticObjectId) -> HTMLResponse:
    item = await rbac_service.get_policy(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")

    await rbac_service.delete_policy(item)
    items = await rbac_service.list_policies()
    context = {
        **base_context(request),
        "items": items,
        "status_meta": STATUS_META,
        "priority_meta": PRIORITY_META,
    }
    response = templates.TemplateResponse("partials/rbac_table.html", context)
    response.headers["HX-Trigger"] = (
        '{"rbac-toast": {"title": "已删除", "message": "权限已移除"}}'
    )
    return response
