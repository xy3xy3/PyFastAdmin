from __future__ import annotations

import pytest

from app.services import config_service, log_service


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_actions_roundtrip(initialized_db) -> None:
    assert await config_service.get_audit_log_actions() == [
        "create",
        "update",
        "delete",
        "trigger",
        "restore",
        "update_self",
    ]

    saved = await config_service.save_audit_log_actions(["restore", "delete", "create", "delete", "update_self", "x"])
    assert saved == ["create", "delete", "restore", "update_self"]
    assert await config_service.get_audit_log_actions() == ["create", "delete", "restore", "update_self"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_record_action_respects_enabled_types(initialized_db) -> None:
    await config_service.save_audit_log_actions(["create"])

    created = await log_service.record_action(
        action="create",
        module="admin_users",
        operator="tester",
        target="管理员: e2e",
        target_id="1",
        detail="创建账号",
        method="POST",
        path="/admin/users",
        ip="127.0.0.1",
    )
    updated = await log_service.record_action(
        action="update",
        module="admin_users",
        operator="tester",
        target="管理员: e2e",
        target_id="1",
        detail="更新账号",
        method="POST",
        path="/admin/users/1",
        ip="127.0.0.1",
    )

    assert created is True
    assert updated is False

    logs, total = await log_service.list_logs(
        {
            "search_q": "",
            "search_action": "",
            "search_module": "",
            "search_sort": "created_desc",
        },
        page=1,
        page_size=10,
    )
    assert total == 1
    assert len(logs) == 1
    assert logs[0].action == "create"
    assert logs[0].module == "admin_users"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_record_action_supports_semantic_actions(initialized_db) -> None:
    await config_service.save_audit_log_actions(["trigger", "restore", "update_self"])

    triggered = await log_service.record_action(
        action="trigger",
        module="backup",
        operator="tester",
        target="手动备份",
        target_id="backup-1",
        detail="触发一次备份",
        method="POST",
        path="/admin/backup/trigger",
        ip="127.0.0.1",
    )
    restored = await log_service.record_action(
        action="restore",
        module="backup",
        operator="tester",
        target="恢复备份",
        target_id="backup-1",
        detail="恢复一次备份",
        method="POST",
        path="/admin/backup/backup-1/restore",
        ip="127.0.0.1",
    )
    updated_self = await log_service.record_action(
        action="update_self",
        module="auth",
        operator="tester",
        target="个人资料",
        target_id="admin-1",
        detail="更新个人资料",
        method="POST",
        path="/admin/profile",
        ip="127.0.0.1",
    )
    created = await log_service.record_action(
        action="create",
        module="admin_users",
        operator="tester",
        target="管理员: e2e",
        target_id="1",
        detail="创建账号",
        method="POST",
        path="/admin/users",
        ip="127.0.0.1",
    )

    assert triggered is True
    assert restored is True
    assert updated_self is True
    assert created is False

    logs, total = await log_service.list_logs(
        {
            "search_q": "",
            "search_action": "trigger",
            "search_module": "",
            "search_sort": "created_desc",
        },
        page=1,
        page_size=10,
    )
    assert total == 1
    assert len(logs) == 1
    assert logs[0].action == "trigger"
    assert logs[0].module == "backup"
