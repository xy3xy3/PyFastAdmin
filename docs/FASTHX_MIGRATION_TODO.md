# PyFastAdmin -> FastHX 渐进迁移 TODO（旧 CRUD 脚手架 + 存量页面）

> 目标：在不破坏 RBAC、HTMX、审计日志与现有 UI 行为的前提下，将旧 `Jinja2Templates.TemplateResponse` 写法平稳迁移到 `fasthx + jinja`。

> 迁移策略：**先改渲染层，不改模板层**。第一阶段仅替换控制器渲染模式，保留 `app/apps/admin/templates/` 现有 Jinja 模板。

---

## 0. 迁移红线（开始前确认）

- [ ] 不改变权限语义：接口鉴权、按钮显隐、操作列显隐规则必须保持一致。
- [ ] 不改变 HTMX 协议：`HX-Retarget` / `HX-Reswap` / `HX-Trigger` 行为保持一致。
- [ ] 不改变错误回显：弹窗 422/200 处理策略保持现状（HTMX 场景优先弹窗内回显）。
- [ ] 不改变审计日志：`log_service.record_request(...)` 的动作和文案不退化。
- [ ] 出现线上风险时可快速回滚到旧 controller 写法（保留迁移前分支/Tag）。

---

## 1. 基线盘点（一次性）

### 1.1 代码盘点

- [ ] 统计所有 `TemplateResponse` 使用点（当前约 47 处）。
- [ ] 统计所有 `HX-*` 响应头设置点（重点是删除/批量删除/弹窗提交）。
- [ ] 统计所有 `_is_htmx_request` 与“HTMX 错误返回”分支。
- [ ] 给页面分级：
  - [ ] A 类（低风险）：纯列表 + table partial（建议 `logs` 先做）
  - [ ] B 类（中风险）：列表 + modal 表单（如 `admin_users`）
  - [ ] C 类（高风险）：权限树/复杂弹窗（如 `rbac`）

### 1.2 回归基线

- [ ] 记录迁移前关键页面截图/录屏（桌面 + 手机）。
- [ ] 记录迁移前关键接口返回（状态码、响应头、HTML 片段结构）。
- [ ] 跑一次基线测试：`uv run pytest -m unit`。

---

## 2. 基础设施改造（先做）

### 2.1 依赖与初始化

- [x] 增加依赖：`uv add fasthx`（已内置 jinja2 的项目仍建议显式确认版本）。
- [ ] 新建统一渲染入口（建议文件：`app/apps/admin/rendering.py`）：
  - [ ] 统一创建 `Jinja2Templates(...)`
  - [ ] 统一创建 `fasthx.jinja.Jinja(...)`
  - [ ] 统一注册模板过滤器（如 `fmt_dt` / `fmt_bytes`）

### 2.2 兼容辅助函数

- [ ] 抽取 `HX-*` 响应头辅助函数（减少每个路由重复拼装）。
- [ ] 抽取“HTMX 弹窗错误返回策略”辅助函数（200/422 策略统一）。
- [ ] 明确装饰器顺序约定（文档化）：
  - [ ] `@router.xxx(...)`
  - [ ] `@permission_meta(...)`
  - [ ] `@jinja.page(...)` 或 `@jinja.hx(...)`

### 2.3 脚手架能力准备（为后续新模块服务）

- [ ] `scripts/generate_admin_module.py` 增加渲染模式参数（建议：`--renderer legacy|fasthx_jinja`）。
- [ ] 新增脚手架模板（controller）支持 `fasthx` 装饰器写法。
- [ ] 默认保留旧模板生成能力，避免一次性切断。

---

## 3. 试点迁移：logs（A 类，低风险）

> 试点文件：`app/apps/admin/controllers/logs.py`

### 3.1 路由迁移

- [x] `GET /logs`：改为 `@jinja.page("pages/logs.html")`。
- [x] `GET /logs/table`：改为 `@jinja.page("partials/logs_table.html")`（保持非 HTMX 也可访问）。
- [x] `DELETE /logs/{log_id}`：改为 `@jinja.hx("partials/logs_table.html", no_data=True)`。
- [x] `POST /logs/bulk-delete`：改为 `@jinja.hx("partials/logs_table.html", no_data=True)`。

