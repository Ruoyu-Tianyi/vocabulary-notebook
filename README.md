[![Vocove 概念封面 · 访问产品网站](assets/vocove-cover.jpg)](https://www.vocove.cn)

# Vocove

[![Website](https://img.shields.io/badge/Website-vocove.cn-b89962)](https://www.vocove.cn)
[![CI](https://github.com/Eric-Zhou-0302/vocove/actions/workflows/ci.yml/badge.svg)](https://github.com/Eric-Zhou-0302/vocove/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Vocove 是一个本地优先的英文词汇学习应用。你可以按主题整理单词，使用 Ollama 或多家云端模型补全音标、中文释义和例句，再通过间隔复习巩固记忆。

**[访问产品网站 ↗](https://www.vocove.cn)** · [下载桌面版](https://www.vocove.cn/#download) · [查看功能](https://www.vocove.cn/#features) · [常见问题](https://www.vocove.cn/#faq)

当前版本：[**1.5.1**](https://github.com/Eric-Zhou-0302/vocove/releases/tag/v1.5.1)。支持 15 个模型供应商及自定义 API，完整变更见[更新日志](CHANGELOG.md)。

## 功能亮点

- **单词本管理**：同词可加入多个单词本，每本独立保存内容与复习进度。
- **AI 内容补全**：支持 Ollama、DeepSeek、OpenAI、Claude 等 15 个供应商及自定义 API，显示任务进度，支持失败重试。
- **间隔复习**：四档记忆评分、每日新词额度和复习间隔预览，也可按字母或随机顺序翻卡。
- **查找与导出**：支持搜索、筛选、排序，以及 PDF、CSV、JSON 导出。
- **同步与备份**：可选 Google Drive 文件夹或 API 直连，支持完整学习历史备份与合并导入。
- **桌面与移动端体验**：提供深浅色主题、响应式布局、可收起侧栏和键盘快捷键。

Vocove 提供桌面应用和网页两种使用方式。学习数据保存在本机；跨电脑使用可通过 Google Drive 同步，详见 [Drive 同步指南](docs/DRIVE_SYNC.md)。

### 补全期间的编辑保护

模型请求发出后，如词条被移动、重命名或所属单词本被修改，本次旧结果不会写入；无效词响应也不会删除变更后的词条。页面会提示重新补全。已有释义和复习记录保留，同步日志格式不变。

## 桌面版：下载即用

桌面版基于 Electron，内置运行环境，无需安装 Python、Node.js 或使用命令行。

[下载 Vocove 1.5.1 →](https://github.com/Eric-Zhou-0302/vocove/releases/tag/v1.5.1)

| 系统 | 安装方式 |
| --- | --- |
| macOS Apple Silicon | 下载 arm64 的 `.dmg`，将应用拖入「应用程序」 |
| macOS Intel | 下载 x64 的 `.dmg`，将应用拖入「应用程序」 |
| Windows x64 | 下载 `.exe` 安装包，双击并按提示安装 |

**macOS 首次打开**：若提示 Apple 无法验证应用，点击「完成」，进入「系统设置 → 隐私与安全性 → 安全性」，点击「仍要打开」并确认。

> Q：为什么需要这个？
> A：当前安装包未进行 Apple Developer ID 签名和公证。

安装后打开 **Vocove**，在「设置与工具 → 模型设置」中配置模型供应商，即可开始记录和复习单词。

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

- 内置 **15 个供应商**：Ollama、DeepSeek、OpenAI、Anthropic / Claude、Google Gemini、通义千问 / 百炼、Kimi / Moonshot、智谱 GLM、硅基流动、OpenRouter、Groq、Mistral AI、Together AI、Fireworks AI、xAI / Grok。
- **配置流程**：选择供应商 → 输入密钥或设置对应后端环境变量 → 获取模型目录或手动添加模型 ID → 可选测试连接 → 保存并使用。每家配置独立保留；仅保存当前选择的供应商。保存不依赖目录接口成功，目录包含非对话模型时请选择文本生成模型。
- **Ollama**：先运行 `ollama serve`，使用 `ollama pull 模型名称` 下载模型，再获取已安装模型。默认根地址 `http://localhost:11434`；兼容旧版 `/api/generate` 地址。远程服务支持可选 Bearer 密钥。
- **自定义 API**：支持 OpenAI Chat Completions、Anthropic Messages 和 Ollama 原生协议。填写 API 根地址（保留 `/v1` 等版本路径），可选密钥、模型 ID 和 5–600 秒生成超时。内置供应商也可覆盖地址以适配地区端点或网关；Coding Plan 必须使用供应商对应地址。
- **密钥**：优先使用手动保存的密钥，否则读取界面列出的环境变量。密钥仅存于本机 `config.json`，接口不回传；留空保留旧值，勾选清除后移除已存值。环境变量需在启动后端前设置。重新输入新密钥会取消清除操作；纯空格按留空处理。修改地址时须重新输入密钥，避免旧密钥自动发送到其他服务。
- **DeepSeek 词汇补全**：词典请求显式关闭思考模式、使用 JSON Output，并限制输出为 2048 tokens，避免简单查词默认进入思考模式。仅作用于内置 DeepSeek 的词汇补全；连接测试仍使用普通文本请求，其他供应商和自定义 API 不附加这些专用参数。
- **验证**：获取目录不产生文本生成费用；“测试连接与模型”会发出一条简短真实生成请求，可能计费。自动健康检查只查询目录，云端未列出的模型显示待测试，不等同于模型下线。旧 Ollama / DeepSeek 配置无需手动迁移。

完整 JSON 见 [`config.json.example`](config.json.example)。手动编辑时：

| 字段 | 用法 |
| --- | --- |
| `provider` | 当前供应商 ID，如 `anthropic`、`qwen` 或 `custom`；可选 ID 见配置示例的对象名称 |
| `last_builtin_provider` | 程序自动记录最近保存的内置供应商，用于切换标签后的恢复，无需手动填写 |
| `ollama` / `deepseek` | 为兼容旧配置，这两家继续使用顶层对象 |
| `providers.<供应商 ID>` | 其他供应商及 `custom` 的独立配置对象 |
| `base_url` | API 根地址，保留版本路径；Ollama 也兼容旧 `url` 字段 |
| `api_key` | 留空时读取对应环境变量；自定义服务及 Ollama 可不认证 |
| `model` | 实际调用的完整模型 ID；示例中的云端模型留空，启用前需填写 |
| `models` | 设置页中保留的模型目录；可留空，不限制手动填写的 `model` |
| `timeout` | 生成请求超时秒数，设置页允许 5–600，默认 120 |
| `protocol` | 仅自定义 API 需要：`openai`、`anthropic` 或 `ollama` |

例如启用 Claude：将 `provider` 改为 `anthropic`，填写 `providers.anthropic.model`，并填写其 `api_key` 或设置 `ANTHROPIC_API_KEY`。未启用供应商的空模型和密钥不影响启动。桌面首次启动仍默认使用 Ollama，其他供应商预设由程序目录提供，无需手工复制整份示例。



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

### 分类单词本与语境单词本

在「我的单词本 → 新建单词本」选择类型：

- **分类单词本**：按课程、主题或目标整理，继续使用通用释义。即使名称是「金融英语」，也不会自动启用金融语境。
- **语境单词本**：可选金融、法律、医药。所有供应商均使用内置专业提示词，优先输出相应专业释义和例句；没有专业义项时仍如实解释普通含义。

类型创建后固定，名称和说明仍可修改。同一专业可创建多本；要使用另一种语境，请另建单词本。新增词条不会自动从语境本复制释义，也不会把其他本的内容套入语境本；显式「复制」仍保留原释义。分类本之间保留原有的释义复用行为。已有释义、移动/复制的内容和学习记录不会自动重写，补全只填空缺字段。

语境类型随单词本身份同步，Drive v1 操作字段及复习算法不变；导出、恢复备份也保留类型。旧客户端仍可读取和复习，但只能按通用语境补全，因此请在所有需要专业补全的设备上更新客户端。

[查看语境单词本界面示例](docs/images/context-notebooks.png)（演示数据）。
