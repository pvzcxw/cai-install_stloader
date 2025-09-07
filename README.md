# cai install

![Python 3.7+](https://img.shields.io/badge/Python-3.7%2B-blue)

![License-GPLv3](https://img.shields.io/badge/License-GPLv3-green)

Cai Install是一款强大的Steam游戏清单管理工具，支持多种解锁方案（SteamTools和GreenLuma），能够从多个清单库自动下载并安装游戏清单文件。

功能亮点
🚀 多源清单支持：从多个清单库获取游戏清单文件

🧩 智能适配：自动检测并适配SteamTools或GreenLuma

🔍 灵活搜索：通过AppID、游戏名称或Steam链接搜索游戏

📦 批量处理：支持同时处理多个游戏的清单文件

🔄 格式转换：自动转换.st文件为SteamTools可用的.lua脚本

🛡️ 安全可靠：开源透明，定期更新

使用指南：
安装依赖：
pip install -r requirements.txt

运行程序
python "frontend.py"

操作流程
1.输入游戏AppID、Steam链接或游戏名称

2.选择清单查找方式：

  从指定清单库中选择

  使用游戏名称搜索清单

3.选择要使用的清单库

4.程序自动下载并处理清单文件

5.根据检测到的解锁工具自动配置

支持的清单库：
GitHub清单库	社区	多个社区维护源
多个zip get   稳定可靠

配置文件说明：
配置文件位于config.json：

{
    "Github_Personal_Token": "您的GitHub个人访问令牌",
    "Custom_Steam_Path": "自定义Steam路径",
    "QA1": "温馨提示: Github_Personal_Token可在Github设置中找到"
}

技术架构

![deepseek_mermaid_20250623_e5cb84](https://github.com/user-attachments/assets/97789e67-86e6-45f7-b139-5b5151131ad1)


常见问题
Q: 如何获取GitHub个人访问令牌？
A: 在GitHub设置中创建个人访问令牌，勾选repo权限即可。

Q: 支持哪些解锁工具？
A: 目前完美支持SteamTools和GreenLuma 2025

Q: 如何批量添加多个游戏？
A: 输入AppID时用英文逗号分隔多个ID。

免责声明

⚠️ 本工具仅用于学习交流目的

⚠️ 请勿用于盗版或非法用途

⚠️ 使用可能导致Steam账号受限

⚠️ 支持开发者，请购买正版游戏

贡献指南
欢迎提交PR改进项目：

Fork本项目

创建特性分支 (git checkout -b feature/AmazingFeature)

提交更改 (git commit -m 'Add some AmazingFeature')

推送分支 (git push origin feature/AmazingFeature)

创建Pull Request

许可证

本项目采用GNU General Public License v3开源许可证。
