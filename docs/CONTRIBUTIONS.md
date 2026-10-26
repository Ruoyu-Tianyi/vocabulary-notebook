# 上游贡献与审核记录

**2026-10-19 更新：#1 已合并；其余内容已修复 v1.1.0 冲突并拆为六个独立 PR，见 [最新拆分与验证记录](CONTRIBUTIONS_20261019.md)。以下保留 2026-10-18 的历史审核快照。**

完整版本继续维护在 [Ruoyu-Tianyi/vocabulary-notebook](https://github.com/Ruoyu-Tianyi/vocabulary-notebook) 的 main，保留来源历史、MIT 版权及原项目说明。以下 PR 提给 [Eric-Zhou-0302/vocabulary-notebook](https://github.com/Eric-Zhou-0302/vocabulary-notebook)，按功能分别审核，不需要用户切换到贡献分支安装。

| PR | 范围 | Python 3.9.6 | Python 3.12.14 |
|---|---|---|---|
| [#1 即时记忆与安全输入](https://github.com/Eric-Zhou-0302/vocabulary-notebook/pull/1) | 添加后释义、重复词原内容、首字母大写、独立 SSE 通知、无效新词清理与人工编辑保护 | 73 通过 | 73 通过 |
| [#2 Drive 与课程单词本](https://github.com/Eric-Zhou-0302/vocabulary-notebook/pull/2) | 两机合并、逐次复习、自定义单词本、紧凑状态栏与学习主导航 | 60 通过 | 60 通过 |
| [#3 添加时间排序](https://github.com/Eric-Zhou-0302/vocabulary-notebook/pull/3) | 最新/最早顺序、选择记忆、导出一致、UTC Z 兼容 | 31 通过 | 31 通过 |
| [#4 Windows 一键启动](https://github.com/Eric-Zhou-0302/vocabulary-notebook/pull/4) | 原生 EXE、桌面快捷方式、自制图标、托盘、安全停止 | 30 通过，2 跳过 | 32 通过 |
| [#5 无损更新](https://github.com/Eric-Zhou-0302/vocabulary-notebook/pull/5) | 本地备份、SHA-256 校验、运行锁、安装/简短更新提示词 | 37 通过 | 37 通过 |

2026-10-18 重新审核，基于上游 `2fa140c`。#1、#2、#4 前端重新构建通过；#3 前端在上一轮已构建，本轮源码未变；#5 不改前端。Python 3.9 的两个跳过项仅因本机嵌入式解释器缺少 venv，涉及创建隔离虚拟环境的 EXE 验收；同样的真实 EXE 用例在 Python 3.12 全部通过。

本轮修复：启动器等待线程写入结束后才报告停止；默认单词本仅修改课程说明时名称不再消失；误词移除后刷新分页并保留明确提示；输入 PR 的后台结果保护人工释义与改名后的词条。已有的通知竞争、局域网访问、同步草稿、课程移动及 UTC 时间问题也保留在相应 PR 中。

测试使用临时词库、模拟 AI、隔离端口和临时 Drive 文件夹，不把模拟结果当作真实 Google OAuth 或收费 AI 验收。各 PR 保留上游的 Ollama / DeepSeek 选择；本 fork 的 DeepSeek 默认方案、个人安装路径和旧仓库迁移说明继续留在完整版本，不要求上游采用。

各 PR 当前分别针对上游 main，可以单独审阅；它们共同修改 app.py、README 或已构建前端，依次合并后其余 PR 仍可能需要整合，届时应保留双方功能并重新构建测试。不要直接采用一方整个文件覆盖另一方。提交 PR 不代表原作者已批准或合并。


## 2026-10-25 上游状态与整合

- #1 即时记忆、#2 Drive 同步、#3 时间排序已合并。
- #4 桌面启动器已关闭，作者计划统一支持 macOS / Windows。
- #5 安全更新工具已关闭，作者表示暂不实现。
- #6 单词本、#7 导航已关闭；上游另有单词本与新布局实现，本分支吸收上游实现并保留课程 AI 上下文。
- 整合基线：bccf30d（v1.2.0 后的测试配置隔离修复）。保留双方历史，私人远程网关为本分支独立功能，默认不启用公网。

## 2026-10-26 · Vocove v1.3.0

上游已更名为 Eric-Zhou-0302/vocove，整合基线 9dbf223。#6 的剩余课程语境与并发保护部分基于最新 main 重写为 [PR #13](https://github.com/Eric-Zhou-0302/vocove/pull/13)，不重复引入旧单词本界面。#7 导航目标已被上游实现覆盖，#4 已由官方桌面应用替代，#5 尊重作者暂不实现的决定，均不重复提交。

服务器仍沿用原安装目录、数据与私有网关；独立 Electron 桌面程序的安装、迁移和官方自动更新不是本 fork 服务器的更新路径。
