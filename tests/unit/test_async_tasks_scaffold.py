from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.unit
def test_async_tasks_scaffold_files_exist() -> None:
    assert Path("app/models/async_tasks.py").exists()
    assert Path("app/services/async_tasks_service.py").exists()
    assert Path("app/apps/admin/controllers/async_tasks.py").exists()


@pytest.mark.unit
def test_async_tasks_registry_generated_contains_read_action() -> None:
    payload = json.loads(Path("app/apps/admin/registry_generated/async_tasks.json").read_text(encoding="utf-8"))

    assert payload["node"]["key"] == "async_tasks"
    assert payload["node"]["mode"] == "settings"
    assert payload["node"]["actions"] == ["read"]


@pytest.mark.unit
def test_async_tasks_nav_generated_contains_resource_binding() -> None:
    payload = json.loads(Path("app/apps/admin/nav_generated/async_tasks.json").read_text(encoding="utf-8"))

    assert payload["group_key"]
    assert payload["node"]["resource"] == "async_tasks"
    assert payload["node"]["menu_visible"] is True
