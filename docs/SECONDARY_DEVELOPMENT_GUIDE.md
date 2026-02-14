# PyFastAdmin 二开指南（9 步）

> 目标：让业务项目在保留原有 RBAC / HTMX / 审计能力的前提下，快速迁移和扩展模块。

## 1) 注册资源
- 在 `app/apps/admin/registry.py` 的基础树新增资源，或在 `app/apps/admin/registry_generated/*.json` 追加节点。
- CRUD 脚手架生成后会自动产出 `app/apps/admin/registry_generated/<module>.json`，请优先检查该文件的 `group_key/key/url/mode/actions` 是否符合业务。
- 脚手架也会同步生成 `app/apps/admin/nav_generated/<module>.json`，用于菜单图标/别名/匹配前缀扩展。
- 每个资源必须声明 `key/name/url/actions`，`actions` 建议固定为 `create/read/update/delete`。
- 新增后请确认 `permission_service.build_permission_flags` 能自动识别到资源。
- 若需把资源挂到已有权限分组，`group_key` 使用 `security`、`accounts`、`system` 之一；若使用新 key，会在权限树里生成新分组（分组名默认等于 key，必要时到 `app/apps/admin/registry.py` 的 `BASE_ADMIN_TREE` 手动补中文名和排序）。

## 2) 自动注入侧边菜单与面包屑
- 导航由 `app/apps/admin/navigation.py` 统一构建，默认从 `registry.py + registry_generated/*.json` 自动推导。
- 脚手架产物 `app/apps/admin/nav_generated/<module>.json` 会自动注入左侧菜单、折叠菜单和顶部面包屑，不需要再改 `base.html`。
- 菜单显隐按资源 `read` 动作自动控制；无 `read` 时菜单必须隐藏。
- 需要个性化时优先改 `nav_generated/<module>.json`（图标、名称、匹配前缀），而不是散改模板。

## 3) 新增路由
- 控制器放在 `app/apps/admin/controllers/`，路由统一 `prefix="/admin"`。
- 推荐使用显式权限声明：`@permission_decorator.permission_meta("resource", "action")`。
- 约定式推断仍可用，但只作为兜底，复杂路由（批量、导入导出）必须显式声明。

## 4) 模板按钮权限控制
- 模板中权限字典必须使用下标：`perm['create']`、`perm['update']`、`perm['delete']`。
- 无 `create` 不显示“新建”；无 `update` 不显示“编辑”；无 `delete` 不显示“删除”。
- `update` 和 `delete` 都没有时，整列“操作”不显示。

## 5) 后端鉴权
- 所有增删改接口必须被 `AdminAuthMiddleware` + `permission_service.required_permission` 拦截。
- 若是非常规路径，务必加显式权限声明，避免推断误判。
- 人工验证：直接构造请求访问无权限接口，必须返回 `403`。

## 6) 操作日志
- 页面访问与 CRUD 都应调用 `log_service.record_request(...)`。
- 最少包含：`action/module/target/detail`。
- 导入导出、密码修改、个人资料、登录登出等关键动作也要落日志。

## 7) 测试补齐
- 单测优先覆盖：权限映射、read 依赖约束、字段校验、导入导出数据清洗。
- 建议位置：`tests/unit`；跨模块流程可补 `tests/integration` / `tests/e2e`。
- 至少保证新增模块脚手架生成文件通过 `compileall` 与 `pytest -m unit`。

## 8) 响应式检查
- 页面和表格都需同时检查手机宽度与桌面宽度。
- 宽表必须包裹 `overflow-x-auto`，避免移动端撑爆。
- modal 表单与列表刷新需保持 HTMX 交互一致。

## 9) 交付前自检
- `uv run pytest -m unit`
- `uv run python -m compileall app tests`
- 若修改 Tailwind 源样式：`pnpm build:css`
- 权限场景人工回归：按钮隐藏 + 接口 403 + 日志可追踪。

---

## 附：推荐命令
- 生成模块脚手架：
  - `uv run python scripts/generate_admin_module.py inventory --name "库存管理" --group system`
- 导出角色权限 JSON：
  - `GET /admin/rbac/roles/export?include_system=1`
- 导入角色权限 JSON：
  - 页面按钮打开弹窗后粘贴 JSON 提交。
