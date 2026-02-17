"""任务模块加载入口。"""

from __future__ import annotations

_loaded = False


def load_builtin_tasks() -> None:
    """加载内置任务定义（幂等）。"""

    global _loaded
    from app.tasks import periodic_builtin, queue_builtin

    # 即使 _loaded 为 True，也继续调用注册函数，确保测试清空注册中心后可自动回填。
    periodic_builtin.register_tasks()
    queue_builtin.register_tasks()
    _loaded = True
