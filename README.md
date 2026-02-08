# PyFastAdmin

HTMX + Alpine.js + Tailwind + FastAPI + Jinja2 + Beanie 的不分离管理后台示例。

## 功能
- RBAC 权限管理（增删改查）
- 权限树配置（按页面 URL/名称聚合）
- 管理员管理（创建/编辑/禁用）
- 登录、个人资料、修改密码场景页面
- 系统配置（示例：SMTP）
- 移动端/桌面端响应式布局
- 所有静态资源本地化（HTMX/Alpine/Tailwind 编译产物均为本地）

## 目录结构
- `app/`：FastAPI 应用与模板
- `app/static/`：本地静态资源
- `deploy/dev/`：仅数据库的开发环境
- `deploy/product/`：生产环境 Dockerfile（uv 安装依赖）
- `refs/`：外部仓库参考（已 gitignore）

## 本地运行
1. 准备 MongoDB（开发环境）

```bash
cd deploy/dev
docker compose --env-file ../../.env up -d
```

2. 安装前端依赖并构建 Tailwind

```bash
pnpm install
pnpm build:css
```

3. 使用 uv 创建虚拟环境并同步依赖（Python 3.13）

```bash
uv venv -p 3.13
source .venv/bin/activate
uv sync
```

4. 启动服务

```bash
uv run uvicorn app.main:app --reload --port ${APP_PORT:-8000}
```

访问：http://localhost:8000/admin/rbac
- 权限树配置：http://localhost:8000/admin/rbac/permissions
- 管理员管理：http://localhost:8000/admin/users
- 个人资料：http://localhost:8000/admin/profile
- 修改密码：http://localhost:8000/admin/password
- 系统配置：http://localhost:8000/admin/config

首次启动会自动创建默认管理员（用户名/密码来自 `.env` 的 `ADMIN_USER`、`ADMIN_PASS`）。

## 生产部署（含 uv Dockerfile）

```bash
cd deploy/product
docker compose --env-file ../../.env up -d --build
```

## 环境变量
参考 `.env.example`，重点变量：
- `APP_PORT`：应用端口
- `MONGO_URL`：MongoDB 连接串
- `MONGO_DB`：数据库名称
- `MONGO_PORT`：MongoDB 容器映射端口
- `SECRET_KEY`：Session 加密密钥
- `ADMIN_USER`：默认管理员账号
- `ADMIN_PASS`：默认管理员密码

## 依赖管理（uv）
- 新增依赖：`uv add 包名`
- 同步依赖：`uv sync`
