<!--
Sync Impact Report
- Version change: (initial) → 1.0.0
- Modified principles: N/A (initial ratification)
- Added sections: Core Principles (5), Technology & Runtime Constraints, Development Workflow, Governance
- Removed sections: N/A
- Templates requiring updates:
  - ⚠ pending: .specify/templates/plan-template.md (Constitution Check section should reference principles below)
  - ⚠ pending: .specify/templates/spec-template.md (no immediate change required)
  - ⚠ pending: .specify/templates/tasks-template.md (no immediate change required)
- Follow-up TODOs:
  - TODO(RATIFICATION_DATE): 真实首次约定时间未知，暂用本次 spec-kit 接入日期占位
-->

# HofAutoBot2 Constitution

## Core Principles

### I. 中文优先 (Chinese-First Output)

所有用户可见输出 MUST 使用中文，包括 GUI 标签、CLI 提示、日志消息、异常信息与代码注释。
英文仅允许出现在标识符、库名、配置键、第三方 API 字段以及不可避免的技术术语中。
原因：项目使用者与维护者均以中文为母语，混合语言会降低可读性与一致性。任何 PR
若引入英文用户面文案，MUST 在评审中替换为中文。

### II. 状态机驱动的执行流 (State-Machine Driven Execution)

业务流程的控制流 MUST 通过 `scripts/states/` 下的状态对象表达，由 `HofAutoBot.run_once()`
分派给 `current_state.process()`，状态切换 MUST 调用 `self.set_state(next_state)` 或
`switch_to_next_state(...)`。禁止在 manager / executor 层私自驱动控制流转。
新增状态 MUST 通过 `StateFactory` 创建实例以避免循环导入。
原因：状态机模式是项目运行可观测、可暂停、可恢复的基础；任何短路这一模型的写法
都会破坏 GUI/CLI 的暂停-恢复语义与异常回退行为。

### III. 配置外置 (Externalized Configuration)

游戏元数据、动作组、循环参数、Boss/Stage 列表、账号信息 MUST 写入 `configs/` 下对应
JSON 文件，**绝不**硬编码到代码中。每个服务器的私有配置 MUST 放在 `configs/server_{id:02d}/`。
代码访问配置 MUST 通过 `ServerConfigManager` 与 `AutoBotConfigManager`，禁止直接 `json.load`
绕过类型化访问。
账号文件 `account_config.json`、角色快照 `character_config.json`、抓取的源码
`source_codes/source_code_character_*` MUST 保持 `.gitignore` 中，**绝不**入库。
原因：多服务器并行运行与隐私要求决定了配置必须可按服切换、敏感信息必须留在本地。

### IV. 双入口对等 (CLI / GUI Feature Parity)

`start_up_window.py`（GUI）与 `scripts/start_up_cli.py`（CLI）是项目的两条平等入口。
任何影响运行流程的功能（暂停/恢复、重载配置、状态查询、停止）MUST 在两条入口上
行为一致。CLI 入口在 headless / 容器场景下 MUST 可独立运行，禁止依赖任何 PyQt5
模块——`PyQt5` 仅允许出现在 `start_up_window.py` 及 `scripts/*_editor.py` 等 GUI 文件中，
CLI 链路（`start_up_cli.py` → `hof_auto_bot_main.py` → `scripts/states/` →
`scripts/advanced_*`）MUST 保持对 PyQt5 零依赖。
原因：CLI 路径要在 Docker / NAS 部署，PyQt5 是 ~200MB 的 GUI 框架，污染该路径会让
镜像膨胀且无法在 headless 环境运行。

### V. 简单优先与外科手术式改动 (Simplicity & Surgical Changes)

实现 MUST 是解决问题的最小代码：不要为单次使用的逻辑引入抽象，不要为不会发生的场景
加错误处理，不要给"未来可能要"的能力提前埋钩子。修改既有文件时 MUST 只触动与任务
直接相关的行；禁止顺手"美化"无关代码、改格式、删除非自己引入的死代码。
注释默认不写；仅当 WHY 不显然（隐藏约束、不变量、外部 bug 的 workaround）时才写一行。
禁止解释 WHAT 或引用调用方（"used by X", "added for Y"）。
原因：项目长期由单人维护，代码膨胀与误伤式改动是最大的回归风险源。

## Technology & Runtime Constraints

