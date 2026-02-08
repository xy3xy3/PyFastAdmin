import pytest

from app.services.config_service import normalize_audit_actions


@pytest.mark.unit
def test_normalize_audit_actions_deduplicate_and_sort() -> None:
    values = ["delete", "create", "delete", "read", "unknown", "update"]
    assert normalize_audit_actions(values) == ["create", "read", "update", "delete"]


@pytest.mark.unit
def test_normalize_audit_actions_handles_empty_values() -> None:
    values = ["", "   ", "invalid"]
    assert normalize_audit_actions(values) == []
