# AGENTS.md（PyFastAdmin 开发规范）

本文件用于给后续 AI/开发者统一“怎么开发、参考哪里、如何自检”。

## 0. 总原则
- 优先保证：**权限正确 > 接口安全 > UI 一致性 > 代码简洁**。
- 新功能默认要包含：
  1) 页面与按钮权限控制（前端显示层）
  2) 接口鉴权（后端强校验）
  3) 操作日志记录
  4) 移动端 + PC 响应式适配
- 回答用户使用中文。
- 函数必须有中文注释说明用途；复杂逻辑需补充中文注释。

---

## 1. 技术栈与命令约束

### 1.1 Python / 依赖 / 启动
- Python 相关命令必须使用 `uv run` 或 `.venv` 环境。
- 禁止直接使用 `python` / `python3` 裸命令。
- 常用命令：
  - 安装依赖：`uv sync`
  - 启动服务：`uv run uvicorn app.main:app --reload --port ${APP_PORT:-8000}`

### 1.2 Node / Tailwind
- Node 包管理只用 `pnpm`，禁止 `npm`。
- Tailwind 源文件：`app/static/css/tailwind.css`
- 编译产物：`app/static/css/app.css`
- **禁止手改 `app/static/css/app.css`**，只能由构建生成。
- 常用命令：
  - 安装前端依赖：`pnpm install`
  - 构建 CSS：`pnpm build:css`
  - 开发监听：`pnpm dev:css`

### 1.3 MongoDB（开发）
- 开发环境 MongoDB 在 `deploy/dev`。
- 启动：`cd deploy/dev && docker compose --env-file ../../.env up -d`

---

## 2. 目录速查（改动前先定位）
- 后端路由控制器：`app/apps/admin/controllers/`
- 权限资源注册：`app/apps/admin/registry.py`
- 权限解析与鉴权：`app/services/permission_service.py`
- 鉴权中间件：`app/middleware/auth.py`
- 模板：`app/apps/admin/templates/`
  - 页面：`pages/`
  - 表格/弹窗等局部：`partials/`
- 全局前端交互：`app/static/js/app.js`
- 日志服务：`app/services/log_service.py`
- 测试：`tests/unit`、`tests/integration`、`tests/e2e`

---

## 3. RBAC 权限开发硬性规则

### 3.1 CRUD 与依赖关系
- 权限粒度必须支持 `create/read/update/delete`。
- 必须满足依赖：**未勾选 read 时，不允许 create/update/delete 生效**。
- `viewer` 角色默认只读（仅 read）。

### 3.2 前端按钮/列显示规则（必须）
- 无 `create` 权限：隐藏“新建”按钮。
- 无 `update` 权限：隐藏“编辑”按钮。
- 无 `delete` 权限：隐藏“删除”按钮。
- 若同时无 `update` 与 `delete`：**整列“操作”不显示**。

### 3.3 Jinja 权限判断写法（重要）
- 权限对象是字典时，必须使用下标写法：
  - `perm['update']`、`perm['delete']`、`perm['create']`。
- 禁止使用 `perm.update` 这类点写法，避免命中字典方法导致误判（会造成按钮错误显示）。

### 3.4 后端接口鉴权（必须）
- 仅做前端隐藏不够，所有对应接口必须鉴权。
- 新增/修改路由后，务必同步检查：
  - `permission_service.required_permission(...)` 是否已映射到正确 resource/action。
  - `auth.py` 中间件是否能拦截并返回 403。

### 3.5 角色权限保存约束
- 角色保存时需要二次兜底 read 依赖约束。
- 权限解析时也要做约束清洗（防脏数据绕过）。

---

## 4. HTMX + Alpine + Jinja 开发约定
- 列表页采用“页面 + 表格 partial”模式（如 `.../table`）。
- 弹窗表单通过 HTMX 加载到 `#modal-body`。
- 列表筛选/分页刷新时，保持 `hx-vals` 透传当前筛选条件和页码。
- 返回 403 的 HTMX 请求，要由前端统一 toast 反馈（参考 `app/static/js/app.js`）。
- 新增前端交互逻辑优先复用 `app/static/js/app.js`，避免散落内联脚本。

---

## 5. 响应式规范（移动端 + PC）
- 所有新页面必须同时适配移动端和桌面端。
- 可参考：`app/apps/admin/templates/pages/profile.html` 的布局策略。
- 表格页面保持现有表格风格，不强制改卡片风格。
- 宽表必须使用横向滚动容器（如 `overflow-x-auto`），避免移动端撑爆页面。
- 新增 `min-w-*` 时要控制合理宽度，避免小屏过宽。

---

## 6. 操作日志规范
- 关键页面访问与增删改操作需要记录日志。
- 使用 `log_service.record_request(...)`，至少包含：
  - `action`（create/read/update/delete）
  - `module`（如 rbac/admin_users）
  - `target`（操作对象）
  - `detail`（操作描述）

---

## 7. 开发流程（建议 AI 按此执行）
1. 先读本文件和 `README.md`，明确约束与运行方式。
2. 定位涉及模块（controller/service/template/js）。
3. 先补后端鉴权，再做前端按钮显示控制。
4. 完成响应式检查（至少手机宽度与桌面宽度各看一轮）。
5. 补充/更新测试（尤其权限逻辑单测）。
6. 本地自检通过后再交付。

---

## 8. 交付前自检清单（最少）
- 单测：`uv run pytest -m unit`
- 语法检查：`uv run python -m compileall app`
- 若改了 Tailwind：`pnpm build:css`
- 若改了权限：人工确认以下场景
  - 无编辑权限时编辑按钮不显示
  - 无删除权限时删除按钮不显示
  - 无编辑+删除权限时操作列不显示
  - 强行请求接口会被后端 403 拦截

---

## 9. 参考优先级
1. 本文件（AGENTS.md）
2. `README.md`（运行/部署/测试）
3. 现有同类页面实现（优先复用已有模式）
4. 最后才做新的模式设计（避免破坏整体风格）
