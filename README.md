# HofAutoBot

HofAutoBot是一个用于角色管理的自动化工具，提供标签管理、角色管理等功能。

## 功能特点

- 标签管理系统
  - 支持自定义标签ID和名称
  - 64种预设颜色，按色系分类
  - 可视化的标签编辑界面
  - 配置的保存与加载

## 安装

1. 克隆仓库
```bash
git clone https://github.com/yourusername/hofAutoBot.git
cd hofAutoBot
```

2. 创建虚拟环境（推荐）
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

## 使用说明

### 标签管理

1. 创建新标签
   - 输入标签ID和名称
   - 从预设颜色中选择所需颜色
   - 点击"新建"按钮

2. 编辑标签
   - 在列表中选择要编辑的标签
   - 修改相关信息
   - 点击"更新"按钮

3. 删除标签
   - 选择要删除的标签
   - 点击"删除"按钮

4. 配置管理
   - 使用"保存配置"保存当前标签设置
   - 使用"读取配置"加载已保存的设置
   - 使用"清空所有"清除所有标签

## 项目结构

```
hofAutoBot/
├── tag/                # 标签管理模块
│   ├── models.py      # 数据模型
│   ├── gui.py         # 界面实现
│   └── manager.py     # 管理逻辑
├── config/            # 配置文件目录
├── docs/             # 文档目录
└── requirements.txt  # 项目依赖
```

## 文档

详细的开发文档和说明请参考 [docs/tag_management_memo.md](docs/tag_management_memo.md)。

## 贡献

欢迎提交问题和改进建议！

## 许可证

本项目采用 MIT 许可证。 