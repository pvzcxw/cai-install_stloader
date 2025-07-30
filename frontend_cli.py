# --- START OF FILE frontend_cli.py (ADDED DEPOTKEY PATCH FUNCTIONALITY) ---

import sys
import os
import asyncio
import tkinter as tk
from tkinter import messagebox
import webbrowser
from pathlib import Path
import json

try:
    from backend import CaiBackend
except ImportError:
    print("致命错误: backend.py 文件缺失。请确保两个文件都在同一个目录下。")
    sys.exit(1)

try:
    from colorama import init as colorama_init, Fore, Back, Style
    colorama_init()
except ImportError:
    class DummyStyle:
        def __getattr__(self, name): return ""
    Fore = Back = Style = DummyStyle()

def show_info_dialog():
    settings_path = Path('./settings.json')
    if settings_path.exists():
        try:
            if not json.loads(settings_path.read_text(encoding='utf-8')).get('show_notification', True):
                return
        except Exception: pass

    # webbrowser.open('https://docs.qq.com/doc/DTUp3Z2Fkd2pVRGtX?dver=')
    root = tk.Tk()
    root.title("Cai Install 信息提示")
    window_width, window_height = 400, 200
    screen_width, screen_height = root.winfo_screenwidth(), root.winfo_screenheight()
    pos_x = int(screen_width / 2 - window_width / 2)
    pos_y = int(screen_height / 2 - window_height / 2)
    root.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")
    root.resizable(False, False)
    tk.Label(root, text="请加入官方群聊以获取最新公告及更新:\n993782526\n关注官方b站:菜Games-pvzcxw", font=("Arial", 12)).pack(pady=20)
    dont_show = tk.BooleanVar(value=False)
    tk.Checkbutton(root, text="不再显示此消息", variable=dont_show, font=("Arial", 10)).pack(pady=5)

    def on_confirm():
        if dont_show.get():
            try:
                settings_path.write_text(json.dumps({'show_notification': False}, indent=2), encoding='utf-8')
            except Exception as e:
                print(f"保存设置失败: {e}")
        root.destroy()

    tk.Button(root, text="确认", width=10, command=on_confirm, font=("Arial", 10)).pack(pady=10)
    root.bind('<Return>', lambda event: on_confirm())
    root.mainloop()

def show_banner(backend: CaiBackend):
    log = backend.log
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
    for line in banner: log.info(line)
    log.info('软件作者:pvzcxw')
    log.info('本项目采用GNU General Public License v3开源许可证, 请勿用于商业用途')
    log.info('Cai install XP版本：1.55p1')
    log.info('Cai install项目Github仓库: https://github.com/pvzcxw/cai-install_stloader')
    log.warning('菜Games出品 本项目完全开源免费，作者b站:菜Games-pvzcxw,请多多赞助使用')
    log.warning('官方Q群:993782526')
    log.warning('vdf writer v2  已接入自研manifest2lua se  DLC检索入库by B-I-A-O 创意工坊入库by ☆☆☆☆ 感谢其技术支持 提示：入库创意工坊只需选择修补创意工坊秘钥即可（stool自动下载清单）')
    log.info('App ID可以在SteamDB, SteamUI或Steam商店链接页面查看')

