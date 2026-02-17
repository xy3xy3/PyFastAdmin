"""E2E 测试 fixture。"""

from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterator
from uuid import uuid4

import httpx
import pytest
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from redis import Redis

ROOT_DIR = Path(__file__).resolve().parents[2]
E2E_COMPOSE_FILE = ROOT_DIR / "deploy" / "e2e" / "docker-compose.yml"


@dataclass(frozen=True)
class E2EDatabaseRuntime:
    """E2E 独立数据库运行时信息。"""

    project_name: str
    env_file: Path
    mongo_url: str
    redis_url: str


def _find_free_port() -> int:
    """查找一个本机可用端口。"""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _run_command(command: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    """执行命令并返回结果。"""

    result = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(
            "命令执行失败:\n"
            f"cmd={' '.join(command)}\n"
            f"code={result.returncode}\n"
            f"stdout={result.stdout[-1200:]}\n"
            f"stderr={result.stderr[-1200:]}"
        )
    return result


def _resolve_compose_port(
    command_base: list[str],
    service_name: str,
    container_port: int,
) -> int:
    """解析 compose 发布到宿主机的端口。"""

    result = _run_command([*command_base, "port", service_name, str(container_port)], cwd=ROOT_DIR)
    raw = result.stdout.strip().splitlines()
    if not raw:
        raise RuntimeError(f"无法解析 {service_name} 端口映射")

    first = raw[0].strip()
    if ":" not in first:
        raise RuntimeError(f"{service_name} 端口映射格式非法: {first}")

    try:
        return int(first.rsplit(":", 1)[1])
    except ValueError as exc:
        raise RuntimeError(f"{service_name} 端口映射解析失败: {first}") from exc


def _wait_mongo_ready(mongo_url: str, timeout: float = 180.0) -> None:
    """等待 MongoDB 就绪。"""

    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        client = MongoClient(
            mongo_url,
            serverSelectionTimeoutMS=1500,
            connectTimeoutMS=1500,
        )
        try:
            client.admin.command("ping")
            return
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
        finally:
            client.close()
    if last_error is None:
        raise RuntimeError("MongoDB 在超时时间内未就绪")
    raise RuntimeError(f"MongoDB 在超时时间内未就绪: {last_error}")


def _wait_redis_ready(redis_url: str, timeout: float = 120.0) -> None:
    """等待 Redis 就绪。"""

    deadline = time.time() + timeout
    while time.time() < deadline:
        client = Redis.from_url(redis_url)
        try:
            if bool(client.ping()):
                return
        except Exception:
            time.sleep(0.5)
        finally:
            client.close()
    raise RuntimeError("Redis 在超时时间内未就绪")


def _wait_server_ready(base_url: str, timeout: float = 30.0) -> None:
    """等待应用 HTTP 服务就绪。"""

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/admin/login", timeout=2.0)
            if response.status_code < 500:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Server did not start in time: {base_url}")


def _terminate_process(process: subprocess.Popen[str]) -> tuple[str, str]:
    """终止子进程并返回输出。"""

    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    stdout = process.stdout.read().strip() if process.stdout else ""
    stderr = process.stderr.read().strip() if process.stderr else ""
    return stdout, stderr


def _start_e2e_databases() -> E2EDatabaseRuntime:
    """启动 E2E 独立 MongoDB + Redis。"""

    if not E2E_COMPOSE_FILE.exists():
        raise RuntimeError(f"E2E compose 文件不存在: {E2E_COMPOSE_FILE}")

    if shutil.which("docker") is None:
        pytest.skip("未安装 docker，无法自动启动 E2E 独立数据库")

    try:
        _run_command(["docker", "compose", "version"], cwd=ROOT_DIR)
    except Exception as exc:
        pytest.skip(f"docker compose 不可用，跳过 E2E: {exc}")

    mongo_user = f"pfa_e2e_{uuid4().hex[:8]}"
    mongo_pass = f"pfa_e2e_{uuid4().hex[:12]}"
    redis_pass = f"pfa_e2e_{uuid4().hex[:12]}"

    project_name = f"pyfastadmin-e2e-{uuid4().hex[:8]}"

    temp_dir = Path(tempfile.mkdtemp(prefix="pfa_e2e_"))
    env_file = temp_dir / "compose.env"
    env_file.write_text(
        "\n".join(
            [
                f"MONGO_ROOT_USERNAME={mongo_user}",
                f"MONGO_ROOT_PASSWORD={mongo_pass}",
                f"REDIS_PASSWORD={redis_pass}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    command_base = [
        "docker",
        "compose",
        "-f",
        str(E2E_COMPOSE_FILE),
        "--env-file",
        str(env_file),
        "--project-name",
        project_name,
    ]

    try:
        _run_command([*command_base, "up", "-d"], cwd=ROOT_DIR)
        mongo_port = _resolve_compose_port(command_base, "mongo", 27017)
        redis_port = _resolve_compose_port(command_base, "redis", 6379)
        mongo_url = (
            f"mongodb://{mongo_user}:{mongo_pass}@127.0.0.1:{mongo_port}/"
            "?authSource=admin&directConnection=true"
        )
        redis_url = f"redis://:{redis_pass}@127.0.0.1:{redis_port}/0"

        _wait_mongo_ready(mongo_url)
        _wait_redis_ready(redis_url)
        return E2EDatabaseRuntime(
            project_name=project_name,
            env_file=env_file,
            mongo_url=mongo_url,
            redis_url=redis_url,
        )
    except Exception as exc:
        ps_result = _run_command([*command_base, "ps", "-a"], cwd=ROOT_DIR, check=False)
        logs = _run_command([*command_base, "logs", "--no-color"], cwd=ROOT_DIR, check=False)
        debug = "\n".join(
            [
                "E2E 数据库启动失败，容器日志如下：",
                ps_result.stdout[-1200:],
                logs.stdout[-3000:],
                logs.stderr[-1200:],
            ]
        )
        _run_command([*command_base, "down", "-v", "--remove-orphans"], cwd=ROOT_DIR, check=False)
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"{exc}\n{debug}") from exc


def _stop_e2e_databases(runtime: E2EDatabaseRuntime) -> None:
    """停止并清理 E2E 独立数据库。"""

    command_base = [
        "docker",
        "compose",
        "-f",
        str(E2E_COMPOSE_FILE),
        "--env-file",
        str(runtime.env_file),
        "--project-name",
        runtime.project_name,
    ]
    _run_command([*command_base, "down", "-v", "--remove-orphans"], cwd=ROOT_DIR, check=False)
    shutil.rmtree(runtime.env_file.parent, ignore_errors=True)


@pytest.fixture(scope="session")
def e2e_db_runtime() -> Iterator[E2EDatabaseRuntime]:
    """会话级 E2E 独立数据库生命周期。"""

    runtime = _start_e2e_databases()
    try:
        yield runtime
    finally:
        _stop_e2e_databases(runtime)


@pytest.fixture(scope="session")
def test_mongo_url(e2e_db_runtime: E2EDatabaseRuntime) -> str:
    """覆盖 E2E 场景 MongoDB 连接串。"""

    return e2e_db_runtime.mongo_url


@pytest.fixture(scope="session")
def test_redis_url(e2e_db_runtime: E2EDatabaseRuntime) -> str:
    """提供 E2E 场景 Redis 连接串。"""

    return e2e_db_runtime.redis_url


@pytest.fixture(scope="function")
def e2e_base_url(
    e2e_db_runtime: E2EDatabaseRuntime,
    e2e_mongo_db_name: str,
    test_redis_url: str,
) -> Iterator[str]:
    """启动应用并返回可访问地址。"""

    mongo_client = MongoClient(e2e_db_runtime.mongo_url)
    redis_client = Redis.from_url(test_redis_url)

    try:
        mongo_client.drop_database(e2e_mongo_db_name)
        redis_client.flushdb()
    except PyMongoError as exc:
        pytest.skip(f"E2E MongoDB 不可用: {exc}")
    except Exception as exc:
        pytest.skip(f"E2E Redis 不可用: {exc}")

    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "test",
            "APP_PORT": str(port),
            "MONGO_URL": e2e_db_runtime.mongo_url,
            "MONGO_DB": e2e_mongo_db_name,
            "REDIS_URL": test_redis_url,
            "HTTP_WORKERS": "1",
            "QUEUE_WORKERS": "0",
            "PERIODIC_WORKERS": "0",
            "UVICORN_HOST": "127.0.0.1",
            "ADMIN_USER": os.getenv("TEST_ADMIN_USER", "e2e_admin"),
            "ADMIN_PASS": os.getenv("TEST_ADMIN_PASS", "e2e_pass_123"),
            "SECRET_KEY": os.getenv("TEST_SECRET_KEY", "test-secret-key"),
        }
    )

    process = subprocess.Popen(
        [
            sys.executable,
            "main.py",
        ],
        cwd=str(ROOT_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        try:
            _wait_server_ready(base_url)
        except RuntimeError as exc:
            stdout, stderr = _terminate_process(process)
            debug = "\n".join(part for part in [stdout[-1200:], stderr[-1200:]] if part)
            raise RuntimeError(f"{exc}\n{debug}") from exc

        yield base_url
    finally:
        _terminate_process(process)
        try:
            mongo_client.drop_database(e2e_mongo_db_name)
        except Exception:
            pass
        try:
            redis_client.flushdb()
        except Exception:
            pass
        redis_client.close()
        mongo_client.close()
