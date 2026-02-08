import pytest

from types import SimpleNamespace

from app.services.log_service import get_request_ip, normalize_log_action


@pytest.mark.unit
def test_normalize_log_action() -> None:
    assert normalize_log_action("CREATE") == "create"
    assert normalize_log_action(" update ") == "update"
    assert normalize_log_action("noop") == ""


@pytest.mark.unit
def test_get_request_ip_prefers_x_forwarded_for() -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "10.10.1.1, 192.168.0.1"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert get_request_ip(request) == "10.10.1.1"


@pytest.mark.unit
def test_get_request_ip_falls_back_to_client_host() -> None:
    request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
    assert get_request_ip(request) == "127.0.0.1"
