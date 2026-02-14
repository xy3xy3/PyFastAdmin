from __future__ import annotations

import json

import pytest

from app.apps.admin import navigation
from app.services import permission_service


@pytest.mark.unit
def test_build_navigation_context_with_read_permissions() -> None:
    permission_map = {
        "dashboard_home": {"read"},
        "rbac": {"read"},
        "admin_users": {"read"},
        "profile": {"read"},
        "password": {"read"},
    }
    flags = permission_service.build_permission_flags(permission_map)

    nav = navigation.build_navigation_context("/admin/users", flags)

    assert nav["home"]["name"] == "仪表盘"
    assert nav["breadcrumb_title"] == "管理员管理"
    assert nav["breadcrumb_parent"] == "权限管理"
    assert any(group["key"] == "security" and group["active"] for group in nav["groups"])


@pytest.mark.unit
def test_build_navigation_context_hides_unread_resources() -> None:
    flags = permission_service.build_permission_flags({})

    nav = navigation.build_navigation_context("/admin/dashboard", flags)

    assert nav["home"] is None
    assert nav["groups"] == []
    assert nav["breadcrumb_title"] == "仪表盘"


@pytest.mark.unit
def test_build_navigation_context_matches_longest_prefix() -> None:
    permission_map = {
        "backup_records": {"read"},
        "backup_config": {"read"},
    }
    flags = permission_service.build_permission_flags(permission_map)

    nav = navigation.build_navigation_context("/admin/backup/trigger", flags)

    assert nav["breadcrumb_title"] == "数据备份"


@pytest.mark.unit
def test_build_admin_nav_tree_supports_generated_override(tmp_path, monkeypatch) -> None:
    payload = {
        "group_key": "security",
        "node": {
            "resource": "admin_users",
            "name": "账号审计",
            "icon": "fa-solid fa-shield",
            "menu_visible": True,
            "match_prefixes": ["/admin/users"],
        },
    }
    (tmp_path / "admin_users.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(navigation, "NAV_GENERATED_DIR", tmp_path)

    tree = navigation.build_admin_nav_tree()
    security_group = next(group for group in tree if group["key"] == "security")

    assert any(item["resource"] == "admin_users" and item["name"] == "账号审计" for item in security_group["items"])
