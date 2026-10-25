# 项目说明

## 技术栈
- 后端：Python 3.11+、FastAPI + uvicorn（端口 1400），使用项目 `.venv`
- 前端：React + Vite（端口 5173），静态文件构建到 `frontend/dist`
- 部署模式：后端 `python app.py` 直接托管 `frontend/dist`

## 重要规则

**前端代码改动后，必须执行 `cd frontend && npm run build`**

原因：`python app.py` 模式下，后端只读取 `frontend/dist` 的预编译文件，改源码不会自动同步，必须手动 build 才能让改动生效。

## 开发模式

需要热更新时，从项目根目录分别在两个终端启动服务：

```bash
# 后端
./.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 1400 --no-proxy-headers --timeout-graceful-shutdown 5 --reload
```

```bash
# 前端
cd frontend && npm run dev -- --host 127.0.0.1
```

前端开发页面为 http://localhost:5173，源码修改会自动更新。日常使用可直接运行 `python app.py`，由后端托管已构建的前端。

## 验证与维护

- `make check` 运行 Ruff、pytest、ESLint、前端逻辑测试及构建；开发环境安装和等价命令见 `CONTRIBUTING.md`。
- `frontend/dist` 有意纳入 Git，使用户只安装 Python 依赖也能运行；前端修改后同步提交构建产物。
- 后端测试使用临时词库、配置与模拟外部请求；路由测试使用 `tests.local_client.TestClient` 保留本机访问约束。
- `pdf_export.py` 独立负责 PDF 排版及字体校验，字体要求见 README。
- `sync_storage.py` 保存操作日志并重放复习历史；更改数据格式或 `fsrs.py` 算法需专门处理兼容性，不能作为一般清理顺带修改。
- 同步行为见 `docs/DRIVE_SYNC.md`，依赖维护与验证约定见 `CONTRIBUTING.md`。
- 不读取或修改真实 `words.json`、`config.json`、`.secrets` 来完成自动验证，不运行 `tests.test_prompt --live`，除非用户授权真实模型调用。
