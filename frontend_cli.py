# --- START OF FILE frontend_cli.py (ADDED CUSTOM REPOS SUPPORT) ---

import sys
import os
import asyncio
import tkinter as tk
from tkinter import messagebox, scrolledtext
import webbrowser
from pathlib import Path
import json
import subprocess
import platform

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
        except Exception:
            pass

    # webbrowser.open('https://docs.qq.com/doc/DTUp3Z2Fkd2pVRGtX?dver=')
    root = tk.Tk()
    root.title("Cai Install 信息提示")
    window_width, window_height = 400, 200
    screen_width, screen_height = root.winfo_screenwidth(), root.winfo_screenheight()
    pos_x = int(screen_width / 2 - window_width / 2)
    pos_y = int(screen_height / 2 - window_height / 2)
    root.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")
    root.resizable(False, False)
    tk.Label(root, text="请加入官方群聊以获取最新公告及更新:\n993782526\n关注官方b站:菜Games-pvzcxw",
             font=("Arial", 12)).pack(pady=20)
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
    log.info('Cai install XP版本：1.58p1')
    log.info('Cai install项目Github仓库: https://github.com/pvzcxw/cai-install_stloader')
    log.warning('菜Games出品 本项目完全开源免费，作者b站:菜Games-pvzcxw,请多多赞助使用')
    log.warning('官方Q群:993782526')
    log.warning(
        'vdf writer v2  已接入自研manifest2lua se  DLC检索入库及输出帮助by B-I-A-O 创意工坊入库及不求人清单by ☆☆☆☆ 感谢其技术支持 提示：入库创意工坊只需选择修补创意工坊秘钥即可（stool自动下载清单）')
    log.info('App ID可以在SteamDB, SteamUI或Steam商店链接页面查看')


async def main_flow(backend: CaiBackend):
    log = backend.log
    try:
        app_id_input = input(
            f"{Fore.CYAN}{Back.BLACK}{Style.BRIGHT}请输入游戏AppID、steamdb/steam链接或游戏名称(多个请用英文逗号分隔): {Style.RESET_ALL}").strip()
        if not app_id_input:
            log.error("输入不能为空。")
            return
        input_items = [item.strip() for item in app_id_input.split(',')]
    except (EOFError, KeyboardInterrupt):
        log.warning("\n操作已取消。")
        return

    add_all_dlc = False
    patch_depot_key = False  # NEW: 添加创意工坊密钥修补选项

    # ---------- 1. 自动更新清单 ----------
    print(f"\n{Fore.YELLOW}检测到您正在使用 SteamTools。{Style.RESET_ALL}")
    print(f"{Fore.CYAN}自动更新清单功能可以让 SteamTools 自动获取最新清单版本（浮动版本）。")
    print(f"禁用此功能将使用传统模式，将当前清单版本固定到解锁脚本中。{Style.RESET_ALL}")

    choice = input(
        f"{Fore.GREEN}是否启用其自动更新清单功能？(y/n) (D 加密勿选) [默认: y]: {Style.RESET_ALL}"
    ).strip().lower()

    # ✅ 日志你爱怎么改怎么改，但赋值必须保留
    if choice in ('y', 'yes', '是', ''):
        backend.use_st_auto_update = True
        print(f"{Fore.GREEN}已启用自动更新（浮动版本）。将不指定版本号，由 SteamTools 自动更新。{Style.RESET_ALL}")
    else:
        backend.use_st_auto_update = False
        print(f"{Fore.GREEN}已禁用自动更新（固定版本）。将按照传统方式导入清单和脚本。{Style.RESET_ALL}")

    # ---------- 2. 是否入库全部 DLC ----------
    print(f"\n{Fore.YELLOW}SteamTools 附加功能:{Style.RESET_ALL}")
    choice = input(f"{Fore.GREEN}是否额外入库该游戏的所有可用 DLC? (y/n) [默认: y]: {Style.RESET_ALL}").strip().lower()
    if choice in ('y', 'yes', '是', ''):
        add_all_dlc = True
        print(f"{Fore.GREEN}已启用: 额外入库所有可用 DLC。{Style.RESET_ALL}")
    else:
        add_all_dlc = False
        print(f"{Fore.GREEN}已跳过: 额外入库 DLC。{Style.RESET_ALL}")

    # ---------- 3. 是否修补创意工坊密钥 ----------
    print(f"\n{Fore.YELLOW}创意工坊密钥修补功能:{Style.RESET_ALL}")
    print(f"{Fore.CYAN}此功能会自动下载该游戏的创意工坊密钥，")
    print(f"并将其添加到解锁脚本中，用于解锁该游戏的创意工坊内容。{Style.RESET_ALL}")
    choice = input(f"{Fore.GREEN}是否修补创意工坊密钥? (y/n) [默认: y]: {Style.RESET_ALL}").strip().lower()
    if choice in ('y', 'yes', '是', ''):
        patch_depot_key = True
        print(f"{Fore.GREEN}已启用: 创意工坊密钥修补。{Style.RESET_ALL}")
    else:
        patch_depot_key = False
        print(f"{Fore.GREEN}已跳过: 创意工坊密钥修补。{Style.RESET_ALL}")

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


