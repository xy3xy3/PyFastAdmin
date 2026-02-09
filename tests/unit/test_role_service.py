from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import role_service


@pytest.mark.unit
def test_build_default_role_permissions_for_viewer_read_only() -> None:
    permissions = role_service.build_default_role_permissions("viewer")
    mapping = {(item["resource"], item["action"]) for item in permissions}

    assert ("admin_users", "read") in mapping
    assert ("admin_users", "update") not in mapping
    assert ("config", "update") not in mapping


@pytest.mark.unit
def test_build_default_role_permissions_for_super_has_crud() -> None:
    permissions = role_service.build_default_role_permissions("super")
    mapping = {(item["resource"], item["action"]) for item in permissions}

    assert ("rbac", "create") in mapping
    assert ("rbac", "update") in mapping
    assert ("admin_users", "delete") in mapping
    assert ("config", "update") in mapping


@pytest.mark.unit
def test_is_system_role() -> None:
    assert role_service.is_system_role("super") is True
    assert role_service.is_system_role("admin") is True
    assert role_service.is_system_role("viewer") is True
    assert role_service.is_system_role("ops") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_role_in_use(monkeypatch) -> None:
    async def fake_find_one(*_args, **_kwargs):
        return SimpleNamespace(id="x")

    monkeypatch.setattr(role_service.AdminUser, "find_one", fake_find_one)
    assert await role_service.role_in_use("ops") is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_role_not_in_use(monkeypatch) -> None:
    async def fake_find_one(*_args, **_kwargs):
        return None

    monkeypatch.setattr(role_service.AdminUser, "find_one", fake_find_one)
    assert await role_service.role_in_use("ops") is False
