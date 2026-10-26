![Vocove 概念封面](assets/vocove-cover.jpg)

# Vocove

[![CI](https://github.com/Eric-Zhou-0302/vocove/actions/workflows/ci.yml/badge.svg)](https://github.com/Eric-Zhou-0302/vocove/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Vocove 是一个本地优先的英文词汇学习应用。你可以按主题整理单词，使用 Ollama 或 DeepSeek 补全音标、中文释义和例句，再通过间隔复习巩固记忆。

当前版本：[**1.3.0**](https://github.com/Eric-Zhou-0302/vocove/releases/tag/v1.3.0)。默认分支上的后续改动见[更新日志](CHANGELOG.md)。

## 功能亮点

- **单词本管理**：同词可加入多个单词本，每本独立保存内容与复习进度。
- **AI 内容补全**：支持本地 Ollama 和 DeepSeek API，显示任务进度，支持失败重试。
- **间隔复习**：四档记忆评分、每日新词额度和复习间隔预览，也可按字母或随机顺序翻卡。
- **查找与导出**：支持搜索、筛选、排序，以及 PDF、CSV、JSON 导出。
- **同步与备份**：可选 Google Drive 文件夹或 API 直连，支持完整学习历史备份与合并导入。
- **桌面与移动端体验**：提供深浅色主题、响应式布局、可收起侧栏和键盘快捷键。

Vocove 提供桌面应用和网页两种使用方式。学习数据保存在本机；跨电脑使用可通过 Google Drive 同步，详见 [Drive 同步指南](docs/DRIVE_SYNC.md)。

## 桌面版：下载即用

桌面版基于 Electron，内置运行环境，无需安装 Python、Node.js 或使用命令行。

[下载 Vocove 1.3.0 →](https://github.com/Eric-Zhou-0302/vocove/releases/tag/v1.3.0)

| 系统 | 安装方式 |
| --- | --- |
| macOS Apple Silicon | 下载 arm64 的 `.dmg`，将应用拖入「应用程序」 |
| macOS Intel | 下载 x64 的 `.dmg`，将应用拖入「应用程序」 |
| Windows x64 | 下载 `.exe` 安装包，双击并按提示安装 |

**macOS 首次打开**：若提示 Apple 无法验证应用，点击「完成」，进入「系统设置 → 隐私与安全性 → 安全性」，点击「仍要打开」并确认。

> Q：为什么需要这个？
> A：当前安装包未进行 Apple Developer ID 签名和公证。

安装后打开 **Vocove**，在「设置与工具 → 模型设置」中配置 Ollama 或 DeepSeek，即可开始记录和复习单词。

> **应用内更新**：从 macOS「Vocove → 检查更新」或 Windows「帮助 → 检查更新」获取新版本。

## 网页版：从源码运行

### 环境要求

- Python **3.11+**；CI 覆盖 3.11 和 3.12。
- 直接使用已提交的前端构建文件时，无需 Node.js。
- 修改前端需要 Node.js **22.13+（22.x）或 24+** 及 npm。
- 以下命令适用于 macOS / Linux shell。

### 安装并启动

```bash
git clone https://github.com/Eric-Zhou-0302/vocove.git
cd vocove
python -m pip install -r requirements.txt

# 仅首次创建配置，不覆盖已有设置。
test -f config.json || cp config.json.example config.json
python app.py
```

打开 [http://localhost:1400](http://localhost:1400)。`python app.py` 会直接托管 `frontend/dist`，无需另外启动前端服务器。

### 配置补全服务

- **Ollama**：启动本机或自托管的 Ollama 服务，在「设置与工具 → 模型设置」中填写服务地址和已安装的模型名称。默认地址为 `http://localhost:11434/api/generate`。
- **DeepSeek**：在 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys)创建 API Key，填写后刷新模型列表、选择模型并保存。模型列表由官方接口获取。

网页保存配置后立即生效；已有 Key 不会回传浏览器，留空会保留原值。若直接修改 `config.json`，需重启后端。配置结构见 [config.json.example](config.json.example)。

未连接模型时，仍可浏览已有词库和复习。可选的拼写校验需要先安装系统 Enchant 库及 `en_US` 词典，再运行 `python -m pip install -r requirements-spellcheck.txt`；详见 [PyEnchant 安装说明](https://pyenchant.github.io/pyenchant/install.html)。

旧版用户升级前请先备份数据，迁移与回退说明见[旧词库备份与升级](docs/DRIVE_SYNC.md#旧词库备份与升级)。

## 日常使用

### 记录与整理

添加单词时选择单词本并保存，补全结果会显示在最近记录中。补全期间可继续使用应用；网络、授权或模型响应异常时，记录会保留供重试，也可在详情页手动编辑。

「整理单词」支持跨本加入或移动：加入会保留原词，目标本从新词开始复习；移动会保留复习进度，目标本已有同词时停止整批操作，避免覆盖。

### 复习与快捷键

「今日复习」根据到期记录和每日额度组成队列。先回忆再翻面评分，选择「重来」的卡片会回到本轮队尾。默认每天引入 20 个新词，各本共用额度，可通过 `config.json` 的 `srs.daily_new_limit` 修改。

「全部单词」按 A–Z 或随机顺序翻阅，不提交评分、不消耗新词额度。

| 快捷键 | 用途 |
| --- | --- |
| `/` | 返回单词列表并选中搜索框 |
| `N` | 打开添加单词 |
| `?` | 打开或关闭帮助 |
| `Space` / `Enter` | 复习时显示答案 |
| `1` / `2` / `3` / `4` | 显示答案后选择重来、困难、良好、简单 |
| `←` / `→` | 全部单词模式中返回上一张，或显示答案后进入下一张 |
| `Esc` | 清空搜索、关闭弹窗或菜单，具体行为取决于当前位置 |

快捷键会在输入框、下拉框和其他弹窗中暂停或按场景处理；输入法候选、修饰键组合和长按不会被误触。完整规则可在应用内按 `?` 查看。

### 导出与完整备份

| 入口 | 内容与用途 |
| --- | --- |
| 单词列表 → PDF / CSV / JSON | 导出当前筛选下的词汇内容，适合打印、整理与二次处理 |
| 同步与备份 → 下载完整备份 | 保存所有单词本、字段操作、删除标记及评分事件，适合迁移与恢复 |
| 同步与备份 → 导入备份 | 合并导入完整备份或旧词库，不覆盖整个现有词库 |

**普通列表导出不能替代完整学习历史备份。**

PDF 中文和音标导出需要包含相应字形的静态 TTF / OTF 字体。macOS 默认尝试系统 Arial Unicode 字体，其他环境可手动指定：

```bash
VOCOVE_CJK_FONT=/absolute/path/to/font.ttf python app.py
```

不支持 TTC 字体集合或可变字体。字体不可用、缺少字形或单条词汇超出一页容量时会明确报错，可改用 CSV / JSON。项目不打包第三方字体，使用前请确认字体授权。

## 开发与贡献

开发环境、等价命令和兼容性约定见[贡献指南](CONTRIBUTING.md)。常用检查命令：

```bash
make check   # 静态检查、前后端及桌面测试、前端构建
make lint    # 仅静态检查
make test    # 后端、前端与桌面测试
make build   # 更新 frontend/dist
```

**修改前端后必须构建并一并提交 `frontend/dist`**，否则 `python app.py` 仍会显示旧页面。CI 会检查提交的前端构建是否最新。

<details>
<summary>开发模式与热更新</summary>

安装开发依赖：

```bash
python -m pip install -r requirements-dev.txt
npm --prefix frontend ci
npm --prefix desktop ci --ignore-scripts
```

需要热更新时，在两个终端分别运行：

```bash
./.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 1400 --no-proxy-headers --timeout-graceful-shutdown 5 --reload
```

```bash
npm --prefix frontend run dev -- --host 127.0.0.1
```

开发页面为 [http://localhost:5173](http://localhost:5173)。不要同时启动两个后端操作同一份词库；实例锁会拒绝重复启动。

</details>

自动测试使用临时目录和模拟外部请求，不等于真实 OAuth、模型调用或跨电脑同步验收。

## 反馈与许可

问题反馈请使用 [Issue 模板](https://github.com/Eric-Zhou-0302/vocove/issues/new/choose)，提交改动前请阅读[贡献指南](CONTRIBUTING.md)。

本项目采用 [MIT License](LICENSE)，Copyright © 2026 Eric Zhou。