async def handle_repo_selection(backend: CaiBackend, items: list, add_all_dlc: bool, patch_depot_key: bool):
    log = backend.log
    print(f"\n{Fore.YELLOW}请选择清单库：")

    builtin_zip_repos = {
        1: ("SWA V2库", lambda app_id: backend.process_printedwaste_manifest(app_id, add_all_dlc, patch_depot_key)),
        2: ("Cysaw库", lambda app_id: backend.process_cysaw_manifest(app_id, add_all_dlc, patch_depot_key)),
        3: ("Furcate库", lambda app_id: backend.process_furcate_manifest(app_id, add_all_dlc, patch_depot_key)),
        4: ("CNGS库", lambda app_id: backend.process_assiw_manifest(app_id, add_all_dlc, patch_depot_key)),
        5: ("SteamDatabase库",
            lambda app_id: backend.process_steamdatabase_manifest(app_id, add_all_dlc, patch_depot_key)),
        6: ("SteamAutoCracks/ManifestHub(2)",
            lambda app_id: backend.process_steamautocracks_v2_manifest(app_id, add_all_dlc, patch_depot_key)),
        7: ("清单不求人（仅清单）", lambda app_id: backend.process_buqiuren_manifest(app_id))
    }

    # 显示内置ZIP清单库
    current_index = 1
    repo_handlers = {}

    for i, (name, handler) in builtin_zip_repos.items():
        print(f"{Fore.CYAN}{current_index}. {name}")
        repo_handlers[current_index] = ('builtin_zip', handler)
        current_index += 1

    # 获取并显示自定义ZIP清单库
    custom_zip_repos = backend.get_custom_zip_repos()
    if custom_zip_repos:
        print(f"{Fore.MAGENTA}--- 自定义ZIP清单库 ---")
        for repo_config in custom_zip_repos:
            repo_name = repo_config['name']
            print(f"{Fore.MAGENTA}{current_index}. {repo_name} (自定义)")
            repo_handlers[current_index] = ('custom_zip', repo_config)
            current_index += 1

    # 内置GitHub清单库
    builtin_github_repos = ['Auiowu/ManifestAutoUpdate', 'SteamAutoCracks/ManifestHub']
    print(f"{Fore.GREEN}--- GitHub清单库 ---")
    for repo in builtin_github_repos:
        print(f"{Fore.GREEN}{current_index}. {repo}")
        repo_handlers[current_index] = ('builtin_github', repo)
        current_index += 1

    # 获取并显示自定义GitHub清单库
    custom_github_repos = backend.get_custom_github_repos()
    if custom_github_repos:
        for repo_config in custom_github_repos:
            repo_name = repo_config['name']
            repo_path = repo_config['repo']
            print(f"{Fore.GREEN}{current_index}. {repo_name} ({repo_path}) (自定义)")
            repo_handlers[current_index] = ('custom_github', repo_path)
            current_index += 1

    print(f"{Style.RESET_ALL}")

    try:
        choice_input = input(f"{Fore.GREEN}请输入数字选择清单库: {Style.RESET_ALL}")
        if not choice_input.isdigit():
            log.error("无效选择，请输入数字。")
            return
        choice = int(choice_input)
    except (ValueError, EOFError, KeyboardInterrupt):
        log.error("无效选择或操作已取消。")
        return

    if choice not in repo_handlers:
        log.error(f"无效的库选择: {choice}")
        return

    repo_type, repo_data = repo_handlers[choice]

    # 检查是否需要GitHub API
    is_github_choice = repo_type in ['builtin_github', 'custom_github']

    await backend.checkcn()
    if is_github_choice:
        if not await backend.check_github_api_rate_limit():
            log.error("无法继续进行GitHub操作，因为已达到速率限制。")
            return

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
                if 0 <= choice < len(games):
                    app_id = games[choice]['appid']
                else:
                    log.error("无效选择。")
                    continue
            except (ValueError, EOFError, KeyboardInterrupt):
                log.error("无效输入或操作已取消。")
                continue

        log.info(f"--- 开始处理 AppID: {app_id} ---")
        success = False

        if repo_type == 'builtin_zip':
            success = await repo_data(app_id)
        elif repo_type == 'custom_zip':
            success = await backend.process_custom_zip_manifest(app_id, repo_data, add_all_dlc, patch_depot_key)
        elif repo_type == 'builtin_github':
            success = await backend.process_github_manifest(app_id, repo_data, add_all_dlc, patch_depot_key)
        elif repo_type == 'custom_github':
            success = await backend.process_github_manifest(app_id, repo_data, add_all_dlc, patch_depot_key)
        else:
            log.error(f"未知的库类型: {repo_type}")

        log.info(f"--- AppID {app_id} 处理 {'成功' if success else '失败'} ---\n")


