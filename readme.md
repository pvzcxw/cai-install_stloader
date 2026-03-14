# Cai-Install STLoader (Cai Install XP)

![Version](https://img.shields.io/badge/Version-1.64p1-blue)
![License](https://img.shields.io/badge/License-GPLv3-green)
![Python](https://img.shields.io/badge/Python-3.8+-yellow)

**Cai Install** 是一款专为 Steam 解锁工具（如 SteamTools、GreenLuma）设计的全自动游戏清单（Manifest）及密钥（DepotKey）下载、配置与入库工具。

本项目完全开源免费，采用 GNU GPL v3 许可证。**请勿用于商业用途，严禁倒卖！**

---

## ✨ 核心特性

- 🔍 **智能环境检测**：自动获取 Steam 安装路径，智能识别当前使用的解锁工具（SteamTools 或 GreenLuma）。
- 📦 **多源清单库支持**：内置众多知名清单库（SWA V2, Cysaw, Furcate, Walftech, SteamDatabase, ManifestHub, Sudama, 不求人等）。
- ⚙️ **自定义清单源**：支持通过配置文件轻松添加自定义的 ZIP 清单直链源或 GitHub 仓库源。
- 🔑 **全自动 DepotKey 注入**：自动获取并补全游戏及 DLC 的解密密钥，无缝写入解锁配置文件或 `config.vdf`。
- 🧩 **全 DLC 及创意工坊支持**：
  - 一键扫描并自动入库游戏的所有可用免费/无 Depot 的 DLC。
  - 支持直接修补和获取**创意工坊（Workshop）**的清单及密钥，让您轻松下载订阅 MOD。
- 🔄 **清单动态更新**：SteamTools 模式下支持“浮动版本”（自动更新清单），免去频繁手动更新的烦恼。
- 🌏 **网络优化**：自动检测是否为中国大陆网络，智能切换 GitHub 代理镜像，保障下载畅通无阻。
- 🚀 **自动更新机制**：程序内置自检更新功能，发布新版本时第一时间通知并引导下载。

---

## 🛠️ 支持的解锁工具

- **SteamTools** (默认生成并修补 `.lua` 解锁脚本，支持动态清单更新)
- **GreenLuma** (自动合并密钥至 `config.vdf`，并写入 `AppList`)

---

## 🚀 快速开始

### 环境依赖
请确保您的计算机上已安装 Python 3.8 或更高版本。

克隆仓库后，安装必要的 Python 依赖包：
```bash
pip install aiofiles colorlog httpx ujson vdf colorama
