# 上游贡献状态（2026-11-02）

上游：[Eric-Zhou-0302/vocove](https://github.com/Eric-Zhou-0302/vocove)。本轮分支均以 ddae801 为基线，独立提交。

| 功能 | 状态 |
| --- | --- |
| 即时释义、Drive 同步、添加时间排序 | #1、#2、#3 已合并 |
| AI 迟到结果保护、独立语境单词本 | [#14](https://github.com/Eric-Zhou-0302/vocove/pull/14)、[#15](https://github.com/Eric-Zhou-0302/vocove/pull/15) 已合并；#6/#13 已由它们替代 |
| DeepSeek 查词非思考 JSON 模式 | [#17](https://github.com/Eric-Zhou-0302/vocove/pull/17) 待审，无冲突；代码检查通过，Vercel 预览需上游团队授权 |
| 中文/全角搜索规范化及字母筛选重置 | [#18](https://github.com/Eric-Zhou-0302/vocove/pull/18) 本轮新增 |
| 可选私人手机学习网关 | [#19](https://github.com/Eric-Zhou-0302/vocove/pull/19) 本轮新增，仅固定端口源码服务 |
| 旧 Windows 启动器及旧导航设计 | #4/#7 关闭；采用上游现有桌面和界面，不重复提交 |
| 备份与 agent 更新流程 | #5 原作者明确暂不实现，保留 fork 扩展，不重复提交 |
| fork 更新源及旧个人配置迁移 | 仅本 fork 使用，不适合作为上游功能提交 |

本轮 #18/#19 的 Python 3.11、3.12、前端、官网 GitHub Actions 均通过且无合并冲突；Vercel 预览均需上游团队授权。后续自动检查状态以各 PR 最新提交为准。测试使用临时数据和模拟外部服务，不作为真实 DNS、隧道、桌面安装或 Drive 授权的验收证明。