### 3.2 行为校验

- [x] 删除/批量删除后 `HX-Retarget/#logs-table` 生效。
- [x] `HX-Trigger` 的 toast 事件仍可触发。
- [x] 非 HTMX 请求访问 `no_data=True` 路由返回 400（符合预期）。
- [ ] 权限不足时后端仍返回 403，前端 toast 仍提示“无权限”。

### 3.3 测试与验收

- [x] 补充/更新 `logs` 相关单测或集成测试。
- [x] 手工回归：筛选、分页、单删、批删、移动端布局。

---

## 4. 扩展迁移顺序（按风险推进）

### 4.1 第二批：admin_users（B 类）

> 目标文件：`app/apps/admin/controllers/admin_users.py`

- [x] 先迁移列表与 table partial 路由，再迁移 create/update/delete。
- [x] 保持弹窗提交失败时“弹窗内回显”行为不变。
- [x] 保持批量删除与“不可删除当前账号”逻辑不变。
- [x] 保持修改当前账号后 session 名称刷新逻辑不变。

### 4.2 第三批：rbac（C 类）

> 目标文件：`app/apps/admin/controllers/rbac.py`

- [x] 分两步迁移：先 table，再 form（new/edit/create/update/delete/import）。
- [x] 重点验证权限树弹窗（宏渲染 + 回填 + read 依赖）行为。
- [x] 重点验证导入/导出与“部分跳过”toast 行为。
- [x] 确保 `permission_meta` 显式声明路由不丢失。

---

## 5. 旧 CRUD 脚手架迁移策略

### 5.1 存量模块迁移模板（建议逐模块复制执行）

- [ ] 复制模块 controller 为迁移分支版本（避免直接大改）。
- [ ] 替换 `TemplateResponse` 返回为“返回 context 对象 + `fasthx` 装饰器渲染”。
- [ ] 保留原模板文件路径与结构（`pages/*.html`、`partials/*.html` 不动）。
- [ ] 每迁移一个模块都进行“权限 + HTMX + 日志 + 响应式”回归。

### 5.2 新模块脚手架切换

- [ ] 新模块默认生成 `fasthx_jinja` 写法（可配置回退 legacy）。
- [ ] 旧模块继续可用，不要求一次性全量改造。
- [ ] 在 `README.md` 增加“新旧脚手架并行策略”说明。

---

## 6. 风险控制与回滚

- [ ] 每个模块独立 PR，禁止跨多个高风险模块混改。
- [ ] 每个模块迁移前打 git tag（或保留可回滚提交）。
- [ ] 若出现行为偏差，优先回滚该模块 controller，不回滚全仓。
- [ ] 保留“legacy controller 模板”直到 2 个版本迭代后再清理。

---

## 7. 验收清单（每个模块迁移后）

### 7.1 必测功能

- [ ] 菜单可见性与 `read` 权限一致。
- [ ] `create/update/delete` 按钮显隐正确。
- [ ] 无 `update+delete` 时操作列隐藏。
- [ ] 强行请求无权限接口返回 403。
- [ ] HTMX 弹窗提交失败在弹窗内回显。
- [ ] 成功后列表刷新 + toast 提示正常。

### 7.2 自动化与静态检查

- [ ] `uv run pytest -m unit`
- [ ] `uv run python -m compileall app tests scripts`
- [ ] 若涉及导入导出：`uv run pytest tests/integration/test_rbac_role_transfer.py -m integration`
- [ ] 若改了样式：`pnpm build:css`

---

## 8. 迁移完成定义（项目级）

- [ ] A/B/C 三类模块各至少完成一个迁移并稳定运行。
- [ ] 脚手架支持新建 `fasthx_jinja` 模块。
- [ ] README/二开文档完成迁移说明。
- [ ] 旧写法仅保留在历史模块，不再作为默认模板。
