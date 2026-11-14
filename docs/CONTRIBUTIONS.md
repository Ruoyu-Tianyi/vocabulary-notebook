# 上游贡献状态（2026-11-14）

上游：[Eric-Zhou-0302/vocove](https://github.com/Eric-Zhou-0302/vocove)。各分支均以上游 ddae801 为基线，独立提交。

| 功能 | 状态 |
| --- | --- |
| 即时释义、Drive 同步、添加时间排序 | #1、#2、#3 已合并 |
| AI 迟到结果保护、独立语境单词本 | [#14](https://github.com/Eric-Zhou-0302/vocove/pull/14)、[#15](https://github.com/Eric-Zhou-0302/vocove/pull/15) 已合并；#6/#13 已由它们替代 |
| DeepSeek 查词非思考 JSON 模式 | [#17](https://github.com/Eric-Zhou-0302/vocove/pull/17) 待审；已并入 #22，#22 合并后可关闭 |
| 查词提速：输出长度上限、各供应商非思考模式、参数回退、连接复用 | [#22](https://github.com/Eric-Zhou-0302/vocove/pull/22) 2026-11-14 新增，待审 |
| 中文/全角搜索规范化及字母筛选重置 | [#18](https://github.com/Eric-Zhou-0302/vocove/pull/18) 待审 |
| 可选私人手机学习网关 | [#19](https://github.com/Eric-Zhou-0302/vocove/pull/19) 待审，仅固定端口源码服务 |
| 语境单词本限定专业领域释义 | [#20](https://github.com/Eric-Zhou-0302/vocove/pull/20) 待审 |
| 顶部单行品牌与学习导航 | [#21](https://github.com/Eric-Zhou-0302/vocove/pull/21) 待审 |
| 添加单词默认最近查看的单词本 | [#23](https://github.com/Eric-Zhou-0302/vocove/pull/23) 2026-11-14 新增，待审 |
| 详情页返回来源列表或添加页并保留录入列表 | [#24](https://github.com/Eric-Zhou-0302/vocove/pull/24) 2026-11-14 新增，待审 |
| 旧 Windows 启动器及旧导航设计 | #4/#7 关闭；采用上游现有桌面和界面，不重复提交 |
| 备份与 agent 更新流程 | #5 原作者明确暂不实现，保留 fork 扩展，不重复提交 |
| fork 更新源及旧个人配置迁移 | 仅本 fork 使用，不适合作为上游功能提交 |

本轮 #18/#19 的 Python 3.11、3.12、前端、官网 GitHub Actions 均通过且无合并冲突；Vercel 预览均需上游团队授权。后续自动检查状态以各 PR 最新提交为准。测试使用临时数据和模拟外部服务，不作为真实 DNS、隧道、桌面安装或 Drive 授权的验收证明。

#22、#23、#24 已在本地通过对应的后端或前端检查；上游 CI 以各 PR 页面为准。#23、#24 均包含 `frontend/dist`，先合并其一后另一需重新构建。
