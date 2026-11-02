# 贡献指南

## 准备环境

先按 [README](README.md) 安装项目，再安装开发依赖：

```bash
./.venv/bin/python -m pip install -r requirements-dev.txt
npm --prefix frontend ci
npm --prefix desktop ci --ignore-scripts
```

普通检查只需桌面逻辑测试依赖，可跳过安装脚本。需要启动或打包桌面应用时，先运行 `npm --prefix desktop ci` 完整安装桌面依赖。

使用项目 `.venv`、`frontend/node_modules` 和 `desktop/node_modules`，不需要全局安装 Python / npm 包。运行时使用 Python 3.11+；Node.js 22.13+（22.x）或 24+ 可运行前端检查。CI 使用 Node.js 22，Python 3.11 与 3.12。

`requirements.txt` 固定直接运行依赖，`constraints.txt` 约束已核验的间接依赖修补版本，`requirements-dev.txt` 增加测试与静态检查工具；`frontend/package-lock.json` 固定前端依赖解析。安装前端优先用 `npm ci`。Python 约束文件不是全依赖锁，重建环境后应检查实际解析出的版本。

## 检查入口

```bash
make check
```

等价命令：

```bash
./.venv/bin/python -m ruff check .
./.venv/bin/python -m pytest -q
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
node --test desktop/test/*.test.cjs
```

使用已激活的项目环境时，可用 `make check PYTHON=python`。静态检查约束未定义名称、无用导入和 Hooks 使用，不以批量格式化代替问题修复。

### 后端测试

- 使用 pytest 临时目录隔离词库、配置与同步文件。
- HTTP 路由测试使用 `tests.local_client.TestClient`，显式模拟本机连接；不要为了通过测试关闭实际来源校验。
- 模型调用、Drive 网络与授权应使用 mock，不在默认测试中发起真实请求。
- OAuth 回调测试会使用临时本机 HTTP 服务；Google 与所有模型供应商的外部接口仍被模拟。
- 测试配置全局缓存、后台任务或队列时，恢复 monkeypatch 和任务生命周期。
- `tests/test_prompt.py` 默认只做本地检查；`--live` 会调用已配置的模型，可能产生费用，只有手动验证时使用。

```bash
./.venv/bin/python -m pytest tests/test_sync.py -q
./.venv/bin/python -m tests.test_prompt --case coordinated
```

### 前端测试

`npm test` 使用 Node 自带的测试运行器，覆盖可独立验证的 API、SSE 流与洗牌逻辑，不需要额外浏览器测试框架。

修改 Hook 时检查请求取消、迟到响应、轮询重叠、定时器和监听器清理。改动布局或交互时，还需要浏览器检查：窄屏/桌面、深浅色、键盘焦点与减少动态效果。新增视觉行为的截图可放进 PR，无需提交临时截图到仓库。

### 官网构建

官网是 `website/` 下的独立 Vite 项目。修改官网资源后执行 `npm --prefix website run build`；应用前端仍需单独执行 `npm --prefix frontend run build`。构建使用项目现有依赖，首次准备可在 `website/` 执行 `npm ci`。

官网功能介绍、FAQ、页面元信息应与实现保持一致。尚未发布的功能需明确标注版本与源码可用状态；发布成功后再同步官网 `RELEASE_VERSION`、下载链接验收脚本、README 下载入口与更新日志发布日期。桌面及应用前端版本号同时维护各自的 `package.json` 与 `package-lock.json`，官网包版本独立于应用发行版本。

### 桌面版开发与检查

桌面依赖单独位于 `desktop/package.json` 与 `requirements-desktop.txt`，使用项目内的 `.venv-desktop`，不要求修改网页开发环境。

修改桌面代码后，除相关后端回归测试外，运行 `npm --prefix desktop test`；打包前运行前端构建。安装包必须在目标操作系统和架构上构建、启动与退出验证，不能将 macOS 检查结果视为 Windows 验收。自动验证使用临时 `VOCOVE_DESKTOP_USER_DATA_DIR`，不得指向日常桌面数据或仓库真实词库。

`desktop-build.yml` 在推送到 `main` 时运行，也支持手动触发；它生成各平台构建产物，不自动创建 Release 或发布安装包。更改分发或迁移行为时，应单独说明其对本机数据和发布流程的影响。

