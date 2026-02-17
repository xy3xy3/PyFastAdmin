"""多进程启动编排服务。"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import signal
import subprocess
import sys
import time
from typing import Callable

from app.config import (
    APP_PORT,
    HTTP_WORKERS,
    PERIODIC_WORKERS,
    QUEUE_WORKERS,
    UVICORN_HOST,
    UVICORN_LOG_LEVEL,
    UVICORN_RELOAD,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """主控进程运行配置。"""

    http_workers: int
    queue_workers: int
    periodic_workers: int
    app_port: int
    uvicorn_host: str
    uvicorn_log_level: str
    uvicorn_reload: bool


@dataclass(slots=True)
class ManagedProcess:
    """受管进程信息。"""

    name: str
    process: subprocess.Popen[str]


def load_runtime_config() -> RuntimeConfig:
    """从全局配置读取启动参数。"""

    return RuntimeConfig(
        http_workers=max(HTTP_WORKERS, 1),
        queue_workers=max(QUEUE_WORKERS, 0),
        periodic_workers=max(PERIODIC_WORKERS, 0),
        app_port=max(APP_PORT, 1),
        uvicorn_host=UVICORN_HOST,
        uvicorn_log_level=UVICORN_LOG_LEVEL,
        uvicorn_reload=UVICORN_RELOAD,
    )


def build_uvicorn_command(config: RuntimeConfig) -> list[str]:
    """构建 Uvicorn 启动命令。"""

    worker_count = 1 if config.uvicorn_reload else config.http_workers
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        config.uvicorn_host,
        "--port",
        str(config.app_port),
        "--workers",
        str(worker_count),
        "--log-level",
        config.uvicorn_log_level,
    ]
    if config.uvicorn_reload:
        command.append("--reload")
    return command


def build_queue_worker_command() -> list[str]:
    """构建队列 worker 命令。"""

    return [sys.executable, "-m", "app.workers.queue_worker"]


def build_periodic_worker_command() -> list[str]:
    """构建周期 worker 命令。"""

    return [sys.executable, "-m", "app.workers.periodic_worker"]


class ProcessSupervisor:
    """负责拉起并守护 HTTP/异步任务进程。"""

    def __init__(
        self,
        config: RuntimeConfig,
        *,
        popen_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
    ) -> None:
        self.config = config
        self._popen_factory = popen_factory
        self._processes: list[ManagedProcess] = []
        self._shutdown_requested = False
        self._unexpected_exit: tuple[str, int] | None = None

    @property
    def processes(self) -> list[ManagedProcess]:
        """返回当前受管进程列表。"""

        return list(self._processes)

    def _spawn(self, *, name: str, command: list[str], env_overrides: dict[str, str] | None = None) -> None:
        """启动一个子进程并纳入监管。"""

        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)

        logger.info("启动子进程 name=%s cmd=%s", name, " ".join(command))
        process = self._popen_factory(command, env=env, text=True)
        self._processes.append(ManagedProcess(name=name, process=process))

    def start(self) -> None:
        """启动全部目标进程。"""

        self._spawn(name="http", command=build_uvicorn_command(self.config))

        for index in range(self.config.queue_workers):
            worker_id = f"queue-{index}"
            self._spawn(
                name=worker_id,
                command=build_queue_worker_command(),
                env_overrides={
                    "PFA_WORKER_ID": worker_id,
                    "PFA_WORKER_INDEX": str(index),
                    "PFA_WORKER_TOTAL": str(max(self.config.queue_workers, 1)),
                },
            )

        for index in range(self.config.periodic_workers):
            worker_id = f"periodic-{index}"
            self._spawn(
                name=worker_id,
                command=build_periodic_worker_command(),
                env_overrides={
                    "PFA_WORKER_ID": worker_id,
                    "PFA_WORKER_INDEX": str(index),
                    "PFA_WORKER_TOTAL": str(max(self.config.periodic_workers, 1)),
                },
            )

    def _register_signal_handlers(self) -> None:
        """注册终止信号处理。"""

        def _handle_signal(_signum: int, _frame: object) -> None:
            self._shutdown_requested = True

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    def _poll_children(self) -> None:
        """轮询子进程状态，发现异常立即 fail-fast。"""

        for item in self._processes:
            return_code = item.process.poll()
            if return_code is None:
                continue
            if self._shutdown_requested:
                continue
            self._unexpected_exit = (item.name, int(return_code))
            self._shutdown_requested = True
            logger.error("子进程异常退出 name=%s code=%s", item.name, return_code)
            return

    def _terminate_all(self) -> None:
        """优雅终止所有子进程。"""

        for item in self._processes:
            if item.process.poll() is None:
                item.process.terminate()

        deadline = time.time() + 10
        while time.time() < deadline:
            alive = [item for item in self._processes if item.process.poll() is None]
            if not alive:
                return
            time.sleep(0.2)

        for item in self._processes:
            if item.process.poll() is None:
                item.process.kill()

    def run(self) -> int:
        """启动并守护全部进程，返回退出码。"""

        self._register_signal_handlers()
        self.start()

        try:
            while not self._shutdown_requested:
                self._poll_children()
                time.sleep(0.5)
        finally:
            self._terminate_all()

        if self._unexpected_exit is not None:
            name, code = self._unexpected_exit
            logger.error("触发 fail-fast，异常进程=%s code=%s", name, code)
            return 1
        return 0
