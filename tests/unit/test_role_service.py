from __future__ import annotations

import pytest

from app.services import role_service


@pytest.mark.unit
def test_build_default_role_permissions_for_viewer_read_only() -> None:
    permissions = role_service.build_default_role_permissions('viewer')
    mapping = {(item['resource'], item['action']) for item in permissions}

    assert ('admin_users', 'read') in mapping
    assert ('admin_users', 'update') not in mapping
    assert ('config', 'update') not in mapping


@pytest.mark.unit
def test_build_default_role_permissions_for_super_has_crud() -> None:
    permissions = role_service.build_default_role_permissions('super')
    mapping = {(item['resource'], item['action']) for item in permissions}

    assert ('rbac', 'create') in mapping
    assert ('rbac', 'update') in mapping
    assert ('admin_users', 'delete') in mapping
    assert ('config', 'update') in mapping
