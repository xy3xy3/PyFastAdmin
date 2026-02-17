from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.unit
def test_queue_consumers_scaffold_files_exist() -> None:
    assert Path("app/models/queue_consumers.py").exists()
    assert Path("app/services/queue_consumers_service.py").exists()
    assert Path("app/apps/admin/controllers/queue_consumers.py").exists()


@pytest.mark.unit
def test_queue_consumers_registry_generated_contains_read_action() -> None:
    payload = json.loads(Path("app/apps/admin/registry_generated/queue_consumers.json").read_text(encoding="utf-8"))

    assert payload["node"]["key"] == "queue_consumers"
    assert payload["node"]["mode"] == "settings"
    assert payload["node"]["actions"] == ["read"]


@pytest.mark.unit
def test_queue_consumers_nav_generated_contains_resource_binding() -> None:
    payload = json.loads(Path("app/apps/admin/nav_generated/queue_consumers.json").read_text(encoding="utf-8"))

    assert payload["group_key"]
    assert payload["node"]["resource"] == "queue_consumers"
    assert payload["node"]["menu_visible"] is True
