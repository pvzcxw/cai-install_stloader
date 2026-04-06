# 🚀 Cai-Install STLoader (Cai Install XP)

![Version](https://img.shields.io/badge/Version-1.64p1-blue)
![License](https://img.shields.io/badge/License-GPLv3-green)
![Python](https://img.shields.io/badge/Python-3.8+-yellow)

**Cai Install** 是一款专为 Steam 解锁工具（如 SteamTools、GreenLuma）量身打造的全自动游戏清单（Manifest）及密钥（DepotKey）下载、配置与入库辅助工具。

通过高度自动化的脚本逻辑，本工具可以一键完成：**获取应用ID -> 检索全网清单库 -> 下载解压 -> 解密/转换格式 -> 合并密钥 -> 写入解锁配置** 的完整工作流，彻底解放玩家的双手。

本项目完全开源免费，采用 GNU GPL v3 许可证。**请勿用于商业用途，严禁倒卖！**

---

## 🛑 严正声明与防骗警告

**本项目完全免费！完全开源！如果您是花钱购买的本软件，说明您已经被骗了！**

软件作者与部分无良倒卖者（如B站同名“玩家资源站”、“沧海颐粟/地球一朵花”等）毫无关系。这些人长期盗用开源社区的免费工具，加入卡密弹窗甚至伪装作者进行收费倒卖。请广大玩家擦亮眼睛，坚决抵制，遇到收费请直接举报！

免责声明：
1. 本项目仅供编程学习、网络协议研究与技术交流使用。
2. 请支持正版游戏。由于使用本辅助工具造成的任何 Steam 账号红信、封禁或数据损失，作者概不负责。

---

## ✨ 核心功能详解

### 1. 🔍 智能环境检测与适配
*   **全自动寻址**：自动读取注册表，精准定位 Steam 安装目录。
*   **双环境兼容**：智能识别当前系统运行的是 **SteamTools** 还是 **GreenLuma**。
    *   *SteamTools*：自动转换 `.st` 加密清单，生成或追加 `.lua` 解锁脚本至 `stplug-in` 目录。
    *   *GreenLuma*：自动将解密密钥（DepotKey）合并至 Steam 根目录的 `config/config.vdf` 文件中，并自动更新 `AppList`。
*   **防冲突机制**：如果检测到两款解锁工具同时存在，程序会触发安全拦截，要求用户清理环境，避免配置污染。

### 2. 🧩 进阶解锁支持 (DLC 与 创意工坊)
*   **全 DLC 智能补全**：程序会交叉比对 `DDXNB`、`SteamCMD API` 和 `Steam Store API`，智能筛选出无独立 Depot 的免费或扩展 DLC，并将其 ID 无缝合并到您的解锁脚本中。
*   **创意工坊 (Workshop) 极速入库**：支持直接输入创意工坊物品 URL 或 ID，自动解析其所属游戏，修补 `DepotKey`，并下载对应清单。SteamTools 用户开启此功能后，即可直接在客户端内正常下载订阅的 MOD。

### 3. 📦 庞大且可扩展的清单源
*   **内置海量资源**：集成 SWA V2、Cysaw、Furcate、Walftech、SteamDatabase、ManifestHub(2)、Sudama、清单不求人等知名且优质的 ZIP 与 GitHub 资源库。
*   **支持自定义源**：高级用户可通过修改 `config.json`，无缝接入私有的 GitHub 仓库或第三方的 ZIP 直链下载服务。

### 4. ⚡ 网络优化与动态更新
*   **境内镜像加速**：自带 IP 归属地检测，当识别为中国大陆网络时，自动启用多节点 `gh-proxy`、`fastgit` 等 GitHub 镜像加速下载。
*   **ST 浮动版本控制**：为 SteamTools 用户提供“自动更新清单”选项。开启后，生成的 lua 脚本将不锁定特定版本号（注释掉 `setManifestid`），由 SteamTools 自身接管后续的清单版本浮动更新。
*   **本体自更新**：内置版本检查器，发现 GitHub Release 有新版本时，会弹出友好的 UI 界面提示更新日志并引导下载。

### 📸 界面展示 (Screenshots)

这里是 Cai Install XP 的实际运行界面：

<div align="center">
  <!-- 如果你用的是方法一，把下面的链接换成相对路径，比如 assets/main.png -->
  <!-- 如果你用的是方法二，把下面的链接换成 GitHub 自动生成的链接 -->
  <img src="https://github.com/pvzcxw/cai-install_stloader/blob/main/assets/Screenshot_20260406_095718.jpg" width="800" alt="主界面">
</div>

---

## 🛠️ 安装与运行指南

### 前置条件
本工具基于 Python 开发，运行前请确保您的电脑已安装 **Python 3.8 或更高版本**。

### 1. 克隆/下载项目
您可以直接下载仓库的 ZIP 压缩包并解压，或使用 Git 克隆：
```bash
git clone https://github.com/pvzcxw/cai-install_stloader.git
cd cai-install_stloader
```

### 2. 安装依赖包
在项目根目录打开命令行（CMD 或 PowerShell），运行以下命令安装必要的运行库：
```bash
pip install aiofiles colorlog httpx ujson vdf colorama
```

### 3. 运行程序
确保 `backend.py` 和 `frontend_cli.py` 位于同一目录下，执行前端入口文件：
```bash
python frontend_cli.py
```

---

## 🎮 详细操作流程

启动程序后，您将看到精美的字符画主菜单。基本操作流程如下：

1. **选择主菜单功能**：
   *   输入 `1` 进入 **普通游戏入库** 流程。
   *   输入 `2` 进入 **创意工坊清单入库** 流程。
2. **输入游戏信息**：
   *   支持直接输入 **AppID**（如 `1086940`）。
   *   支持输入 **Steam 商店或 SteamDB 链接**。
   *   支持输入 **游戏中文/英文名称**（如 `博德之门3`），程序会自动调用 API 进行搜索并提供多选列表。
   *   *提示：支持批量输入，用英文逗号 `,` 分隔即可。*
3. **配置入库参数**（仅针对游戏入库）：
   *   **是否启用 ST 自动更新清单？**（输入 y/n）。如果是带有 Denuvo 加密的游戏，建议选 `n`（锁定版本）；普通游戏建议选 `y`。
   *   **是否额外入库所有可用 DLC？**（输入 y/n）。
   *   **是否修补创意工坊密钥？**（输入 y/n）。
4. **选择清单来源**：
   *   选择 `1` 查看并选择具体的清单库（如 SWA V2、Sudama 等）。
   *   选择 `2` 启动 GitHub 全库地毯式搜索。
5. **等待执行完成**：
   *   程序将输出彩色的运行日志。看到“处理成功”并提示“已生成解锁文件”后，**完全重启 Steam 客户端**即可畅玩。

---

## ⚙️ 配置文件 (`config.json`) 高级指南

首次运行程序后，会在同级目录下自动生成 `config.json` 文件。使用记事本或代码编辑器打开，您可以进行深度定制：

```json
{
  "Github_Personal_Token": "",
  "Custom_Steam_Path": "",
  "Force_Unlocker": "",
  "Custom_Repos": {
    "github":[
      {
        "name": "我的私有GitHub库",
        "repo": "YourName/YourRepo"
      }
    ],
    "zip":[
      {
        "name": "我的私有ZIP网盘",
        "url": "https://api.my-server.com/download/{app_id}.zip"
      }
    ]
  }
}
```

### 核心参数解析：
*   **`Github_Personal_Token`**: **【强烈建议配置】** 填入您的 GitHub 个人访问令牌（Personal Access Token）。未配置时，GitHub API 每小时仅允许请求 60 次，极易触发速率限制（Rate Limit）；配置后上限提升至 5000 次/小时。*(获取方式：GitHub 设置 -> Developer settings -> Personal access tokens -> Generate new token)*。
*   **`Custom_Steam_Path`**: 当您的 Steam 注册表损坏，或安装了绿化版 Steam 时，程序可能无法自动找到 Steam 目录。在此处填入绝对路径（如 `D:\\Games\\Steam`，注意转义斜杠）即可强制指定。
*   **`Force_Unlocker`**: 强制指定使用的解锁器逻辑。填入 `"steamtools"` 或 `"greenluma"`。留空为智能检测。
*   **`Custom_Repos`**: 
    *   **`github` 数组**: 格式为 `{"name": "显示名称", "repo": "拥有者/仓库名"}`。
    *   **`zip` 数组**: 格式为 `{"name": "显示名称", "url": "下载链接"}`。注意：链接中必须包含 `{app_id}` 作为占位符，程序在运行时会自动将其替换为当前处理的游戏 ID。

---

## ❓ 常见问题解答 (FAQ)

**Q: 为什么提示 "GitHub API请求次数已用尽"？**  
**A:** 您所在 IP 的 GitHub 公共接口请求额度已达上限。解决方法：打开 `config.json`，在 `Github_Personal_Token` 处填入您的 GitHub Token 即可解决。

**Q: 为什么入库成功了，重启 Steam 后游戏依然显示“购买”？**  
**A:** 可能的原因有：
1. 您选择的清单库中该游戏的清单已失效或未收录。尝试在步骤 4 时更换其他清单库（如从 SWA V2 换成 Cysaw）。
2. SteamTools 未能正确挂载，请检查 ST 客户端的状态。
3. 您输入了错误的 AppID。

**Q: "修补创意工坊密钥" 是什么意思？**  
**A:** 许多解锁玩家会发现游戏本体能玩，但无法在创意工坊下载 MOD。开启此功能后，程序会从服务器拉取该游戏的专属 DepotKey，并将其写入解锁配置中。这样 Steam 就获得了下载该游戏加密 MOD 文件的权限。

**Q: 程序运行报错 `ModuleNotFoundError: No module named 'aiofiles'` 怎么办？**  
**A:** 这说明您跳过了上述的“安装依赖包”步骤。请打开终端运行 `pip install aiofiles colorlog httpx ujson vdf colorama`。

---

## 👨‍💻 制作人员与特别鸣谢

*   **软件主作者**: pvzcxw (B站: [菜Games-pvzcxw](https://space.bilibili.com/your_id))
*   **DLC 插件技术支持**: B-I-A-O
*   **清单不求人技术支持**: ☆☆☆☆
*   **VDF Writer 技术支持**: KS-MLC
*   **Steam 通讯协议技术支持**: pvzcwx
*   **基础环境与代码优化**: 宏
*   **特别感谢前置项目与探路者**: wxy1343 (清单下载器脚本原创者), FQQ, oureveryday, blanktming, Auiowu

---

## 💬 官方社区与问题反馈

我们非常欢迎用户提供使用反馈与建议！获取最新公告、版本更新或寻求人工帮助，请加入我们的社区：

*   **官方交流 QQ 群**: `993782526`
*   **关注作者 B 站**:[菜Games-pvzcxw](https://space.bilibili.com)
*   如果遇到 Bug，也欢迎在 GitHub 仓库提交[Issue](https://github.com/pvzcxw/cai-install_stloader/issues) 或 Pull Request。
```