# MODIFIED: 使用包含自定义仓库的GitHub仓库列表
async def handle_github_search(backend: CaiBackend, items: list, add_all_dlc: bool, patch_depot_key: bool):
    log = backend.log

    await backend.checkcn()
    if not await backend.check_github_api_rate_limit():
        log.error("无法继续进行GitHub搜索，因为已达到速率限制。")
        return

    # 使用包含自定义仓库的完整GitHub仓库列表
    all_github_repos = backend.get_all_github_repos()

    # 显示将要搜索的仓库
    log.info(f"将在以下 {len(all_github_repos)} 个GitHub仓库中搜索:")
    builtin_repos = ['Auiowu/ManifestAutoUpdate', 'SteamAutoCracks/ManifestHub']
    custom_repos = [repo['repo'] for repo in backend.get_custom_github_repos()]

    for repo in builtin_repos:
        log.info(f"  - {repo} (内置)")
    for repo in custom_repos:
        log.info(f"  - {repo} (自定义)")

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
                if 0 <= choice < len(games):
                    app_id = games[choice]['appid']
                else:
                    log.error("无效选择。"); continue
            except (ValueError, EOFError, KeyboardInterrupt):
                log.error("无效输入或操作已取消。");
                continue

        log.info(f"--- 开始为 AppID {app_id} 搜索 GitHub 清单 ---")
        # 使用包含自定义仓库的搜索
        results = await backend.search_all_repos_for_appid(app_id, all_github_repos)
        if not results:
            log.error(f"在所有 GitHub 仓库中都未找到 AppID {app_id} 的清单。");
            continue

        log.info(f"在以下仓库中找到清单：")
        for i, res in enumerate(results, 1):
            repo_name = res['repo']
            # 标识是否为自定义仓库
            if repo_name not in builtin_repos:
                repo_display = f"{repo_name} (自定义)"
            else:
                repo_display = repo_name
            print(f"{Fore.CYAN}{i}. {repo_display} (更新时间: {res['update_date']}){Style.RESET_ALL}")

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
        workshop_input_batch = input(
            f"{Fore.CYAN}{Back.BLACK}{Style.BRIGHT}请输入一个或多个创意工坊物品ID/URL (用英文逗号 ',' 分隔): {Style.RESET_ALL}").strip()

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

        await check_and_prompt_update(backend)

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

        # 显示自定义仓库配置状态
        custom_github_repos = backend.get_custom_github_repos()
        custom_zip_repos = backend.get_custom_zip_repos()

        if custom_github_repos or custom_zip_repos:
            log.info(f"\n{Fore.GREEN}已检测到自定义清单库配置:")
            if custom_github_repos:
                log.info(f"  - 自定义GitHub清单库: {len(custom_github_repos)} 个")
                for repo in custom_github_repos:
                    log.info(f"    * {repo['name']} ({repo['repo']})")
            if custom_zip_repos:
                log.info(f"  - 自定义ZIP清单库: {len(custom_zip_repos)} 个")
                for repo in custom_zip_repos:
                    log.info(f"    * {repo['name']}")
            log.info(f"{Style.RESET_ALL}")

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


