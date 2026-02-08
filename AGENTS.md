python环境使用uv run，或者.venv，禁止用python或者python3

node用pnpm，禁止用npm

docker启动mongodb在deploy文件夹

用tailwind+htmx+alphinejs+jinja2开发，css编辑app/static/css/atailwindpp.css，禁止编辑app/static/css/app.css，只能编译生成app.css

新增功能需要考虑RBAC权限控制以及日志记录

权限控制需要对增删改查控制，以及必须选了查才能选增删改，以及增删改的按钮级别需要做隐藏（同时没有改和删的权限则表格中不显示操作列），以及接口要做鉴权

所有页面都要做移动端+PC端双端的响应式适配，可参考个人资料的页面进行适配，不能出现移动端某些页面过宽的问题。

中文回答用户