"""应用配置（通过 .env 覆盖）。"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 优先加载项目根目录下的 .env
BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


def _to_int(value: str | None, default: int, *, minimum: int = 0) -> int:
    """安全解析整数环境变量。"""

    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= minimum else default


def _to_bool(value: str | None, default: bool = False) -> bool:
    """安全解析布尔环境变量。"""

    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "on", "yes"}


APP_NAME = os.getenv("APP_NAME", "PyFastAdmin")
APP_ENV = os.getenv("APP_ENV", "dev")

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "pyfastadmin")
MONGO_ROOT_USERNAME = os.getenv("MONGO_ROOT_USERNAME", "")
MONGO_ROOT_PASSWORD = os.getenv("MONGO_ROOT_PASSWORD", "")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

APP_PORT = _to_int(os.getenv("APP_PORT"), 8000, minimum=1)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")

HTTP_WORKERS = _to_int(os.getenv("HTTP_WORKERS"), 1, minimum=1)
QUEUE_WORKERS = _to_int(os.getenv("QUEUE_WORKERS"), 1, minimum=0)
PERIODIC_WORKERS = _to_int(os.getenv("PERIODIC_WORKERS"), 1, minimum=0)

UVICORN_HOST = os.getenv("UVICORN_HOST", "0.0.0.0")
UVICORN_LOG_LEVEL = os.getenv("UVICORN_LOG_LEVEL", "info")
UVICORN_RELOAD = _to_bool(os.getenv("UVICORN_RELOAD"), default=False)

QUEUE_MAX_RETRIES = _to_int(os.getenv("QUEUE_MAX_RETRIES"), 3, minimum=0)
QUEUE_BLOCK_MS = _to_int(os.getenv("QUEUE_BLOCK_MS"), 1500, minimum=100)
LOG_CLEANUP_INTERVAL_SECONDS = _to_int(os.getenv("LOG_CLEANUP_INTERVAL_SECONDS"), 3600, minimum=30)
LOG_RETENTION_DAYS = _to_int(os.getenv("LOG_RETENTION_DAYS"), 30, minimum=1)
WORKER_HEARTBEAT_TTL_SECONDS = _to_int(os.getenv("WORKER_HEARTBEAT_TTL_SECONDS"), 30, minimum=10)
