# Tianyi 分支：沿用上游桌面应用

本仓库基于 [Eric Zhou 的 Vocove](https://github.com/Eric-Zhou-0302/vocove)，保留 MIT 许可和完整 Git 历史。2026-11-02 同步至 v1.5.1 / `ddae801`；本分支构建版本为 `1.5.1-tianyi.4`。

## 使用与迭代方式

默认采用上游的 React 界面、Electron 桌面窗口、内置 Python 后端、独立数据目录、NSIS Windows 安装器、macOS DMG/ZIP 和应用内更新。后续功能在此架构上迭代，不再维护另一套主界面。

在本仓库 [Desktop packages](https://github.com/Ruoyu-Tianyi/vocabulary-notebook/actions/workflows/desktop-build.yml) 中打开成功运行，下载对应的 Windows-x64、macOS-arm64 或 macOS-x64 artifact。解压 artifact 后，Windows 运行其中的安装 EXE，Mac 打开 DMG 并拖入应用程序。构建验证通过不等于已发布 Release；签名、公证和首次安装提示沿用上游现有限制。

本分支更新来源为 `Ruoyu-Tianyi/vocabulary-notebook`，只有该仓库正式发布了兼容的 Release、校验文件及更新元数据后才能发现更新。上游发布新版本不会自动覆盖本分支扩展。README 中的上游下载链接仍指向原作者原版，请区分来源。

为兼容上游，产品名、安装身份及默认数据目录仍是 Vocove，不应把两个来源当作互不干扰的应用并行安装。切换来源前完全退出应用并备份。需要独立测试时使用绝对路径环境变量 `VOCOVE_DESKTOP_USER_DATA_DIR`，勿指向日常资料。

## 保留的补充

| 部分 | 本分支处理 |
| --- | --- |
| 语境单词本、即时记忆、排序、复习、Drive、多模型与整体设计 | 采用上游现有实现；#14 / #15 已进入上游，不重复维护 |
| 中文译文搜索 | 保留空白、全角字符和大小写规范化；输入搜索时清除字母筛选 |
| DeepSeek 查词 | 保留 `fix/deepseek-dictionary-nonthinking` 的非思考 JSON 输出修复；不改变其他供应商协议 |
| 私人手机/平板入口 | 可选源码服务器扩展，认证网关限制管理接口；见 [私人访问说明](PRIVATE_ACCESS.md) |
| 更新数据保护 | 保留 `maintenance.py` 离线备份和 `migrate_legacy_config.py` 显式配置迁移 |
| 旧 VocabularyBook.exe | 仅兼容已有源码服务器，不是新版 Electron 安装包；新用户使用 Desktop packages |

桌面应用和私人服务器是不同运行方式：桌面版使用独立目录和动态本地端口，关闭窗口/退出应用的行为遵循上游；已有远程网关仍连接固定的源码服务端口 1400。安装桌面版不会自动把旧目录变成桌面资料，也不会自动接管现有手机域名服务。

## 已有用户迁移

现有词库、复习日志、Drive 授权和密码文件不随 Git 更新覆盖。历史版本保存在 `archive/pre-v151-20261102` 分支。

1. 停止旧应用/源码服务器，用 `python maintenance.py --project "原项目绝对路径" backup` 创建并记录本地备份；密钥与备份不要提交 Git。
2. 如果原分支把 DeepSeek 设置放在 `.secrets/deepseek.json`，执行 `python migrate_legacy_config.py --root "原项目绝对路径"`。它先保留 `config.json.pre-v151.bak`，再把模型和密钥接入上游配置格式，不修改词库或删除旧密钥；重复运行不会覆盖备份。此配置仅保存在本机。
3. 继续使用源码服务器时，在依赖更新后启动原入口。改用桌面版时，先从旧应用导出完整学习备份，再在新桌面版的同步/备份页导入；核对词数、单词本和复习进度。模型与 Drive 连接在桌面版中配置，原目录保留作恢复来源。
4. 两个运行方式如需接续学习，分别配置同一个 Drive 同步空间；不要让两个进程直接共用同一个本地词库文件。

## 给 Agent 的更新提示词

```text
请更新我的 https://github.com/Ruoyu-Tianyi/vocabulary-notebook 安装。
先确认我使用的是 Electron 安装版还是旧源码服务器，并找到实际数据目录；停止对应实例，完整备份词库、复习记录、配置及本地凭据，记录当前版本。
安装版采用本 fork 的兼容安装包；源码版拉取 main 并按指南更新依赖，必要时运行 migrate_legacy_config.py 接入旧 DeepSeek 配置。
保留现有数据、Drive/API 配置和私人域名服务；不要用示例配置覆盖真实文件，不要重建空词库，不要把密钥上传 Git。
更新后核对词数、单词本、复习记录及启动情况。若改用桌面版，先导出完整备份再导入其独立数据目录，不删除旧安装目录。
```

## 开发与打包

### Windows 本地一键升级

先在桌面应用的“同步与备份”完成同步；文件夹模式另在 Google Drive 桌面版确认上传进度。双击仓库根目录 `upgrade-desktop.cmd`，默认安装项目内打包依赖、检查前端与桌面逻辑并构建当前源码，再退出原应用、创建 `.backups/desktop-upgrades/` 本地备份、校验安装包 SHA-256、静默升级原目录。使用原项目 `.venv` 启动工具，打包使用独立 `.venv-desktop`，需要 Python 3.11+ 与 Node.js 22.13+ 或 24+。

已有本仓库可信构建包时可跳过构建（同目录必须有对应 `.sha256`）：

```powershell
.\.venv\Scripts\python.exe tools\desktop_upgrade.py --installer "安装包绝对路径.exe"
```

默认升级 `%LOCALAPPDATA%\Programs\Vocove`，保护 `%APPDATA%\Vocove` 资料；可用 `--install-dir` / `--profile` 指定其他绝对路径。构建在退出应用前进行；不会拉取 Git、强制终止进程、修改环境变量或发布 Release。安装后用独立空资料运行 `--smoke-test`（含后端健康、页面、保存和复习），再次逐文件校验正式词库、完整 data 目录、本机凭据和桌面偏好，全部通过后才重启原资料。可传 `--no-restart` 保持停机。

传 `--build-only` 可只构建和校验安装包，不停止或更新应用；构建流程也运行完整后端回归。备份包含密钥，只留本机；升级报告与冒烟日志保存在备份目录。失败保留现场且不自动恢复快照，以免覆盖后来记录。现有内置“帮助 → 检查更新”仍用于正式 Release；本地工具用于开发构建，不代替发布流程。SHA-256 校验不代表签名认证，只运行自己构建或可信仓库下载的安装包。

遵循上游 [CONTRIBUTING](../CONTRIBUTING.md)。`desktop/` 的构建工作流在 Windows 和两种 Mac 架构分别测试、构建和冒烟验证。私人网关依赖位于 `requirements-remote.txt`；常规桌面不需要启动网关。自动验证只使用临时目录与模拟外部请求。
