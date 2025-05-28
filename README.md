
# HofAutoBot2 项目说明文档

## 项目概述
HofAutoBot2 是一个基于 Python 和 Selenium 的游戏自动化工具，使用 PyQt5 构建图形界面，通过模拟用户操作来实现游戏的自动化。

## 核心组件

### 1. 启动界面（<mcfile name="start_up_window.py" path="/Users/wenguanggu/MyProjects/Python/HofAutoBot2/start_up_window.py"></mcfile>）
- 提供图形用户界面，包含服务器选择和操作控制
- 管理浏览器驱动实例和机器人线程
- 通过 `BotThread` 类在后台运行自动化任务

### 2. 自动化核心（<mcfile name="hof_auto_bot_main.py" path="/Users/wenguanggu/MyProjects/Python/HofAutoBot2/scripts/hof_auto_bot_main.py"></mcfile>）
- `HofAutoBot` 类：实现游戏自动化的核心逻辑
- `AutoBotConfigManager` 类：管理自动化配置，如体力消耗、BOSS挑战等参数
- 定义了多种游戏状态（BOSS战斗、PVP等）

### 3. 动作执行系统
#### 3.1 动作执行器（<mcfile name="advanced_action_executor.py" path="/Users/wenguanggu/MyProjects/Python/HofAutoBot2/scripts/advanced_action_executor.py"></mcfile>）
- `AdvancedActionExecutor`：动作执行器的抽象基类
- 实现了多种具体执行器：
  - `MainMenuActionExecutor`：主菜单操作
  - `SubMenuStageActionExecutor`：关卡选择
  - `SubMenuBossActionExecutor`：BOSS选择
  - `CharacterSelectActionExecutor`：角色选择
  - `ClearTeamActionExecutor`：清空队伍
  - `StartBattleActionExecutor`：开始战斗

#### 3.2 元素查找器（<mcfile name="advanced_element_finder.py" path="/Users/wenguanggu/MyProjects/Python/HofAutoBot2/scripts/advanced_element_finder.py"></mcfile>）
- `AdvancedElementFinder`：元素查找器的抽象基类
- 为每种操作类型实现专门的查找器
- 使用 XPath 和 NAME 定位器查找页面元素

### 4. 配置系统
#### 4.1 动作配置（<mcfile name="action_config_advanced.json" path="/Users/wenguanggu/MyProjects/Python/HofAutoBot2/configs/server_01/action_config_advanced.json"></mcfile>）
- 定义了各种自动化动作序列
- 包含动作名称、说明和具体步骤
- 支持多种动作类型：点击菜单、选择角色、开始战斗等

#### 4.2 循环配置（<mcfile name="auto_bot_loop_config.json" path="/Users/wenguanggu/MyProjects/Python/HofAutoBot2/configs/server_01/auto_bot_loop_config.json"></mcfile>）
- 设置游戏相关参数：体力消耗、恢复速度等
- 配置 BOSS 战循环顺序
- 设置关卡循环顺序
- 控制 PVP 和世界 PVP 参与

## 项目结构
```
├── configs/            # 配置文件目录
│   ├── server_01/     # 服务器1的配置
│   └── server_02/     # 服务器2的配置
├── scripts/           # 核心脚本目录
│   ├── actions/       # 动作相关实现
│   └── states/        # 状态管理
├── images/            # 图片资源
└── start_up_window.py # 程序入口
```

## 工作流程
1. 用户通过图形界面选择服务器并启动自动化
2. `BotThread` 在后台运行 `HofAutoBot`
3. `HofAutoBot` 根据配置文件执行相应的动作序列
4. 动作执行器和元素查找器协同工作，完成具体操作
5. 系统自动处理各种游戏状态，如 BOSS 战、关卡战斗等

## 扩展性
- 通过配置文件可以轻松添加新的动作序列
- 动作执行器和元素查找器使用工厂模式，易于扩展新功能
- 支持多服务器配置，可以针对不同服务器定制行为
        