def show_update_dialog(update_info: dict) -> bool:
    """
    显示更新提示对话框
    返回: True 如果用户选择更新，False 如果跳过
    """
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口

    # 准备更新信息文本
    current_ver = update_info.get('current_version', '未知')
    latest_ver = update_info.get('latest_version', '未知')
    release_name = update_info.get('release_name', '')
    release_url = update_info.get('release_url', '')

    # 构建消息
    message = f"发现新版本！\n\n"
    message += f"当前版本: {current_ver}\n"
    message += f"最新版本: {latest_ver}\n"
    if release_name:
        message += f"版本名称: {release_name}\n"
    message += f"\n是否前往下载页面？"

    # 显示对话框
    result = messagebox.askyesno(
        "发现新版本",
        message,
        parent=root
    )

    root.destroy()

    if result and release_url:
        # 打开浏览器访问发布页面
        webbrowser.open(release_url)

    return result


def show_update_dialog_with_details(update_info: dict) -> str:
    """
    显示详细的更新对话框，包含更新日志
    返回: 'update' 更新, 'skip' 跳过这次, 'ignore' 忽略这个版本
    """
    root = tk.Tk()
    root.title("发现新版本")

    # 设置窗口大小和位置
    window_width, window_height = 600, 500
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    pos_x = int(screen_width / 2 - window_width / 2)
    pos_y = int(screen_height / 2 - window_height / 2)
    root.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")
    root.resizable(False, False)

    # 版本信息
    current_ver = update_info.get('current_version', '未知')
    latest_ver = update_info.get('latest_version', '未知')
    release_name = update_info.get('release_name', '')
    release_body = update_info.get('release_body', '')
    release_url = update_info.get('release_url', '')
    download_urls = update_info.get('download_urls', [])

    # 标题
    title_frame = tk.Frame(root)
    title_frame.pack(pady=10, padx=20, fill='x')

    tk.Label(title_frame, text="🎉 发现新版本可用！", font=("Arial", 16, "bold")).pack()

    # 版本信息框
    info_frame = tk.Frame(root)
    info_frame.pack(pady=10, padx=20, fill='x')

    tk.Label(info_frame, text=f"当前版本: {current_ver}", font=("Arial", 11)).pack(anchor='w')
    tk.Label(info_frame, text=f"最新版本: {latest_ver}", font=("Arial", 11, "bold"), fg="green").pack(anchor='w')
    if release_name:
        tk.Label(info_frame, text=f"版本名称: {release_name}", font=("Arial", 11)).pack(anchor='w')

    # 更新日志
    tk.Label(root, text="更新内容:", font=("Arial", 11, "bold")).pack(anchor='w', padx=20, pady=(10, 5))

    # 创建带滚动条的文本框
    text_frame = tk.Frame(root)
    text_frame.pack(padx=20, pady=5, fill='both', expand=True)

    text_widget = scrolledtext.ScrolledText(text_frame, wrap='word', height=10)
    text_widget.pack(fill='both', expand=True)

    # 插入更新日志
    if release_body:
        text_widget.insert('1.0', release_body)
    else:
        text_widget.insert('1.0', "暂无更新日志")

    text_widget.config(state='disabled')  # 设为只读

    # 用户选择结果
    user_choice = {'action': 'skip'}

    # 按钮框架
    button_frame = tk.Frame(root)
    button_frame.pack(pady=20)

    def on_update():
        user_choice['action'] = 'update'
        if release_url:
            webbrowser.open(release_url)
        root.destroy()

    def on_skip():
        user_choice['action'] = 'skip'
        root.destroy()

    def on_ignore():
        user_choice['action'] = 'ignore'
        # 保存忽略的版本
        try:
            settings_path = Path('./update_settings.json')
            settings = {}
            if settings_path.exists():
                settings = json.loads(settings_path.read_text(encoding='utf-8'))
            settings['ignored_version'] = latest_ver
            settings_path.write_text(json.dumps(settings, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"保存忽略版本失败: {e}")
        root.destroy()

    tk.Button(button_frame, text="立即更新", command=on_update,
              bg="green", fg="white", font=("Arial", 11, "bold"),
              width=12, height=2).pack(side='left', padx=5)
    tk.Button(button_frame, text="稍后提醒", command=on_skip,
              font=("Arial", 10), width=10).pack(side='left', padx=5)
    tk.Button(button_frame, text="忽略此版本", command=on_ignore,
              font=("Arial", 10), width=10).pack(side='left', padx=5)

    # 自动聚焦到更新按钮
    root.focus_force()

    root.mainloop()

    return user_choice['action']


async def check_and_prompt_update(backend: CaiBackend):
    """
    检查更新并提示用户
    """
    try:
        # 检查是否应该跳过更新检查
        update_settings_path = Path('./update_settings.json')
        if update_settings_path.exists():
            try:
                settings = json.loads(update_settings_path.read_text(encoding='utf-8'))
                # 检查是否有忽略的版本
                ignored_version = settings.get('ignored_version', '')

                # 检查是否禁用了自动更新检查
                if settings.get('disable_update_check', False):
                    backend.log.info("自动更新检查已禁用")
                    return

            except Exception:
                pass

        # 检查更新
        has_update, update_info = await backend.check_for_updates()

        if has_update:
            # 检查是否是被忽略的版本
            if update_settings_path.exists():
                try:
                    settings = json.loads(update_settings_path.read_text(encoding='utf-8'))
                    ignored_version = settings.get('ignored_version', '')
                    if ignored_version == update_info.get('latest_version', ''):
                        backend.log.info(f"版本 {ignored_version} 已被忽略")
                        return
                except Exception:
                    pass

            # 显示更新对话框
            action = show_update_dialog_with_details(update_info)

            if action == 'update':
                backend.log.info("用户选择更新，正在打开下载页面...")
            elif action == 'ignore':
                backend.log.info(f"用户选择忽略版本 {update_info.get('latest_version', '')}")
            else:
                backend.log.info("用户选择稍后更新")

    except Exception as e:
        backend.log.warning(f"更新检查过程出错: {e}")


if __name__ == '__main__':
    show_info_dialog()
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n用户中断了程序。")
    finally:
        print("\n操作完成。按任意键退出...")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass