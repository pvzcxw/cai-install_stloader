# --- START OF FILE frontend_cli.py ---

import sys
import os
import asyncio
import re
import tkinter as tk
from tkinter import messagebox
import webbrowser
from pathlib import Path
import json

import colorlog
import logging
from colorama import init as colorama_init, Fore, Style

# Import the backend
from backend import CaiCore

# --- UI and Presentation Functions ---

LOG_FORMAT = '%(log_color)s%(message)s'
LOG_COLORS = {'INFO': 'cyan', 'WARNING': 'yellow', 'ERROR': 'red', 'CRITICAL': 'purple'}

def setup_logger() -> logging.Logger:
    """Sets up the colored logger for the CLI."""
    colorama_init()
    logger = logging.getLogger('CaiInstallCLI')
    logger.setLevel(logging.INFO)
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(LOG_FORMAT, log_colors=LOG_COLORS))
    if not logger.handlers:
        logger.addHandler(handler)
    return logger

log = setup_logger()

def print_banner():
    """Prints the ASCII art banner."""
    banner = [
        r"                     /$$       /$$                       /$$               /$$ /$$",
        r"                    |__/      |__/                      | $$              | $$| $$",
        r"  /$$$$$$$  /$$$$$$  /$$       /$$ /$$$$$$$   /$$$$$$$ /$$$$$$    /$$$$$$ | $$| $$",
        r" /$$_____/ |____  $$| $$      | $$| $$__  $$ /$$_____/|_  $$_/   |____  $$| $$| $$",
        r"| $$        /$$$$$$$| $$      | $$| $$  \ $$|  $$$$$$   | $$      /$$$$$$$| $$| $$",
        r"| $$       /$$__  $$| $$      | $$| $$  | $$ \____  $$  | $$ /$$ /$$__  $$| $$| $$",
        r"|  $$$$$$$|  $$$$$$$| $$      | $$| $$  | $$ /$$$$$$$/  |  $$$$/|  $$$$$$$| $$| $$",
        r" \_______/ \_______/|__/      |__/|__/  |__/|_______/    \___/   \_______/|__/|__/",
    ]
    for line in banner:
        log.info(line)
    log.info('软件作者:pvzcxw')
    log.info('Cai install XP版本：1.35b1-fix1')
    log.warning('官方Q群:993782526, 官方b站:菜Games-pvzcxw')
    log.info('App ID可以在SteamDB, Steam商店链接页面或通过游戏名搜索来查看')

def show_info_dialog():
    """Shows the initial Tkinter info dialog."""
    settings_path = Path('./settings.json')
    if settings_path.exists():
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                if not json.load(f).get('show_notification', True):
                    return
        except Exception: pass
    
    webbrowser.open('https://docs.qq.com/doc/DTUp3Z2Fkd2pVRGtX?dver=')
    
    root = tk.Tk()
    root.title("Cai Install 信息提示")
    root.geometry("400x200")
    root.resizable(False, False)
    
    tk.Label(root, text="请加入官方群聊以获取最新公告及更新:\n993782526\n关注官方b站:菜Games-pvzcxw", font=("Arial", 12)).pack(pady=20)
    
    dont_show = tk.BooleanVar()
    tk.Checkbutton(root, text="不再显示此消息", variable=dont_show).pack(pady=5)
    
    def on_confirm():
        if dont_show.get():
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump({'show_notification': False}, f)
        root.destroy()
        
    tk.Button(root, text="确认", command=on_confirm).pack(pady=10)
    root.mainloop()

def extract_app_id(user_input: str) -> str:
    """Extracts an App ID from a URL or returns the input if it's a digit."""
    match = re.search(r"/app/(\d+)", user_input)
    return match.group(1) if match else user_input if user_input.isdigit() else None

# --- Main Application Flow ---

async def main():
    show_info_dialog()
    print_banner()

    core = CaiCore()
    success, message = await core.initialize()
    if not success:
        log.error(message)
        await core.close()
        os.system('pause')
        return

    log.info(message)
    log.info(f"Detected Unlocker: {'SteamTools' if core.isSteamTools else 'GreenLuma' if core.isGreenLuma else 'None'}")
    
    while True:
        try:
            user_input = input(f"\n{Fore.CYAN}请输入游戏AppID、链接、名称 (多个用逗号','分隔), 或输入 'exit' 退出:{Style.RESET_ALL} ").strip()
            if user_input.lower() == 'exit':
                break
            if not user_input:
                continue

            app_id_inputs = [item.strip() for item in user_input.split(',')]
            app_ids_to_process = []

            # Resolve names to AppIDs first
            for item in app_id_inputs:
                app_id = extract_app_id(item)
                if app_id:
                    app_ids_to_process.append(app_id)
                else:
                    log.info(f"'{item}'不是有效的AppID或链接，将作为游戏名搜索...")
                    games = await core.search_games_by_name(item)
                    if not games:
                        log.warning(f"找不到名为 '{item}' 的游戏。")
                        continue
                    
                    log.info(f"找到以下匹配 '{item}' 的游戏:")
                    for i, game in enumerate(games, 1):
                        name = game.get('schinese_name') or game.get('name', 'Unknown')
                        log.info(f"  {i}. {name} (AppID: {game['appid']})")
                    
                    try:
                        choice = int(input("  请选择游戏编号: ")) - 1
                        if 0 <= choice < len(games):
                            app_ids_to_process.append(str(games[choice]['appid']))
                        else:
                            log.error("无效的选择。")
                    except ValueError:
                        log.error("请输入数字。")

            if not app_ids_to_process:
                log.error("没有有效的AppID可供处理，请重试。")
                continue

            log.info(f"准备处理以下AppIDs: {', '.join(app_ids_to_process)}")

            # Let user choose the source
            print("\n" + Fore.YELLOW + "请选择清单库：" + Style.RESET_ALL)
            sources = ["SWA", "Cysaw", "Furcate", "CNGS", "SteamDB"] + core.GITHUB_REPOS
            for i, src in enumerate(sources, 1):
                print(f"  {Fore.CYAN}{i}. {src}{Style.RESET_ALL}")
            
            try:
                choice = int(input(f"{Fore.GREEN}请输入数字选择清单库: {Style.RESET_ALL}")) - 1
                if not (0 <= choice < len(sources)):
                    log.error("无效的选择。")
                    continue
                
                selected_source = sources[choice]

                # Process each AppID
                for app_id in app_ids_to_process:
                    log.info(f"--- 开始处理 AppID: {app_id} from {selected_source} ---")
                    if choice < 5: # Non-github sources
                        success, message = await core.install_from_source(app_id, selected_source)
                    else: # GitHub repos
                        success, message = await core.install_from_github_repo(app_id, selected_source)

                    if success:
                        log.info(f"成功: {message}")
                    else:
                        log.error(f"失败: {message}")

            except ValueError:
                log.error("请输入有效的数字。")
            except Exception as e:
                log.error(f"发生意外错误: {e}")

        except (KeyboardInterrupt, EOFError):
            break
    
    log.info("正在清理并退出...")
    await core.close()
    log.info("程序已退出。")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被用户强制退出。")
    except Exception as e:
        print(f"\n发生致命错误: {e}")
    finally:
        os.system('pause')
