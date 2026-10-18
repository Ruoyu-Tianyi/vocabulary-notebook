# 云端词汇本 · Drive Vocabulary Book

**本机运行词汇本，DeepSeek API 补全，Google Drive 同步词汇与学习记录。** 支持将新电脑作为日常主力、旧电脑作为备用，按法律、金融等课程创建独立单词本。

基于 **[Eric Zhou 的 Vocabulary Notebook](https://github.com/Eric-Zhou-0302/vocabulary-notebook)** 开发，保留原项目提交历史与 MIT 版权声明。原项目提供 FastAPI、React、AI 补全、FSRS 复习及导出；本项目扩展云同步、多单词本、逐次复习记录与冲突合并。[来源说明](NOTICE) · [原 README](docs/UPSTREAM_README.md) · [MIT License](LICENSE)

当前维护仓库为 **[Ruoyu-Tianyi/vocabulary-notebook](https://github.com/Ruoyu-Tianyi/vocabulary-notebook)**，它是原项目的 fork。`main` 提供完整云端版本；向原作者贡献的功能使用从原项目建立的独立分支。旧仓库 [drive-vocabulary-book](https://github.com/Ruoyu-Tianyi/drive-vocabulary-book) 保留历史并提示迁移。迁移只改变程序更新来源，沿用原来的安装目录、Drive 文件夹、词库、学习记录及本机密钥。

## 能做什么

| 你的使用场景 | 对应功能 |
|---|---|
| 上课遇到法律、金融等专业词汇 | 按课程创建单词本，填写领域说明；同一拼写可以在不同本中保存不同含义 |
| 想快速记词，添加后马上理解 | 只输入单词并保存，DeepSeek 自动补全音标、中文释义和例句，下方即时记忆区自动展示结果 |
| 回看刚学的词或查找旧词 | 列表默认最新添加在前，可搜索拼写与释义、筛选日期或首字母、切换时间与字母排序 |
| 希望长期记住，而不只是收集 | 今日复习按 FSRS 安排到期卡片；全部单词支持 A–Z 或随机翻卡，适合课前快速回顾 |
| 在两台私人电脑交替学习 | 同一 Drive 文件夹同步词汇、单词本和逐次复习记录；离线保存，恢复连接后合并 |
| 需要打印、整理或更换电脑 | 按条件导出 PDF / CSV / JSON；完整备份保留学习历史；Agent 更新提示词帮助保留数据升级 |

## 日常怎么用

### 1. 选择课程单词本

顶部三个醒目的入口分别是 **单词列表 → 添加单词 → 复习**，当前页面会高亮，复习入口的角标显示当前范围内待复习的数量。单词详情归在“单词列表”下。

主导航下方是紧凑的状态栏：左侧选择当前单词本，右侧查看 AI 和 Drive 连接状态。点击 **管理 → 新建单词本**，例如创建“法律英语”，并填写“合同法课程中的专业词汇”等说明，AI 补全时会参考这个领域。名称和课程说明可在 **管理 → 编辑当前单词本** 中修改。

选择“全部单词本”可以跨本浏览和复习；添加页仍需选择一个具体单词本作为保存位置。

### 2. 输入单词，边添加边记忆

进入 **添加单词**，确认“保存到”的单词本，输入英文单词或短语，按 Enter 或点击保存。单词立即保存，输入框清空后可继续录入；没有 API Key 或暂时离线也可以先记录。

新词入库时会将普通英文词的首字母改为小写，例如 `Contract` → `contract`；全大写缩写、单个大写字母及内部大小写保持原样，例如 `API`、`I`、`iPhone`、`McDonald`。只处理新添加的词，不批量改写旧词；专名需要特定大小写时，可在详情页编辑保留。

保存区下方的 **刚刚添加 · 即时记忆** 展示本页最近添加或再次查看的 10 个单词。若所选单词本已有相同拼写（忽略大小写），会直接展示原来的释义、音标和例句，并标记“单词本中已有”，不会新增词条、改变添加时间或复习记录，也不会自动重新调用 AI。同一个词反复输入会移到最前面，不会堆叠重复卡片；不同单词本的相同拼写分别处理。

新词的音标、释义和例句生成后自动出现，不必切回列表；切走或刷新页面会清空这块临时展示，已保存的单词仍在列表中。补全失败可以点击单条“重试补全”，也可在列表批量“补全缺失”。

添加页只保留单词输入，不需要先填写课堂释义。需要修正含义或采用老师的定义时，点击 **查看 / 编辑 → 编辑**，修改释义、音标、课程例句或所属单词本。已有的手动释义会保留。

### 3. 整理和查找

**单词列表** 默认“添加时间：最新在前”，也可选择最早在前、A→Z 或 Z→A，当前浏览器会记住选择。搜索框同时匹配拼写和释义；日期和首字母筛选帮助缩小范围，点击单词卡片查看详情。

“导出”支持 PDF、CSV 和 JSON，按当前单词本、关键词、日期及所选排序导出；首字母按钮仅用于屏幕列表筛选。PDF 适合打印，但中文显示取决于本机可用字体。需要备份全部单词本及复习历史时，使用 **同步与备份 → 下载完整备份**。

### 4. 复习并保留进度

**今日复习** 优先安排到期卡片，并按每日新词上限加入新词（默认 20）。先回忆，再点击卡片或按空格查看答案，以 **1 重来 / 2 困难 / 3 良好 / 4 简单** 评分；应用据此计算下次复习时间，并记录每次评分。没有释义的单词需要先补全或手动编辑，之后才会进入复习。

**全部单词** 可以按 A–Z 或随机顺序翻卡，使用左右方向键切换、空格翻面。这种快速回顾不写入 FSRS 评分，也不会改变下次到期时间。按 `?` 可查看键盘帮助，Esc 关闭帮助。

### 5. 在另一台电脑接着学

两台电脑各自安装程序，连接同一个 Drive 文件夹。状态栏的 **Drive 已连接** 表示应用已连接所选存储，点击 **同步** 可以立即合并，点击状态文字或右上角 **同步与备份** 查看连接、API 设置和备份工具。

文件夹模式下，待处理为 0 表示变更已写入本机 Drive 文件夹，实际上传下载由 Drive 桌面版完成。换电脑前确认桌面版同步结束；另一台收到文件后，应用默认每 30 秒自动合并。安装新电脑或更新现有电脑，直接复制下面对应的 Agent 提示词即可。

## Agent 安装提示词

在另一台电脑把下面整段复制给可操作本机的 Agent 即可。常规安装直接使用仓库附带的前端，无需 Node.js、Ollama 或模型文件。API Key 在该电脑的设置页输入。

```text
请在这台私人电脑上直接安装并配置“云端词汇本”，将这台电脑作为我的日常主力机。

GitHub 仓库：https://github.com/Ruoyu-Tianyi/vocabulary-notebook
请先读取最新 README 和适用的 AGENTS.md，然后实际执行安装，不要只给我步骤。

1. 检查操作系统、Git 和 Python 3.10+。缺少时通过官方渠道安装；遇到系统权限、登录或安装条款时说明需要我完成的具体步骤。Windows 默认使用 D:\000_Workspace\云端词汇本；D 盘不可用则使用用户 Documents 下的 drive-vocabulary-book。本程序放在本地非同步目录。
2. 克隆上述仓库的 main 分支。如果已存在这个项目，先检查工作区与远程，保留已有词库、配置和未提交修改，安全更新，不执行强制重置或覆盖。
3. 创建项目独立 .venv 并安装 requirements.txt。使用已包含的 frontend/dist，常规安装无需 Node.js。此版本使用 DeepSeek API，不安装 Ollama 或下载模型。
4. 检查是否已有 DEEPSEEK_API_KEY。没有时先启动应用，引导我在“同步与备份 → DeepSeek API 词汇补全”中自己输入 Key；不要让我把 Key 贴到聊天、命令行参数或仓库。默认模型 deepseek-flash，可按我的账号可用模型调整。Key 只留本机，各电脑分别配置，不复制另一台的 .secrets 或令牌。
5. 检测 Google Drive 桌面版，未安装时从 Google 官方渠道安装并引导我登录；系统不支持桌面版时，说明情况并参考 README 的 Drive API 方案。找到同一 Google 账号已有的“我的云端硬盘/Drive Vocabulary Book”文件夹，等待完整下载并设为可离线使用，然后通过设置页连接它在本机的绝对路径。不同电脑的盘符可以不同。不要另建同名空词库，不要覆盖或清空云端 library.json / vocabulary-*.json。如果尚未登录、授权或尚未出现已有文件夹，只暂停这项并告诉我需要完成的步骤，继续其他安装工作。
6. 启动词汇本，访问 http://127.0.0.1:1400，确认已有“法律英语”“金融英语”等单词本从云端恢复。同步采用双向合并，新电脑作为主力不需要清空或禁用旧电脑。保留两台各自的 words.json 本地缓存。
7. 检查 /api/health、/api/sync/status 和浏览器错误。Key 未配置时应标记为待配置，仍能手动保存和同步。连接检测不发送收费的生成请求；需要测试真实词汇补全时，使用我指定的一个词验证，保留我的正式词汇与学习进度。没有 Key 时不要声称真实 DeepSeek 调用已通过。
8. 完成后告诉我本机安装目录、启动方式、Drive 路径、当前 AI 配置状态、检查结果及任何仍需我处理的事项。默认无需创建远程部署、开机自启或推送任何个人数据。
```

## Agent 更新提示词

### 已配置用户：快速更新

已经安装并配置好 Drive、DeepSeek API 的电脑，直接复制这一段。无需重新安装、授权或填写 Key；两台电脑各执行一次即可。

```text
请直接更新本机已安装的“云端词汇本”：https://github.com/Ruoyu-Tianyi/vocabulary-notebook
读取最新 README 的更新约定，在原安装目录执行：完成同步 → 只停止本项目进程 → 用 maintenance.py backup 创建本地备份 → 检查 Git 状态并快进更新到 origin/main → 按需更新原虚拟环境依赖，使用附带 frontend/dist → 启动前运行 maintenance.py verify --backup <实际备份路径> → 原方式重启并检查词库、复习进度、API 和 Drive 状态。
沿用现有单词本、学习记录、配置、环境变量及密钥，不重新配置 Drive/API、不清空或覆盖数据、不调用收费生成。若旧仓库地址、未提交修改、冲突或校验失败，按 README 完整流程保留现场处理，不强制重置。正常完成后只汇报旧/新提交、备份位置和检查结果。
```

### 首次迁移或异常排查：完整提示词

旧仓库迁移、版本较旧或需要逐步排查时使用以下完整流程。每台电脑分别更新程序，继续连接原来的 Drive 文件夹。程序和数据分开保存，当前数据格式版本为 1。

```text
请直接更新这台电脑上已经在使用的“云端词汇本”，获取新功能并保留我的全部单词本、词汇、逐次评分、FSRS 进度、删除记录、API Key 和 Drive 连接。

仓库：https://github.com/Ruoyu-Tianyi/vocabulary-notebook
目标：更新现有安装到 origin/main，不重新创建词库，不将另一台电脑的数据文件整份覆盖到本机。

1. 找到现有安装目录、应用启动方式、VOCAB_DATA_FILE（若设置）、config.json 和 sync.credentials_dir（默认 .secrets）。读取 README、适用的 AGENTS.md、Git 状态与当前提交，检查 origin。若仍指向旧仓库 Ruoyu-Tianyi/drive-vocabulary-book，先记录旧地址并保留为 legacy 远程，再把 origin 切换到上述 fork；如果 legacy 已存在则先检查其地址，不覆盖其他远程。其他不明来源不要擅自替换。保留现有用户环境变量，不回显任何 API Key 或令牌。
2. 若应用正在运行，先通过本机页面完成一次同步，记录状态及词库/学习记录数量。文件夹模式还要确认 Google Drive 桌面版上传完成。离线时必须保留所有未同步变更，在报告里说明，不能清空缓存或待同步记录。
3. 只停止这个安装目录对应的词汇本进程，保留其他程序。先创建升级前本地备份：已有 maintenance.py 时，使用项目 .venv 中的 Python 执行 maintenance.py backup，记录返回的备份路径与旧提交。工具会备份词库及其已有备份、config.json、完整的本机凭据目录，并验证复制结果。备份包含密钥，不能上传到 Drive、GitHub 或聊天。
4. 如果旧版本没有 maintenance.py，则在项目外新建本地时间戳备份目录，用文件复制保存上述数据、配置及凭据，并记录每个源文件的 SHA-256、原路径、旧提交和词库/评分数量。保留备份直到更新验收结束。不能先更新再把新状态当作升级前备份。
5. 获取远程代码并确认现有提交是 origin/main 的祖先后，用 git pull --ff-only origin main 更新现有工作区，设置 main 跟踪新的 origin/main。存在未提交修改、分支分叉或冲突时，保留现场并说明冲突，不强制重置、不清理未跟踪文件，也不覆盖 config.json、words.json、.secrets、.backups 或云端变更文件。旧仓库迁移同样走这个流程，不另行克隆覆盖现有安装。
6. 使用原 .venv 安装 requirements.txt，使用仓库附带的 frontend/dist。前端只有在修改源码或构建产物缺失时才安装开发依赖并重新构建。保留本机 DeepSeek 模型设置、Key 与原 Drive 目录，不复制示例配置覆盖真实配置。
7. 启动前先校验：已有工具备份使用 maintenance.py verify --backup <第 3 步返回的本地路径>；手动备份则比较第 4 步所有原文件的 SHA-256 和词库统计。发现文件丢失、变化或版本不兼容时停止启动，保留新旧文件供检查。不要静默恢复快照覆盖可能更新过的数据。
8. 用原启动方式重启并刷新浏览器，确认原单词本与学习记录可读取、DeepSeek 设置保留、Drive 仍连接原目录。检查“添加后即时释义”和“添加时间：最新在前”选项。常规升级不需要新建测试词或发送收费 AI 请求；如确需生成测试，先使用我指定的一个词。
9. 继续同步并检查结果；正常云端合并可能带来其他电脑的新词、评分或删除，不要因数量变化而用旧快照回灌云端。若失败，保留备份、日志和新旧提交，说明失败环节；必要时回退程序版本，恢复数据前先确认不会覆盖更新后的记录。
10. 汇报旧/新提交、备份路径、文件一致性检查、原词库与学习记录检查、AI/同步状态和未解决事项。两台电脑各自更新程序即可继续同步，不需要重新授权已有 Drive 文件夹。
```

### 更新工具

先停止应用，在项目目录运行（Windows）：

```powershell
.\.venv\Scripts\python.exe maintenance.py backup
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe maintenance.py verify --backup ".backups\update-上一步返回的时间戳目录"
.\start.bat
```

`verify` 的路径使用 `backup` 实际返回值。macOS / Linux 换成 `.venv/bin/python`。备份默认在本机 `.backups/`，包含私密配置，已加入 Git 忽略；工具拒绝对正在使用的缓存进行备份或校验。它检查备份与原文件的 SHA-256，并比对词汇、单词本、评分事件和 FSRS 统计；不会自动恢复文件、请求 AI 或写入云端。校验应在应用重新启动前执行。

## Windows 快速启动

安装 [Python 3.10+](https://www.python.org/downloads/)，然后：

```powershell
git clone https://github.com/Ruoyu-Tianyi/vocabulary-notebook.git
cd vocabulary-notebook
.\start.bat
```

首次运行自动创建虚拟环境并安装依赖。前端构建产物已包含在仓库中，日常使用不需要 Node.js。浏览器访问 **http://127.0.0.1:1400**。

已安装依赖可直接运行 `.venv\Scripts\python.exe app.py`。升级后安装新依赖：`powershell -ExecutionPolicy Bypass -File .\start.ps1 -Install`。

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## DeepSeek API 配置

从 [DeepSeek 平台](https://platform.deepseek.com/api_keys) 创建 API Key，在“同步与备份 → DeepSeek API 词汇补全”填写并保存。Key 写入本机 `.secrets/deepseek.json`，页面不回显，且不进入 Drive 或 Git。每台电脑各自配置；修改后立即生效。

也支持启动进程的环境变量 `DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`。优先级为环境变量 > 本机设置页 > `config.json`。`config.json.example` 可复制为 `config.json`，示例中的空 Key 不影响启动。

默认使用当前官方模型名 `deepseek-flash`，请求 `https://api.deepseek.com/chat/completions`，采用 JSON Output 并关闭深度思考。可在设置页填写其他账号可用模型。[官方接入说明](https://api-docs.deepseek.com/) · [JSON 输出](https://api-docs.deepseek.com/guides/json_mode/) · [思考开关](https://api-docs.deepseek.com/guides/thinking_mode/)

补全会把当前单词与单词本的领域说明发送给 DeepSeek，并按其 API 规则计费；不会上传整本词库或复习历史。连接检查通过 `GET /models` 完成，不生成词汇。没有 Key、断网、鉴权失败或额度不足时，手动保存、同步和已有词汇复习仍可用；恢复后点击“补全缺失”。从旧 Ollama 版本更新时会在内存中切换到 DeepSeek，保留原有同步与复习配置。

## 同步方式一：Drive 桌面同步文件夹（推荐）

无需 Google Cloud 项目和 OAuth 客户端。

1. 两台电脑安装[桌面版 Google Drive](https://support.google.com/drive/answer/10838124?hl=zh-Hans)，登录同一个私人账号。
2. 在“我的云端硬盘”新建专用文件夹，例如 `Drive Vocabulary Book`，将它设为“可离线使用”。
3. 进入“同步与备份”，填写本机绝对路径，例如 `G:\我的云端硬盘\Drive Vocabulary Book`，点击“连接同步文件夹”。第二台电脑选择**同一个云端文件夹**，本机盘符可以不同。
4. 各自在本机运行程序。应用默认每 30 秒读取并合并变更。

**“待写入文件夹为 0”表示变更已交给 Drive 桌面版；实际上传/下载由桌面版完成。关闭电脑前还应确认 Drive 的同步状态为已完成。** 另一台电脑收到文件后，应用下一轮自动合并。

两台电脑的程序目录、`.venv`、`.secrets` 和 `words.json` 分别留在本机。云端目录只保存 `library.json` 身份标识及不可变的 `vocabulary-*.json` 变更文件。不要将整个项目或 `.secrets` 放入同步目录，不要手动编辑/删除变更文件。

ChatGPT 的 Drive 插件可帮助聊天读写文件，这个独立应用不依赖 ChatGPT 持续运行，也不读取或导出聊天插件的授权令牌。[OpenAI 插件授权说明](https://developers.openai.com/plugins/build/auth)

## 同步方式二：Drive API 直连（可选）

适合不安装 Drive 桌面版的电脑。与文件夹方式二选一，在设置中断开后可切换。

1. 在 [Google Cloud](https://console.cloud.google.com/apis/library/drive.googleapis.com) 创建项目并启用 Google Drive API。
2. 配置 OAuth 同意屏幕，个人测试时把自己的账号加入测试用户。
3. 创建 **桌面应用** OAuth 客户端，下载 JSON。
4. 在设置中导入 JSON，点击“连接 Google Drive”→“继续 Google 授权”。
5. 两台电脑使用**同一客户端 JSON、同一 Google 账号**各自授权，不要复制 `token.json`。

只申请 `drive.appdata` 权限，数据存于应用专属的隐藏 `appDataFolder`，不出现在普通 Drive 文件列表，也不访问其他文件。[Google 文档](https://developers.google.com/workspace/drive/api/guides/appdata)

授权采用本机回调、随机 state 和 PKCE。令牌仅保存在 `.secrets/token.json`。Google 测试应用的授权可能按 Google 发布状态/策略失效；应用会保留离线修改并提示重新授权。账户空间、API 配额和网络仍适用。

## 两台电脑如何合并

```text
电脑 A：本地界面 → 原子保存缓存 → 追加变更文件
                                   ↕ Google Drive
电脑 B：本地界面 ← 合并并重算 FSRS ← 读取变更文件
```

- 不用整份词库覆盖云端。每个变更有独立 ID，重试、重启和重复传输不会重复评分。
- 不同字段的编辑同时保留。同一字段同时编辑，按 Lamport 时钟、设备 ID、操作 ID 的固定顺序选择一致结果，不以电脑墙上时间决定先后。
- 每次复习是独立事件，按时间与事件 ID 排序重算 FSRS，两台电脑的评分均保留。请保持系统时钟正确。
- 删除优先于旧设备的编辑和评分，避免单词复活。重新添加会生成新 ID。
- 同步为最终一致，两个设备同时写入后，下一轮读取收敛；尚未上传的修改不会出现在另一台电脑。
- 两台电脑离线分别新建同一拼写时，保留两条独立记录，避免误合并课程含义与学习记录。同步后可检查并删除重复项。
- 当前不自动压缩历史或清理删除标记，以支持长期离线设备。适合私人词库，变更文件会随使用增长。

## 备份、迁移与恢复

“同步与备份”里的**完整备份**包含全部单词本、字段变更、删除标记和每次复习事件。导入时合并，不覆盖现有数据，也保留删除标记。

从原项目迁移：导入原 `words.json`，或首次启动前复制到本项目根目录。旧 FSRS 状态作为基线保留；旧版本未记录的逐次评分无法补造。自动迁移前保留 `words.json.legacy.bak`。原格式导入时，已有 ID 跳过。

单词列表的 JSON/CSV/PDF 导出只含当前筛选结果，需要全部历史时请用设置中的完整备份。本地每 10 分钟另存 `words.json.bak`。损坏文件会保留并停止读取，不会用空词库覆盖云端。

## 配置与安全

```json
{
  "provider": "deepseek",
  "deepseek": {"model": "deepseek-flash", "api_key": ""},
  "srs": {"daily_new_limit": 20},
  "sync": {"interval_seconds": 30, "credentials_dir": ".secrets"}
}
```

只监听 `127.0.0.1:1400`，限制 Host 与修改请求来源；不用于公开部署。一个本地缓存只允许一个进程打开。真实配置、词库、备份和令牌被 Git 忽略。同步文件为 JSON，文件夹模式沿用文件夹的现有共享权限，请使用私人文件夹。

测试可用 `VOCAB_DATA_FILE` 指定独立本地缓存。不要把个人词库、令牌或完整备份提交到公共仓库。

## 开发与验证

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
cd frontend
npm ci
npm run build
```

前端修改后必须重新构建。上游误提交的 `node_modules` 已从版本管理移除。测试覆盖双设备编辑与复习合并、删除、离线重试、文件夹重启、Drive HTTP 模拟及备份恢复。真实 API 直连需要自己的 Google OAuth 客户端。

核心扩展：`sync_storage.py`（变更与 FSRS 重放）、`drive_sync.py`（文件夹、Drive API、OAuth）、`instance_lock.py`（本地单进程保护）、`frontend/src/Books.jsx` 和 `frontend/src/pages/Settings.jsx`。
