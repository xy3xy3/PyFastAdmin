from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import Callable, cast

import pytest

from app.services.process_supervisor import ManagedProcess, ProcessSupervisor, RuntimeConfig, build_uvicorn_command


@dataclass
class FakeProcess:
    poll_result: int | None = None

    def poll(self) -> int | None:
        return self.poll_result

    def terminate(self) -> None:
        return None

    def kill(self) -> None:
        return None


class FakePopenFactory:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **_kwargs: object) -> FakeProcess:
        self.commands.append(command)
        return FakeProcess(poll_result=None)


@pytest.mark.unit
def test_build_uvicorn_command_contains_workers_and_port() -> None:
    command = build_uvicorn_command(
        RuntimeConfig(
            http_workers=3,
            queue_workers=1,
            periodic_workers=1,
            app_port=9000,
            uvicorn_host="127.0.0.1",
            uvicorn_log_level="debug",
            uvicorn_reload=False,
        )
    )

    assert "--workers" in command
    assert "3" in command
    assert "--port" in command
    assert "9000" in command


@pytest.mark.unit
def test_supervisor_start_spawns_http_queue_periodic_processes() -> None:
    popen = FakePopenFactory()
    supervisor = ProcessSupervisor(
        RuntimeConfig(
            http_workers=2,
            queue_workers=2,
            periodic_workers=1,
            app_port=8000,
            uvicorn_host="0.0.0.0",
            uvicorn_log_level="info",
            uvicorn_reload=False,
        ),
        popen_factory=cast(Callable[..., subprocess.Popen[str]], popen),
    )

    supervisor.start()

    assert len(popen.commands) == 4


@pytest.mark.unit
def test_supervisor_poll_children_fail_fast_on_unexpected_exit() -> None:
    supervisor = ProcessSupervisor(
        RuntimeConfig(
            http_workers=1,
            queue_workers=0,
            periodic_workers=0,
            app_port=8000,
            uvicorn_host="0.0.0.0",
            uvicorn_log_level="info",
            uvicorn_reload=False,
        )
    )

    supervisor._processes = [
        ManagedProcess(name="http", process=cast(subprocess.Popen[str], FakeProcess(poll_result=2))),
    ]
    supervisor._poll_children()

    assert supervisor._shutdown_requested is True
    assert supervisor._unexpected_exit == ("http", 2)
