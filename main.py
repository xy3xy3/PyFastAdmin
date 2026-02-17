"""项目主启动入口（统一编排 HTTP 与异步任务进程）。"""

from __future__ import annotations

import logging

from app.services.process_supervisor import ProcessSupervisor, load_runtime_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    """启动主控进程。"""

    config = load_runtime_config()
    logger.info(
        "启动参数: http_workers=%d queue_workers=%d periodic_workers=%d port=%d",
        config.http_workers,
        config.queue_workers,
        config.periodic_workers,
        config.app_port,
    )

    supervisor = ProcessSupervisor(config)
    return supervisor.run()


if __name__ == "__main__":
    raise SystemExit(main())