**Python 与依赖**
- Python 3.9+，依赖锁定在 `requirements.txt`，新增依赖 MUST 同步加入该文件。
- 关键栈：`selenium`（驱动 Chrome）、`PyQt5`（仅 GUI）、`opencv-python-headless` + `pytesseract`
  + `Pillow`（验证码 OCR）、`webdriver-manager`（本地驱动管理）、`beautifulsoup4` + `requests`
  （HTTP 抓取与 HTML 解析）。

**浏览器与 OCR**
- Chrome / Chromium MUST 由调用方安装；CLI 路径优先使用 `CHROME_BIN` 与 `CHROMEDRIVER_PATH`
  环境变量指向的二进制，未设置时回退到 `ChromeDriverManager().install()`。
- Tesseract OCR 二进制由 `_ensure_tesseract_path()` 在 `/opt/homebrew/bin`、`/usr/local/bin`、
  `/usr/bin` 中自动探测，或由 `TESSERACT_PATH` 环境变量覆盖。

**HTML 抓取**
- `battle_watcher_manager.py` 直接对 `page_source` 做正则匹配，**不使用** DOM 选择器。
  游戏 HTML 结构变化 MUST 通过修改该文件的正则模式应对，禁止改为复杂的解析器。

**日志**
- 所有日志通过 `LogManager.get_instance()` 单例输出到 `logs/log_server_{id}.txt`，
  新条目置顶。控制台输出使用 ANSI 颜色。禁止使用裸 `print` 输出运行时事件
  （脚本初始化阶段除外）。

**进程模型与多实例**
- CLI 默认 PID 文件按 server-id 分隔为 `hof_auto_bot_server_{id}.pid`，保证多服并存。
- `--stop` MUST 配合 `--server-id` / `--server-name` / `--pid-file` 使用，不允许误伤其他进程；
  `--status` 不传参时扫描所有 PID 文件并列出存活进程。

## Development Workflow

**改动前**
- 复杂或非平凡任务 MUST 先在对话里明确假设、可选方案、成功标准，再动手。
- 涉及 ≥3 步或多文件的工作 MUST 用 TaskCreate/TaskUpdate 追踪进度。

**改动中**
- 优先 `Edit` 既有文件，不新建文件除非必要。
- 不创建 README/文档文件，除非用户明确要求。
- UI 或前端改动 MUST 在浏览器中实际操作过再报告完成；不能仅靠类型检查/测试通过就声称成功。

**Git 协作**
- 提交 MUST 由用户明确请求后再执行；不自作主张 commit。
- 禁止 `--no-verify`、`--force` 推送 main、`reset --hard` 等危险操作，除非用户显式授权。
- 每次提交 MUST 仅包含与本次任务直接相关的文件；运行时产物（PID、character_config、
  source_codes、wdm 缓存）禁止入库。
- Commit message 风格遵循仓库习惯（`feat(...)`、`fix(...)`、`chore(deps)` 等中文描述）。

**测试与验证**
- 项目当前未强制 TDD；测试位于 `tests/` 和顶层 `test_*.py`。新增涉及解析、状态机分支、
  配置加载的代码 SHOULD 补单元测试。
- 改动 CLI/GUI 行为后 SHOULD 至少手动跑一遍对应入口；改动验证码、登录、断线重连
  SHOULD 在真实服务器上验证。

## Governance

1. 本宪法凌驾于个人偏好之上。CLAUDE.md 中的 "Behavioral Guidelines" 与本宪法一致；
   当两者出现冲突时，以本宪法为准并同步更新 CLAUDE.md。
2. 修订流程：
   - PATCH：措辞、错别字、格式微调。
   - MINOR：新增原则、扩展约束、新增 Section。
   - MAJOR：移除原则、改变核心约束语义（如允许 CLI 引入 PyQt5）。
3. 每次修订 MUST 在文件顶端的 Sync Impact Report HTML 注释里记录版本变更、影响的模板与
   待跟进 TODO；MUST 更新 `Last Amended` 日期。
4. 评审任何变更时 MUST 对照本宪法逐条检查。若某次合理改动确需偏离原则，PR/对话中
   MUST 显式说明偏离原因，并考虑是否需要修订宪法。

**Version**: 1.0.0 | **Ratified**: 2026-05-25 | **Last Amended**: 2026-05-25