async def main_flow(backend: CaiBackend):
    log = backend.log
    try:
        app_id_input = input(f"{Fore.CYAN}{Back.BLACK}{Style.BRIGHT}请输入游戏AppID、steamdb/steam链接或游戏名称(多个请用英文逗号分隔): {Style.RESET_ALL}").strip()
        if not app_id_input:
            log.error("输入不能为空。")
            return
        input_items = [item.strip() for item in app_id_input.split(',')]
    except (EOFError, KeyboardInterrupt):
        log.warning("\n操作已取消。")
        return

    add_all_dlc = False
    patch_depot_key = False  # NEW: 添加创意工坊密钥修补选项

    if backend.is_steamtools():
        while True:
            try:
                print(f"\n{Fore.YELLOW}检测到您正在使用 SteamTools。")
                print(f"{Fore.CYAN}自动更新清单功能可以让SteamTools自动获取最新清单版本（浮动版本）。")
                print(f"{Fore.CYAN}禁用此功能将使用传统模式，将当前清单版本固定到解锁脚本中。")
                choice = input(f"{Fore.GREEN}是否启用其自动更新清单功能？(y/n) (D加密勿选): {Style.RESET_ALL}").lower().strip()
                if choice in ['y', 'yes', '是']:
                    backend.use_st_auto_update = True
                    log.info("已启用自动更新（浮动版本）。将不指定版本号，由SteamTools自动更新。")
                    break
                elif choice in ['n', 'no', '否']:
                    backend.use_st_auto_update = False
                    log.info("已禁用自动更新（固定版本）。将按照传统方式导入清单和脚本。")
                    break
                else:
                    log.error("无效输入，请输入 y 或 n。")
            except (EOFError, KeyboardInterrupt):
                log.warning("\n操作已取消。")
                return

        while True:
            try:
                print(f"\n{Fore.YELLOW}SteamTools 附加功能:")
                choice = input(f"{Fore.GREEN}是否额外入库该游戏的所有可用DLC? (y/n): {Style.RESET_ALL}").lower().strip()
                if choice in ['y', 'yes', '是']:
                    add_all_dlc = True
                    log.info("已启用: 额外入库所有可用DLC。")
                    break
                elif choice in ['n', 'no', '否']:
                    add_all_dlc = False
                    log.info("已跳过: 额外入库DLC。")
                    break
                else:
                    log.error("无效输入，请输入 y 或 n。")
            except (EOFError, KeyboardInterrupt):
                log.warning("\n操作已取消。")
                return

        # NEW: 询问是否修补创意工坊密钥
        while True:
            try:
                print(f"\n{Fore.YELLOW}创意工坊密钥修补功能:")
                print(f"{Fore.CYAN}此功能会自动下载该游戏的创意工坊密钥。")
                print(f"{Fore.CYAN}并将其添加到解锁脚本中，用于解锁该游戏的创意工坊内容。")
                choice = input(f"{Fore.GREEN}是否修补创意工坊密钥? (y/n): {Style.RESET_ALL}").lower().strip()
                if choice in ['y', 'yes', '是']:
                    patch_depot_key = True
                    log.info("已启用: 创意工坊密钥修补。")
                    break
                elif choice in ['n', 'no', '否']:
                    patch_depot_key = False
                    log.info("已跳过: 创意工坊密钥修补。")
                    break
                else:
                    log.error("无效输入，请输入 y 或 n。")
            except (EOFError, KeyboardInterrupt):
                log.warning("\n操作已取消。")
                return

    print(f"\n{Fore.YELLOW}请选择清单查找方式：")
    print(f"{Fore.CYAN}1. 从指定清单库中选择")
    print(f"{Fore.CYAN}2. 使用游戏名称或appid搜索清单(仅支持github清单库){Style.RESET_ALL}")

    try:
        search_choice_input = input(f"{Fore.GREEN}请输入数字选择查找方式: {Style.RESET_ALL}")
        if not search_choice_input.isdigit():
            log.error("无效选择，请输入数字。")
            return
        search_choice = int(search_choice_input)
    except (ValueError, EOFError, KeyboardInterrupt):
        log.error("无效选择或操作已取消。")
        return

    if search_choice == 1:
        await handle_repo_selection(backend, input_items, add_all_dlc, patch_depot_key)
    elif search_choice == 2:
        await handle_github_search(backend, input_items, add_all_dlc, patch_depot_key)
    else:
        log.error("无效的选择，请输入1或2。")

