# 贡献指南

## 准备环境

先按 [README](README.md) 安装项目，再安装开发依赖：

```bash
./.venv/bin/python -m pip install -r requirements-dev.txt
npm --prefix frontend ci
```

使用项目 `.venv` 和 `frontend/node_modules`，不需要全局安装 Python / npm 包。运行时使用 Python 3.11+；Node.js 22.13+（22.x）或 24+ 可运行前端检查。CI 使用 Node.js 22，Python 3.11 与 3.12。

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
```

使用已激活的项目环境时，可用 `make check PYTHON=python`。静态检查约束未定义名称、无用导入和 Hooks 使用，不以批量格式化代替问题修复。

### 后端测试

- 使用 pytest 临时目录隔离词库、配置与同步文件。
- HTTP 路由测试使用 `tests.local_client.TestClient`，显式模拟本机连接；不要为了通过测试关闭实际来源校验。
- 模型调用、Drive 网络与授权应使用 mock，不在默认测试中发起真实请求。
- OAuth 回调测试会使用临时本机 HTTP 服务；Google / DeepSeek 等外部接口仍被模拟。
- 测试配置全局缓存、后台任务或队列时，恢复 monkeypatch 和任务生命周期。
- `tests/test_prompt.py` 默认只做本地检查；`--live` 会调用已配置的模型，可能产生费用，只有手动验证时使用。

```bash
./.venv/bin/python -m pytest tests/test_sync.py -q
./.venv/bin/python -m tests.test_prompt --case coordinated
```

### 前端测试

`npm test` 使用 Node 自带的测试运行器，覆盖可独立验证的 API、SSE 流与洗牌逻辑，不需要额外浏览器测试框架。

修改 Hook 时检查请求取消、迟到响应、轮询重叠、定时器和监听器清理。改动布局或交互时，还需要浏览器检查：窄屏/桌面、深浅色、键盘焦点与减少动态效果。新增视觉行为的截图可放进 PR，无需提交临时截图到仓库。

## 代码结构与边界

| 模块 | 维护重点 |
| --- | --- |
| `app.py` | 路由校验、HTTP 错误语义、任务启动与退出、应用状态 |
| `config.py` | 校验成功后发布缓存；保存失败不污染现有配置 |
| `sync_storage.py` | 操作日志合并、旧数据兼容、原子落盘 |
| `drive_sync.py` | 同步重试、OAuth 生命周期、部分成功的进度报告 |
| `fsrs.py` | 复习调度与历史重放一致性；更改算法需独立评估 |
| `pdf_export.py` | 排版、分页、字体字形完整性与错误提示 |
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

```bash
npm --prefix frontend audit
./.venv/bin/python -m pip check
```

`pip check` 只检查版本约束，不查询安全公告；`npm audit` 反映已知公告匹配，是否可触达还需结合应用使用方式判断。依赖变更需同步更新约束文件、lockfile 和 CI，并执行回归检查。

维护 Router 6 时需注意两项已知边界：

- [反斜杠跳转公告](https://github.com/remix-run/react-router/security/advisories/GHSA-wrjc-x8rr-h8h6)：词条链接和 API 路径已统一编码，属于应用层防护，依赖公告仍需后续升级解决。路由改动必须保留特殊词条 ID 的回归测试。
- [SSR hydration 公告](https://github.com/remix-run/react-router/security/advisories/GHSA-337j-9hxr-rhxg)：当前使用 `createRoot + BrowserRouter`，没有 SSR / hydration 入口；如果引入这些能力，需重新评估依赖。

GitHub Actions 运行 Python 静态检查/测试、前端静态检查/测试/构建，并拒绝过期构建产物。提交 PR 时应确认 CI 通过。
