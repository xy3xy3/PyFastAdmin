from __future__ import annotations

import re
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute

from app.main import app
from app.services import permission_service


@pytest.mark.unit
def test_required_permission_route_mapping() -> None:
    assert permission_service.required_permission("/admin/users", "GET") == ("admin_users", "read")
    assert permission_service.required_permission("/admin/users/507f1f77bcf86cd799439011", "POST") == (
        "admin_users",
        "update",
    )
    assert permission_service.required_permission("/admin/rbac/roles/viewer", "DELETE") == ("rbac", "delete")
    assert permission_service.required_permission("/admin/unknown", "GET") is None


@pytest.mark.unit
def test_required_permission_covers_all_admin_routes() -> None:
    exempt_paths = {"/admin/login", "/admin/logout"}

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/admin"):
            continue
        if route.path in exempt_paths:
            continue

        concrete_path = re.sub(r"\{[^/]+\}", "demo", route.path)
        methods = {method for method in (route.methods or set()) if method in {"GET", "POST", "DELETE"}}
        for method in methods:
            assert permission_service.required_permission(concrete_path, method) is not None, (
                f"未配置权限映射: {method} {route.path}"
            )


@pytest.mark.unit
def test_build_permission_flags_contains_menu_switches() -> None:
    permission_map = {
        "dashboard_home": {"read"},
        "rbac": {"read"},
        "profile": {"read"},
    }

    flags = permission_service.build_permission_flags(permission_map)

    assert flags["dashboard"]["read"] is True
    assert flags["rbac"]["read"] is True
    assert flags["admin_users"]["read"] is False
    assert flags["menus"]["security"] is True
    assert flags["menus"]["system"] is False
    assert flags["menus"]["profile"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_permission_map_uses_role_permissions_without_slug_special_case(monkeypatch) -> None:
    request = SimpleNamespace(session={"admin_id": "abc"}, state=SimpleNamespace())

    admin = SimpleNamespace(status="enabled", role_slug="viewer")
    role = SimpleNamespace(
        status="enabled",
        permissions=[
            {"resource": "admin_users", "action": "read", "status": "enabled"},
            {"resource": "admin_users", "action": "update", "status": "enabled"},
            {"resource": "config", "action": "read", "status": "enabled"},
            {"resource": "config", "action": "invalid", "status": "enabled"},
        ],
    )

    async def fake_get_admin_by_id(_admin_id: str):
        return admin

    async def fake_get_role_by_slug(_role_slug: str):
        return role

    monkeypatch.setattr(permission_service.auth_service, "get_admin_by_id", fake_get_admin_by_id)
    monkeypatch.setattr(permission_service.role_service, "get_role_by_slug", fake_get_role_by_slug)

    permission_map = await permission_service.resolve_permission_map(request)

    assert permission_map == {
        "admin_users": {"read", "update"},
        "config": {"read"},
    }
    assert request.state.permission_flags["admin_users"]["update"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_permission_map_requires_read_for_mutating_actions(monkeypatch) -> None:
    request = SimpleNamespace(session={"admin_id": "abc"}, state=SimpleNamespace())

    admin = SimpleNamespace(status="enabled", role_slug="admin")
    role = SimpleNamespace(
        status="enabled",
        permissions=[
            {"resource": "admin_users", "action": "update", "status": "enabled"},
        ],
    )

    async def fake_get_admin_by_id(_admin_id: str):
        return admin

    async def fake_get_role_by_slug(_role_slug: str):
        return role

    monkeypatch.setattr(permission_service.auth_service, "get_admin_by_id", fake_get_admin_by_id)
    monkeypatch.setattr(permission_service.role_service, "get_role_by_slug", fake_get_role_by_slug)

    permission_map = await permission_service.resolve_permission_map(request)

    assert permission_map == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_permission_map_returns_empty_when_role_missing(monkeypatch) -> None:
    request = SimpleNamespace(session={"admin_id": "abc"}, state=SimpleNamespace())

    admin = SimpleNamespace(status="enabled", role_slug="viewer")

    async def fake_get_admin_by_id(_admin_id: str):
        return admin

    async def fake_get_role_by_slug(_role_slug: str):
        return None

    monkeypatch.setattr(permission_service.auth_service, "get_admin_by_id", fake_get_admin_by_id)
    monkeypatch.setattr(permission_service.role_service, "get_role_by_slug", fake_get_role_by_slug)

    permission_map = await permission_service.resolve_permission_map(request)

    assert permission_map == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_permission_map_returns_empty_for_disabled_role(monkeypatch) -> None:
    request = SimpleNamespace(session={"admin_id": "abc"}, state=SimpleNamespace())

    admin = SimpleNamespace(status="enabled", role_slug="viewer")
    role = SimpleNamespace(status="disabled", permissions=[])

    async def fake_get_admin_by_id(_admin_id: str):
        return admin

    async def fake_get_role_by_slug(_role_slug: str):
        return role

    monkeypatch.setattr(permission_service.auth_service, "get_admin_by_id", fake_get_admin_by_id)
    monkeypatch.setattr(permission_service.role_service, "get_role_by_slug", fake_get_role_by_slug)

    permission_map = await permission_service.resolve_permission_map(request)

    assert permission_map == {}