# MODIFIED: 添加 patch_depot_key 参数
async def handle_repo_selection(backend: CaiBackend, items: list, add_all_dlc: bool, patch_depot_key: bool):
    log = backend.log
    print(f"\n{Fore.YELLOW}请选择清单库：")
    repo_map = {
        1: ("SWA V2库", lambda app_id: backend.process_printedwaste_manifest(app_id, add_all_dlc, patch_depot_key)),
        2: ("Cysaw库", lambda app_id: backend.process_cysaw_manifest(app_id, add_all_dlc, patch_depot_key)),
        3: ("Furcate库", lambda app_id: backend.process_furcate_manifest(app_id, add_all_dlc, patch_depot_key)),
        4: ("CNGS库", lambda app_id: backend.process_assiw_manifest(app_id, add_all_dlc, patch_depot_key)),
        5: ("SteamDatabase库", lambda app_id: backend.process_steamdatabase_manifest(app_id, add_all_dlc, patch_depot_key)),
    }
    for i, (name, _) in repo_map.items(): print(f"{Fore.CYAN}{i}. {name}")

    github_repos = ['Auiowu/ManifestAutoUpdate', 'SteamAutoCracks/ManifestHub']
    for i, repo in enumerate(github_repos, len(repo_map) + 1):
        print(f"{Fore.CYAN}{i}. {repo}{Style.RESET_ALL}")

    try:
        choice_input = input(f"{Fore.GREEN}请输入数字选择清单库: {Style.RESET_ALL}")
        if not choice_input.isdigit():
            log.error("无效选择，请输入数字。")
            return
        choice = int(choice_input)
    except (ValueError, EOFError, KeyboardInterrupt):
        log.error("无效选择或操作已取消。")
        return

    is_github_choice = choice > len(repo_map)

    await backend.checkcn()
    if is_github_choice:
        if not await backend.check_github_api_rate_limit():
            log.error("无法继续进行GitHub操作，因为已达到速率限制。")
            return

    for item in items:
        app_id = backend.extract_app_id(item)
        if not app_id:
            log.error(f"无法从 '{item}' 中提取有效的 AppID。已跳过...")
            continue

        log.info(f"--- 开始处理 AppID: {app_id} ---")
        success = False
        if choice in repo_map:
            success = await repo_map[choice][1](app_id)
        elif is_github_choice and choice <= len(repo_map) + len(github_repos):
            repo = github_repos[choice - len(repo_map) - 1]
            success = await backend.process_github_manifest(app_id, repo, add_all_dlc, patch_depot_key)
        else:
            log.error(f"无效的仓库选择: {choice}")
        log.info(f"--- AppID {app_id} 处理 {'成功' if success else '失败'} ---\n")

# MODIFIED: 添加 patch_depot_key 参数
async def handle_github_search(backend: CaiBackend, items: list, add_all_dlc: bool, patch_depot_key: bool):
    log = backend.log

    await backend.checkcn()
    if not await backend.check_github_api_rate_limit():
        log.error("无法继续进行GitHub搜索，因为已达到速率限制。")
        return

    github_repos = ['Auiowu/ManifestAutoUpdate', 'SteamAutoCracks/ManifestHub']

    for item in items:
        app_id = backend.extract_app_id(item)

        if not app_id:
            log.info(f"'{item}' 不是一个有效的AppID, 正在按游戏名称搜索...")
            games = await backend.find_appid_by_name(item)
            if not games:
                log.error(f"未找到名为 '{item}' 的游戏。")
                continue

            log.info("找到以下匹配的游戏:")
            for i, game in enumerate(games, 1):
                name = game.get('schinese_name') or game.get('name', 'N/A')
                log.info(f"{i}. {name} (AppID: {game['appid']})")

            try:
                choice_input = input("请选择游戏编号: ")
                if not choice_input.isdigit():
                    log.error("无效选择，请输入数字。")
                    continue
                choice = int(choice_input) - 1
                if 0 <= choice < len(games): app_id = games[choice]['appid']
                else: log.error("无效选择。"); continue
            except (ValueError, EOFError, KeyboardInterrupt):
                log.error("无效输入或操作已取消。"); continue

        log.info(f"--- 开始为 AppID {app_id} 搜索 GitHub 清单 ---")
        results = await backend.search_all_repos_for_appid(app_id, github_repos)
        if not results:
            log.error(f"在所有 GitHub 仓库中都未找到 AppID {app_id} 的清单。"); continue

        log.info(f"在以下仓库中找到清单：")
        for i, res in enumerate(results, 1): print(f"{Fore.CYAN}{i}. {res['repo']} (更新时间: {res['update_date']}){Style.RESET_ALL}")

        try:
            choice_input = input(f"{Fore.GREEN}请选择要使用的仓库编号: {Style.RESET_ALL}")
            if not choice_input.isdigit():
                log.error("无效选择，请输入数字。")
                continue
            choice = int(choice_input) - 1
            if 0 <= choice < len(results):
                repo = results[choice]['repo']
                success = await backend.process_github_manifest(app_id, repo, add_all_dlc, patch_depot_key)
                log.info(f"--- AppID {app_id} 处理 {'成功' if success else '失败'} ---\n")
            else:
                log.error("无效选择。")
        except (ValueError, EOFError, KeyboardInterrupt):
            log.error("无效输入或操作已取消。")