macOS 更新请求通过 `desktop/lib/electron-update-fetch.cjs` 使用 Electron `net.request`，将重定向交回下载器逐跳校验；不要换回 `net.fetch` 的 `redirect: manual`，该组合会在 GitHub 安装包跳转时报错。下载器保留 HTTPS 官方域名限制、跳转次数上限、文件大小与 SHA256 校验。

更新逻辑测试使用模拟版本源、下载响应、对话框及安装回调，不访问真实词库，也不启动安装程序。源码和冒烟模式不联网检查更新；实际升级链路仍需分别在 Windows 与各 macOS 架构上验收。

## 代码结构与边界

| 模块 | 维护重点 |
| --- | --- |
| `app.py` | 路由校验、HTTP 错误语义、任务启动与退出、应用状态 |
| `config.py` | 校验成功后发布缓存；保存失败不污染现有配置；旧配置兼容与密钥脱敏 |
| `model_providers.py` | 供应商预设、环境变量、三种协议适配与模型目录；变更时同步配置示例、README 和官网 |
| `sync_storage.py` | 操作日志合并、旧数据兼容、原子落盘 |
| `drive_sync.py` | 同步重试、OAuth 生命周期、部分成功的进度报告 |
| `fsrs.py` | 复习调度与历史重放一致性；更改算法需独立评估 |
| `pdf_export.py` | 排版、分页、字体字形完整性与错误提示 |
| `desktop_backend.py` | 桌面独立数据目录、启动握手、父进程退出后的服务清理 |
| `desktop/` | Electron 进程管理、窗口隔离、导航与下载、平台打包 |
| `desktop/lib/updates.cjs` | 更新确认、进度、取消及安装状态；安装前须保存偏好并关闭后端 |
| `frontend/src/lib/` | 无 React 生命周期依赖、可用 Node 测试的纯逻辑 |
| `frontend/src/use*.js` | 请求、事件、轮询与页面状态生命周期 |

保留 API、词库和备份兼容性。尤其不要将“代码清理”顺带变成调度算法或同步格式升级；历史评分会被重放，算法更改可能影响所有已有复习状态。

样式优先修改拥有该组件的规则，避免不断追加同选择器覆盖。新注释解释约束与意图，不复述代码；遵循相邻代码的命名与格式。

## 提交范围

- 每个 PR 聚焦一个问题，描述触发条件、变化后的行为及验证结果。
- 前端修改必须包含更新后的 `frontend/dist`。仓库有意跟踪构建文件，便于只安装 Python 即可运行。
- 功能、入口、配置或兼容性发生变化时，同步修改 README / 相关指南与 `CHANGELOG.md` 的 `Unreleased`。
- 不提交虚拟环境、`node_modules`、测试缓存、系统文件、真实密钥、词库或个人备份。
- 删除资源前检查运行时代码、文档及构建引用。保留有用的封面、示例配置与测试资源。

## 依赖与 CI

常规检查使用 lockfile 和已固定的依赖。依赖升级单独审查，记录旧/新版本、兼容性影响与验证，不直接执行 `npm audit fix --force`。

应用内更新新增固定运行依赖 `electron-updater` **6.8.11** 与 `semver` **7.8.5**，未升级现有 Electron / electron-builder。此次安装后的桌面依赖 `npm audit` 为 0 条已知漏洞；后续维护仍应重新检查，不代表跨平台安装验收已完成。

```bash
npm --prefix frontend audit
npm --prefix desktop audit
./.venv/bin/python -m pip check
```

`pip check` 只检查版本约束，不查询安全公告；`npm audit` 反映已知公告匹配，是否可触达还需结合应用使用方式判断。依赖变更需同步更新约束文件、lockfile 和 CI，并执行回归检查。

维护 Router 6 时需注意两项已知边界：

- [反斜杠跳转公告](https://github.com/remix-run/react-router/security/advisories/GHSA-wrjc-x8rr-h8h6)：词条链接和 API 路径已统一编码，属于应用层防护，依赖公告仍需后续升级解决。路由改动必须保留特殊词条 ID 的回归测试。
- [SSR hydration 公告](https://github.com/remix-run/react-router/security/advisories/GHSA-337j-9hxr-rhxg)：当前使用 `createRoot + BrowserRouter`，没有 SSR / hydration 入口；如果引入这些能力，需重新评估依赖。

GitHub Actions 运行 Python 静态检查/测试、前端静态检查/测试/构建，并拒绝过期构建产物。提交 PR 时应确认 CI 通过。
