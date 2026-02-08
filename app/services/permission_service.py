"""权限解析与鉴权服务。"""

from __future__ import annotations

import re
from typing import Any

from starlette.requests import Request

from app.apps.admin.registry import ADMIN_TREE, iter_leaf_nodes
from app.services import auth_service, role_service

_RESOURCE_ACTIONS: dict[str, set[str]] = {
    node["key"]: set(node.get("actions", []))
    for node in iter_leaf_nodes(ADMIN_TREE)
}


def _read_only_permissions() -> dict[str, set[str]]:
    permission_map: dict[str, set[str]] = {}
    for resource, actions in _RESOURCE_ACTIONS.items():
        if "read" in actions:
            permission_map[resource] = {"read"}
    return permission_map


FULL_PERMISSION_MAP: dict[str, set[str]] = {
    resource: set(actions) for resource, actions in _RESOURCE_ACTIONS.items()
}
READ_ONLY_PERMISSION_MAP: dict[str, set[str]] = _read_only_permissions()


def _normalize_permission_items(items: list[Any] | None) -> dict[str, set[str]]:
    permission_map: dict[str, set[str]] = {}
    for item in items or []:
        resource = getattr(item, "resource", None) or (item.get("resource") if isinstance(item, dict) else None)
        action = getattr(item, "action", None) or (item.get("action") if isinstance(item, dict) else None)
        status = getattr(item, "status", None) or (item.get("status") if isinstance(item, dict) else None)

        if status and status != "enabled":
            continue
        if not resource or not action:
            continue
        if action not in _RESOURCE_ACTIONS.get(resource, set()):
            continue
        permission_map.setdefault(resource, set()).add(action)
    return permission_map


def default_permission_map(role_slug: str) -> dict[str, set[str]]:
    """默认角色兜底权限。"""
    if role_slug in {"super", "admin"}:
        return {resource: set(actions) for resource, actions in FULL_PERMISSION_MAP.items()}
    if role_slug == "viewer":
        return {resource: set(actions) for resource, actions in READ_ONLY_PERMISSION_MAP.items()}
    return {}


async def resolve_permission_map(request: Request) -> dict[str, set[str]]:
    """解析当前登录账号的权限并缓存到 request.state。"""

    cached = getattr(request.state, "permission_map", None)
    if cached is not None:
        return cached

    admin = await auth_service.get_admin_by_id(request.session.get("admin_id"))
    request.state.current_admin_model = admin
    if not admin or admin.status != "enabled":
        request.state.permission_map = {}
        request.state.permission_flags = build_permission_flags({})
        return {}

    role = await role_service.get_role_by_slug(admin.role_slug)
    request.state.current_role_model = role

    if role and role.status != "enabled":
        request.state.permission_map = {}
        request.state.permission_flags = build_permission_flags({})
        return {}

    if role:
        permission_map = _normalize_permission_items(role.permissions)
    else:
        permission_map = default_permission_map(admin.role_slug)

    request.state.permission_map = permission_map
    request.state.permission_flags = build_permission_flags(permission_map)
    return permission_map


def can(permission_map: dict[str, set[str]], resource: str, action: str) -> bool:
    return action in permission_map.get(resource, set())


def build_resource_flags(permission_map: dict[str, set[str]], resource: str) -> dict[str, bool]:
    return {
        "create": can(permission_map, resource, "create"),
        "read": can(permission_map, resource, "read"),
        "update": can(permission_map, resource, "update"),
        "delete": can(permission_map, resource, "delete"),
    }


def build_permission_flags(permission_map: dict[str, set[str]]) -> dict[str, Any]:
    flags = {
        "dashboard": build_resource_flags(permission_map, "dashboard_home"),
        "rbac": build_resource_flags(permission_map, "rbac"),
        "admin_users": build_resource_flags(permission_map, "admin_users"),
        "profile": build_resource_flags(permission_map, "profile"),
        "password": build_resource_flags(permission_map, "password"),
        "config": build_resource_flags(permission_map, "config"),
        "operation_logs": build_resource_flags(permission_map, "operation_logs"),
    }
    flags["menus"] = {
        "security": flags["rbac"]["read"] or flags["admin_users"]["read"],
        "system": flags["config"]["read"] or flags["operation_logs"]["read"],
        "profile": flags["profile"]["read"] or flags["password"]["read"],
    }
    return flags


def required_permission(path: str, method: str) -> tuple[str, str] | None:
    """将请求路径映射到资源与动作。"""

    if method == "GET":
        if path in {"/admin", "/admin/dashboard"}:
            return ("dashboard_home", "read")
        if path in {"/admin/rbac", "/admin/rbac/roles/table"}:
            return ("rbac", "read")
        if path == "/admin/rbac/roles/new":
            return ("rbac", "create")
        if re.fullmatch(r"/admin/rbac/roles/[^/]+/edit", path):
            return ("rbac", "update")
        if path in {"/admin/users", "/admin/users/table"}:
            return ("admin_users", "read")
        if path == "/admin/users/new":
            return ("admin_users", "create")
        if re.fullmatch(r"/admin/users/[^/]+/edit", path):
            return ("admin_users", "update")
        if path == "/admin/profile":
            return ("profile", "read")
        if path == "/admin/password":
            return ("password", "read")
        if path == "/admin/config":
            return ("config", "read")
        if path in {"/admin/logs", "/admin/logs/table"}:
            return ("operation_logs", "read")

    if method == "POST":
        if path == "/admin/rbac/roles":
            return ("rbac", "create")
        if re.fullmatch(r"/admin/rbac/roles/[^/]+", path):
            return ("rbac", "update")
        if path == "/admin/users":
            return ("admin_users", "create")
        if re.fullmatch(r"/admin/users/[^/]+", path):
            return ("admin_users", "update")
        if path == "/admin/profile":
            return ("profile", "update")
        if path == "/admin/password":
            return ("password", "update")
        if path == "/admin/config":
            return ("config", "update")

    if method == "DELETE":
        if re.fullmatch(r"/admin/rbac/roles/[^/]+", path):
            return ("rbac", "delete")
        if re.fullmatch(r"/admin/users/[^/]+", path):
            return ("admin_users", "delete")

    return None