# --- MODIFIED: Function to handle workshop flow with BATCH input ---
async def workshop_flow(backend: CaiBackend):
    log = backend.log
    log.info(f"\n{Fore.YELLOW}--- 创意工坊清单下载模式 ---{Style.RESET_ALL}")
    try:
        # Get the whole batch of inputs at once
        workshop_input_batch = input(f"{Fore.CYAN}{Back.BLACK}{Style.BRIGHT}请输入一个或多个创意工坊物品ID/URL (用英文逗号 ',' 分隔): {Style.RESET_ALL}").strip()
        
        if not workshop_input_batch:
            log.error("输入不能为空。")
            return

        # Split the input string into a list of items
        items_to_process = [item.strip() for item in workshop_input_batch.split(',')]

        # Loop through each item and process it
        for item in items_to_process:
            if not item:  # Skip empty strings which can result from trailing commas
                continue
            
            log.info(f"--- 开始处理: {item} ---")
            success = await backend.process_workshop_manifest(item)
            if success:
                log.info(f"{Fore.GREEN}--- '{item}' 处理成功 ---{Style.RESET_ALL}\n")
            else:
                log.error(f"{Fore.RED}--- '{item}' 处理失败 ---{Style.RESET_ALL}\n")

    except (EOFError, KeyboardInterrupt):
        log.warning("\n操作已取消。")

async def async_main():
    backend = CaiBackend()
    log = backend.log

    show_banner(backend)

    try:
        status = await backend.initialize()
        if status is None:
            return

        if status == "conflict":
            log.error(f"{Fore.RED}{Style.BRIGHT}错误的解锁环境！检测到 SteamTools 和 GreenLuma 同时存在。")
            log.error("请手动卸载其中一个，以避免冲突。")
            return

        if status == "none":
            log.warning("未查找到解锁工具，请手动选择您的解锁方式：")
            print(f"  {Fore.CYAN}1. SteamTools")
            print(f"  {Fore.CYAN}2. GreenLuma{Style.RESET_ALL}")
            while True:
                try:
                    choice = input(f"{Fore.GREEN}请输入您的选择 (1 或 2): {Style.RESET_ALL}")
                    if choice == '1':
                        backend.unlocker_type = "steamtools"
                        log.info("已手动选择: SteamTools")
                        break
                    elif choice == '2':
                        backend.unlocker_type = "greenluma"
                        log.info("已手动选择: GreenLuma")
                        break
                    else:
                        log.error("无效输入，请输入 1 或 2。")
                except (EOFError, KeyboardInterrupt):
                    log.warning("\n操作已取消。")
                    return
        
        # --- Main Menu ---
        while True:
            print(f"\n{Fore.YELLOW}请选择要执行的操作：")
            print(f"{Fore.CYAN}1. 游戏入库")
            print(f"{Fore.CYAN}2. 创意工坊清单入库（stool会自动下载，一般无须使用）")
            print(f"{Fore.CYAN}q. 退出程序{Style.RESET_ALL}")

            try:
                main_choice = input(f"{Fore.GREEN}请输入您的选择: {Style.RESET_ALL}").strip().lower()

                if main_choice == '1':
                    await main_flow(backend)
                elif main_choice == '2':
                    await workshop_flow(backend)
                elif main_choice in ['q', 'quit', 'exit']:
                    break
                else:
                    log.error("无效选择，请输入 1, 2 或 q。")

            except (EOFError, KeyboardInterrupt):
                log.warning("\n操作已取消，返回主菜单。")
                continue


    except Exception as e:
        log.error(f'主程序发生意外错误: {backend.stack_error(e)}')
    finally:
        await backend.cleanup_temp_files()
        await backend.close_resources()

if __name__ == '__main__':
    show_info_dialog()
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n用户中断了程序。")
    finally:
        print("\n操作完成。按任意键退出...")
        try: input()
        except (EOFError, KeyboardInterrupt): pass