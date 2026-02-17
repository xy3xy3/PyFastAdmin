"""周期任务工作进程入口。"""

from __future__ import annotations

import asyncio
import logging

from app.db import close_db, init_db
from app.services.redis_service import close_redis
from app.services.periodic_service import read_worker_identity_from_env, run_periodic_worker
from app.tasks import load_builtin_tasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def _main() -> int:
    """运行周期任务 worker。"""

    await init_db()
    try:
        load_builtin_tasks()
        worker_id, worker_index, worker_total = read_worker_identity_from_env()
        logger.info(
            "启动周期任务 worker id=%s index=%d total=%d",
            worker_id,
            worker_index,
            worker_total,
        )
        await run_periodic_worker(worker_id=worker_id, worker_index=worker_index, worker_total=worker_total)
    finally:
        await close_redis()
        await close_db()
    return 0


def main() -> int:
    """周期任务 worker 同步入口。"""

    try:
        return asyncio.run(_main())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
