import sys
import os
import traceback
import time
import logging
import subprocess
import asyncio
import re
import aiofiles
import colorlog
import httpx
import winreg
import ujson as json
import vdf
import json
import webbrowser
import zipfile
import shutil
import struct
import zlib
import psutil
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from typing import Tuple
from typing import Any
from colorama import init, Fore, Back, Style
client = httpx.AsyncClient(verify=False, trust_env=True)

# 检测非法调用


# 显示提示窗口
def show_info_dialog():
    # 检查是否存在不再显示的设置文件
    settings_path = Path('./settings.json')
    show_dialog = True
    
    # 尝试加载设置文件
    if settings_path.exists():
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                show_dialog = settings.get('show_notification', True)
        except Exception:
            show_dialog = True
    
    # 如果用户选择了不再显示，直接返回
    if not show_dialog:
        return
    
    # 创建主窗口前自动打开网址
    webbrowser.open('https://docs.qq.com/doc/DTUp3Z2Fkd2pVRGtX?dver=')
    
    # 创建主窗口
    root = tk.Tk()
    root.title("Cai Install 信息提示")
    
    # 设置窗口大小和位置
    window_width = 400
    window_height = 200  # 增加高度以容纳新按钮
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    position_top = int(screen_height / 2 - window_height / 2)
    position_right = int(screen_width / 2 - window_width / 2)
    root.geometry(f"{window_width}x{window_height}+{position_right}+{position_top}")
    
    # 防止窗口调整大小
    root.resizable(False, False)
    
    # 添加说明文本
    label = tk.Label(root, text="请加入官方群聊以获取最新公告及更新:\n993782526\n关注官方b站:菜Games-pvzcxw", font=("Arial", 12))
    label.pack(pady=20)
    
    # 创建"不再显示"的复选框变量
    dont_show_again = tk.BooleanVar()
    dont_show_again.set(False)
    
    # 添加复选框
    checkbox = tk.Checkbutton(root, text="不再显示此消息", variable=dont_show_again, font=("Arial", 10))
    checkbox.pack(pady=5)
    
    # 保存设置的函数
    def save_settings_and_close():
        # 保存设置到文件
        if dont_show_again.get():
            try:
                settings = {'show_notification': False}
                with open(settings_path, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=2)
            except Exception as e:
                print(f"保存设置失败: {e}")
        
        # 关闭窗口
        root.destroy()
    
    # 添加确认按钮
    button = tk.Button(root, text="确认", width=10, command=save_settings_and_close, font=("Arial", 10))
    button.pack(pady=10)
    
    # 按下回车键也可以提交
    root.bind('<Return>', lambda event: save_settings_and_close())
    
    # 显示窗口，并等待用户操作
    root.mainloop()


init()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
lock = asyncio.Lock()
client = httpx.AsyncClient(trust_env=True)


DEFAULT_CONFIG = {
    "Github_Personal_Token": "",
    "Custom_Steam_Path": "",
    "QA1": "温馨提示: Github_Personal_Token-cixcode可在Github设置的最底下开发者选项找到, 详情看教程"
}

LOG_FORMAT = '%(log_color)s%(message)s'
LOG_COLORS = {
    'INFO': 'cyan',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'purple',
}


def init_log(level=logging.DEBUG) -> logging.Logger:
    """ 初始化日志模块 """
    logger = logging.getLogger(' Cai install')
    logger.setLevel(level)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)

    fmt = colorlog.ColoredFormatter(LOG_FORMAT, log_colors=LOG_COLORS)
    stream_handler.setFormatter(fmt)

    if not logger.handlers:
        logger.addHandler(stream_handler)

    return logger


log = init_log()


def init():
    """ 输出初始化信息 """
    banner_lines = [
        r"                     /$$       /$$                       /$$               /$$ /$$",
        r"                    |__/      |__/                      | $$              | $$| $$",
        r"  /$$$$$$$  /$$$$$$  /$$       /$$ /$$$$$$$   /$$$$$$$ /$$$$$$    /$$$$$$ | $$| $$",
        r" /$$_____/ |____  $$| $$      | $$| $$__  $$ /$$_____/|_  $$_/   |____  $$| $$| $$",
        r"| $$        /$$$$$$$| $$      | $$| $$  \ $$|  $$$$$$   | $$      /$$$$$$$| $$| $$",
        r"| $$       /$$__  $$| $$      | $$| $$  | $$ \____  $$  | $$ /$$ /$$__  $$| $$| $$",
        r"|  $$$$$$$|  $$$$$$$| $$      | $$| $$  | $$ /$$$$$$$/  |  $$$$/|  $$$$$$$| $$| $$",
        r" \_______/ \_______/|__/      |__/|__/  |__/|_______/    \___/   \_______/|__/|__/",
    ]
    for line in banner_lines:
        log.info(line)



    log.info('软件作者:pvzcxw')
    log.info('本项目采用GNU General Public License v3开源许可证, 请勿用于商业用途')
    log.info('Cai install XP版本：1.35b1-fix1')
    log.info(
        'Cai install项目Github仓库: https://github.com/pvzcxw/cai-install_stloader'
    )
    log.warning(
        '菜Games出品 本项目完全开源免费，作者b站:菜Games-pvzcxw,因为清单库成本,请多多赞助使用'
    )
    log.warning(
        '官方Q群:993782526'
    )
    log.warning(
        'vdf writer v2  已接入自研manifest2lua se'
    )
    log.info('App ID可以在SteamDB, SteamUI或Steam商店链接页面查看')
    
async def search_all_repos(app_id, repos):
    """搜索所有GitHub仓库并返回结果列表"""
    github_token = config.get("Github_Personal_Token", "")
    headers = {'Authorization': f'Bearer {github_token}'} if github_token else None
    
    # 先检查一次GitHub API速率限制和CN连接性
    await checkcn()
    await check_github_api_rate_limit(headers)
    
    results = []
    for repo in repos:
        log.info(f"搜索仓库: {repo}")
        
        url = f'https://api.github.com/repos/{repo}/branches/{app_id}'
        r_json = await fetch_branch_info(url, headers)
        
        if r_json and 'commit' in r_json:
            sha = r_json['commit']['sha']
            url = r_json['commit']['commit']['tree']['url']
            r2_json = await fetch_branch_info(url, headers)
            
            if r2_json and 'tree' in r2_json:
                # 找到了清单文件，添加到结果列表
                update_date = r_json["commit"]["commit"]["author"]["date"]
                results.append({
                    'repo': repo,
                    'sha': sha,
                    'tree': r2_json['tree'],
                    'update_date': update_date
                })
                log.info(f"在仓库 {repo} 中找到清单，更新时间: {update_date}")
    
    if not results:
        log.error(f'在所有仓库中未找到清单: {app_id}')
    else:
        log.info(f'共在 {len(results)} 个仓库中找到清单')
    
    return results




async def find_appid_by_name(game_name):
    """通过游戏名找到AppID"""
    games = await search_game_info(game_name)

    if games:
        log.info("找到以下匹配的游戏:")
        for idx, game in enumerate(games, 1):
            # 显示中文名，如果没有则使用英文名
            game_name_display = game.get('schinese_name') or game.get('name', '')
            log.info(f"{idx}. {game_name_display} (AppID: {game['appid']})")

        choice = input("请选择游戏编号：")
        if choice.isdigit() and 1 <= int(choice) <= len(games):
            selected_game = games[int(choice) - 1]
            game_name_display = selected_game.get('schinese_name') or selected_game.get('name', '')
            log.info(f"选择的游戏: {game_name_display} (AppID: {selected_game['appid']})")
            return selected_game['appid']
    
    log.error("未找到匹配的游戏")
    return None

def stack_error(exception: Exception) -> str:
    """ 处理错误堆栈 """
    stack_trace = traceback.format_exception(
        type(exception), exception, exception.__traceback__)
    return ''.join(stack_trace)
async def search_game_info(search_term):
    """从Steam API搜索游戏信息"""
    url = f'https://steamui.com/loadGames.php?search={search_term}'
    try:
        r = await client.get(url)
        if r.status_code == 200:
            data = r.json()
            games = data.get('games', [])
            return games
        else:
            log.error("获取游戏信息失败")
            return []
    except KeyboardInterrupt:
        log.info("程序已退出")
    except Exception as e:
        log.error(f"搜索游戏时出错: {stack_error(e)}")
        return []


async def gen_config_file():
    """ 生成配置文件 """
    try:
        async with aiofiles.open("./config.json", mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False))

        log.info('程序可能为第一次启动或配置重置,请填写配置文件后重新启动程序')
    except KeyboardInterrupt:
        log.info("程序已退出")
    except Exception as e:
        log.error(f'配置文件生成失败,{stack_error(e)}')


async def load_config():
    """ 加载配置文件 """
    if not os.path.exists('./config.json'):
        await gen_config_file()
        os.system('pause')
        sys.exit()

    try:
        async with aiofiles.open("./config.json", mode="r", encoding="utf-8") as f:
            config = json.loads(await f.read())
            return config
    except KeyboardInterrupt:
        log.info("程序已退出")
    except Exception as e:
        log.error(f"配置文件加载失败，原因: {stack_error(e)},重置配置文件中...")
        os.remove("./config.json")
        await gen_config_file()
        os.system('pause')
        sys.exit()

config = asyncio.run(load_config())


async def check_github_api_rate_limit(headers):
    """ 检查Github请求数 """

    if headers != None:
        log.info(f"您已配置Github Token")

    url = 'https://api.github.com/rate_limit'
    try:
        r = await client.get(url, headers=headers)
        r_json = r.json()
        if r.status_code == 200:
            rate_limit = r_json.get('rate', {})
            remaining_requests = rate_limit.get('remaining', 0)
            reset_time = rate_limit.get('reset', 0)
            reset_time_formatted = time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(reset_time))
            log.info(f'剩余请求次数: {remaining_requests}')
            if remaining_requests == 0:
                log.warning(f'GitHub API 请求数已用尽, 将在 {
                            reset_time_formatted} 重置,建议生成一个填在配置文件里')
        else:
            log.error('Github请求数检查失败, 网络错误')
    except KeyboardInterrupt:
        log.info("程序已退出")
    except httpx.ConnectError as e:
        log.error(f'检查Github API 请求数失败, {stack_error(e)}')
    except httpx.ConnectTimeout as e:
        log.error(f'检查Github API 请求数超时: {stack_error(e)}')
    except Exception as e:
        log.error(f'发生错误: {stack_error(e)}')


async def checkcn() -> bool:
    try:
        req = await client.get('https://mips.kugou.com/check/iscn?&format=json')
        body = req.json()
        scn = bool(body['flag'])
        if (not scn):
            log.info(
                f"您在非中国大陆地区({body['country']})上使用了项目, 已自动切换回Github官方下载CDN")
            os.environ['IS_CN'] = 'no'
            return False
        else:
            os.environ['IS_CN'] = 'yes'
            return True
    except KeyboardInterrupt:
        log.info("程序已退出")
    except httpx.ConnectError as e:
        os.environ['IS_CN'] = 'yes'
        log.warning('检查服务器位置失败，已忽略，自动认为你在中国大陆')
        log.warning(stack_error(e))
        return False

def parse_lua_file(lua_file_path):
    """解析Lua文件,提取addappid和setManifestid信息
    
    Args:
        lua_file_path (str): lua文件路径
        
    Returns:
        tuple: (depots字典, manifests字典)
        - depots格式: {depot_id: {"DecryptionKey": key}}
        - manifests格式: {app_id: manifest_id}
    """
    import re
    
    # 定义正则表达式匹配模式
    addappid_pattern = re.compile(r'addappid\((\d+),\s*1,\s*"([^"]+)"\)')
    setmanifestid_pattern = re.compile(r'setManifestid\((\d+),\s*"([^"]+)"(?:,\s*\d+)?\)')

    depots = {}  # 存储depot ID和解密密钥
    manifests = {}  # 存储app ID和manifest ID

    try:
        # 读取lua文件内容
        with open(lua_file_path, 'r', encoding='utf-8') as file:
            lua_content = file.read()

            # 提取所有addappid信息
            for match in addappid_pattern.finditer(lua_content):
                appid = match.group(1)  # depot ID
                decryption_key = match.group(2)  # 解密密钥
                depots[appid] = {"DecryptionKey": decryption_key}

            # 提取所有setManifestid信息
            for match in setmanifestid_pattern.finditer(lua_content):
                appid = match.group(1)  # app ID
                manifest_id = match.group(2)  # manifest ID
                manifests[appid] = manifest_id

        return depots, manifests

    except FileNotFoundError:
        print(f"错误: 找不到文件 {lua_file_path}")
        return {}, {}
    except Exception as e:
        print(f"解析lua文件时出错: {str(e)}")
        return {}, {}


async def depotkey_merge(config_path: Path, depots_config: dict) -> bool:
    if not config_path.exists():
        async with lock:
            log.error('Steam默认配置不存在, 可能是没有登录账号')
        return False

    try:
        async with aiofiles.open(config_path, encoding='utf-8') as f:
            content = await f.read()

        config = vdf.loads(content)
        steam = config.get('InstallConfigStore', {}).get('Software', {}).get('Valve') or \
            config.get('InstallConfigStore', {}).get(
                'Software', {}).get('valve')

        if steam is None:
            log.error('找不到Steam配置, 请检查配置文件')
            return False

        depots = steam.setdefault('depots', {})
        depots.update(depots_config.get('depots', {}))

        async with aiofiles.open(config_path, mode='w', encoding='utf-8') as f:
            new_context = vdf.dumps(config, pretty=True)
            await f.write(new_context)

        log.info('成功合并')
        return True
    except KeyboardInterrupt:
        log.info("程序已退出")
    except Exception as e:
        async with lock:
            log.error(f'合并失败, 原因: {e}')
        return False


async def get(sha: str, path: str, repo: str):
    if os.environ.get('IS_CN') == 'yes':
        url_list = [           
            f'https://cdn.jsdmirror.com/gh/{repo}@{sha}/{path}',
            f'https://raw.gitmirror.com/{repo}/{sha}/{path}',
            f'https://raw.dgithub.xyz/{repo}/{sha}/{path}',
            f'https://gh.akass.cn/{repo}/{sha}/{path}'
        ]
    else:
        url_list = [
            f'https://raw.githubusercontent.com/{repo}/{sha}/{path}'
        ]
    retry = 3
    while retry > 0:
        for url in url_list:
            try:
                r = await client.get(url, timeout=30)
                if r.status_code == 200:
                    return r.read()
                else:
                    log.error(f'获取失败: {path} - 状态码: {r.status_code}')
            except KeyboardInterrupt:
                log.info("程序已退出")
            except httpx.ConnectError as e:
                log.error(f'获取失败: {path} - 连接错误: {str(e)}')
            except httpx.ConnectTimeout as e:
                log.error(f'连接超时: {url} - 错误: {str(e)}')

        retry -= 1
        log.warning(f'重试剩余次数: {retry} - {path}')

    log.error(f'超过最大重试次数: {path}')
    raise Exception(f'无法下载: {path}')


async def get_manifest(sha: str, path: str, steam_path: Path, repo: str, current_app_id: str = None) -> list:
    """
    获取清单文件
    
    Args:
        sha: GitHub提交SHA
        path: 文件路径
        steam_path: Steam安装路径
        repo: GitHub仓库
        current_app_id: 当前正在处理的AppID，添加此参数用于正确命名Lua文件
        
    Returns:
        list: 收集到的depot信息列表
    """
    collected_depots = []
    depot_cache_path = steam_path / 'depotcache'
    config_depot_cache_path = steam_path / 'config' / 'depotcache'
    stplug_path = steam_path / 'config' / 'stplug-in'
    
    # 用于收集清单文件信息的列表
    manifest_files = []

    try:
        # 确保目录存在
        depot_cache_path.mkdir(exist_ok=True)
        config_depot_cache_path.mkdir(parents=True, exist_ok=True)
        stplug_path.mkdir(exist_ok=True)

        if path.endswith('.manifest'):
            # 下载文件并保存到两个不同的位置
            save_path_1 = depot_cache_path / path
            save_path_2 = config_depot_cache_path / path

            # 如果文件已经存在，跳过下载
            if save_path_1.exists() and save_path_2.exists():
                log.warning(f'清单已存在: {path}')
                # 即使文件已存在，也记录清单名称，用于后续添加setManifestid
                manifest_files.append(path)
                return collected_depots

            # 获取文件内容
            content = await get(sha, path, repo)
            log.info(f'清单下载成功: {path}')

            # 保存文件到第一个位置
            async with aiofiles.open(save_path_1, 'wb') as f:
                await f.write(content)

            # 保存文件到第二个位置
            async with aiofiles.open(save_path_2, 'wb') as f:
                await f.write(content)
            
            # 记录清单文件名
            manifest_files.append(path)
                
        elif path.endswith('.lua'):
            # 如果是lua文件，直接下载到stplug-in文件夹
            save_path = stplug_path / path
            
            # 如果文件已经存在，跳过下载
            if save_path.exists():
                log.warning(f'Lua脚本已存在: {path}')
                return collected_depots
                
            # 获取文件内容
            content = await get(sha, path, repo)
            log.info(f'Lua脚本下载成功: {path}')
            
            # 保存文件到stplug-in文件夹
            async with aiofiles.open(save_path, 'wb') as f:
                await f.write(content)
            log.info(f'Lua脚本已保存到: {save_path}')

        elif "key.vdf" in path.lower():
            content = await get(sha, path, repo)
            log.info(f'密钥下载成功: {path}')
            depots_config = vdf.loads(content.decode('utf-8'))
            collected_depots = [
                (depot_id, depot_info['DecryptionKey'])
                for depot_id, depot_info in depots_config['depots'].items()
            ]
            
            # 如果是SteamTools，将key.vdf转换为lua脚本并保存
            if isSteamTools and current_app_id:
                try:
                    # 使用传入的current_app_id作为Lua文件名的基础，确保不会生成key.lua
                    lua_filename = f"{current_app_id}.lua"
                    lua_filepath = stplug_path / lua_filename
                    log.info(f'为SteamTools创建Lua脚本: {lua_filepath}')
                    
                    # 检查是否已存在此lua文件
                    lua_content = []
                    if lua_filepath.exists():
                        with open(lua_filepath, 'r', encoding='utf-8') as f:
                            lua_content = f.readlines()
                    
                    # 先添加addappid调用
                    async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                        await lua_file.write(f'addappid({current_app_id}, 1, "None")\n')
                        for depot_id, depot_key in collected_depots:
                            await lua_file.write(f'addappid({depot_id}, 1, "{depot_key}")\n')
                        
                        # 解析已下载的清单文件名，添加setManifestid调用
                        for manifest_file in manifest_files:
                            # 解析文件名格式如 "depotid_manifestid.manifest"
                            manifest_match = re.search(r'(\d+)_(\w+)\.manifest', manifest_file)
                            if manifest_match:
                                depot_id = manifest_match.group(1)
                                manifest_id = manifest_match.group(2)
                                await lua_file.write(f'setManifestid({depot_id}, "{manifest_id}")\n')
                                log.info(f'已添加清单ID: {depot_id} -> {manifest_id}')
                        
                        # 如果原来的lua文件已存在，且有setManifestid调用，添加回去
                        for line in lua_content:
                            if 'setManifestid' in line and not any(depot_id in line for depot_id, _ in collected_depots):
                                await lua_file.write(line)
                    
                    log.info('Lua脚本创建成功，已直接保存到SteamTools插件目录')
                except Exception as e:
                    log.error(f'创建Lua脚本时出错: {e}')
    except KeyboardInterrupt:
        log.info("程序已退出")
    except Exception as e:
        log.error(f'处理失败: {path} - {stack_error(e)}')
        raise
    
    # 返回收集到的depot信息和manifest文件名列表
    return collected_depots


def get_steam_path() -> Path:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
        steam_path = Path(winreg.QueryValueEx(key, 'SteamPath')[0])

        custom_steam_path = config.get("Custom_Steam_Path", "").strip()
        return Path(custom_steam_path) if custom_steam_path else steam_path
    except KeyboardInterrupt:
        log.info("程序已退出")
    except Exception as e:
        log.error(f'Steam路径获取失败, {stack_error(e)}, 请检查是否正确安装Steam')
        os.system('pause')
        return Path()


steam_path = get_steam_path()
isGreenLuma = any((steam_path / dll).exists()
                  for dll in ['GreenLuma_2024_x86.dll', 'GreenLuma_2024_x64.dll', 'User32.dll'])
isSteamTools = (steam_path / 'config' / 'stUI').is_dir()
directory = Path(steam_path) / "config" / "stplug-in"
temp_path = Path('./temp')
setup_url = 'https://steamtools.net/res/SteamtoolsSetup.exe'
setup_file = temp_path / 'SteamtoolsSetup.exe'


async def download_setup_file() -> None:
    log.info('开始下载 SteamTools 安装程序...')
    try:
        r = await client.get(setup_url, timeout=30)
        if r.status_code == 200:
            async with aiofiles.open(setup_file, mode='wb') as f:
                await f.write(r.read())
            log.info('安装程序下载完成')
        else:
            log.error(f'网络错误，无法下载安装程序，状态码: {r.status_code}')
    except KeyboardInterrupt:
        log.info("程序已退出")
    except httpx.ConnectTimeout:
        log.error('下载时超时')
    except Exception as e:
        log.error(f'下载失败: {e}')


async def migrate(st_use: bool) -> None:
    try:
        if st_use:
            log.info('检测到你正在使用 SteamTools,尝试迁移旧文件')
            if directory.exists():
                for file in directory.iterdir():
                    if file.is_file() and file.name.startswith("Cai_unlock_"):
                        new_filename = file.name[len("Cai_unlock_"):]
                        try:
                            file.rename(directory / new_filename)
                            log.info(f'Renamed: {file.name} -> {new_filename}')
                        except Exception as e:
                            log.error(
                                f'重命名失败 {file.name} -> {new_filename}: {e}')
            else:
                log.error('故障,正在重新安装 SteamTools')
                temp_path.mkdir(parents=True, exist_ok=True)
                await download_setup_file(client)
                subprocess.run(str(setup_file), check=True)
                for file in temp_path.iterdir():
                    file.unlink()
                temp_path.rmdir()
        else:
            log.info('未使用 SteamTools,停止迁移')
    except KeyboardInterrupt:
        log.info("程序已退出")


async def stool_add(depot_data: list, app_id: str) -> bool:
    lua_filename = f"{app_id}.lua"
    lua_filepath = steam_path / "config" / "stplug-in" / lua_filename
    async with lock:
        log.info(f'SteamTools 解锁文件生成: {lua_filepath}')
        try:
            async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                await lua_file.write(f'addappid({app_id}, 1, "None")\n')
                for depot_id, depot_key in depot_data:
                    await lua_file.write(f'addappid({depot_id}, 1, "{depot_key}")\n')
            luapacka_path = steam_path / "config" / "stplug-in" / "luapacka.exe"
            log.info(f'正在处理文件: {lua_filepath}')
            result = subprocess.run(
                [str(luapacka_path), str(lua_filepath)],
                capture_output=True
            )
            if result.returncode != 0:
                log.error(f'调用失败: {result.stderr.decode()}')
                return False
            log.info('处理完成')
        except KeyboardInterrupt:
            log.info("程序已退出")
        except Exception as e:
            log.error(f'处理过程出现错误: {e}')
            return False
        finally:
            if lua_filepath.exists():
                os.remove(lua_filepath)
                log.info(f'删除临时文件: {lua_filepath}')
    return True


async def greenluma_add(depot_id_list: list) -> bool:
    app_list_path = steam_path / 'AppList'
    try:
        app_list_path.mkdir(parents=True, exist_ok=True)
        for file in app_list_path.glob('*.txt'):
            file.unlink(missing_ok=True)
        depot_dict = {
            int(i.stem): int(i.read_text(encoding='utf-8').strip())
            for i in app_list_path.iterdir() if i.is_file() and i.stem.isdecimal() and i.suffix == '.txt'
        }
        for depot_id in map(int, depot_id_list):
            if depot_id not in depot_dict.values():
                index = max(depot_dict.keys(), default=-1) + 1
                while index in depot_dict:
                    index += 1
                (app_list_path /
                 f'{index}.txt').write_text(str(depot_id), encoding='utf-8')
                depot_dict[index] = depot_id
        return True
    except Exception as e:
        print(f'处理时出错: {e}')
        return False


async def fetch_branch_info(url, headers) -> str | None:
    try:
        r = await client.get(url, headers=headers)
        return r.json()
    except KeyboardInterrupt:
        log.info("程序已退出")
    except Exception as e:
        log.error(f'获取信息失败: {stack_error(e)}')
        return None
    except httpx.ConnectTimeout as e:
        log.error(f'获取信息时超时: {stack_error(e)}')
        return None


async def get_latest_repo_info(repos: list, app_id: str, headers) -> Any | None:
    latest_date = None
    selected_repo = None
    for repo in repos:
        url = f'https://api.github.com/repos/{repo}/branches/{app_id}'
        r_json = await fetch_branch_info(url, headers)
        if r_json and 'commit' in r_json:
            date = r_json['commit']['commit']['author']['date']
            if (latest_date is None) or (date > latest_date):
                latest_date = date
                selected_repo = repo

    return selected_repo, latest_date

def extract_app_id(user_input: str):
    try:
        # 尝试匹配Steam商店和SteamDB链接的正则表达式
        app_id_match_steam = re.search(r"https://store\.steampowered\.com/app/(\d+)", user_input)
        app_id_match_steamdb = re.search(r"https://steamdb\.info/app/(\d+)", user_input)
        
        # 如果检测到Steam商店的URL
        if app_id_match_steam:
            app_id = app_id_match_steam.group(1)
            log.info(f"检测到 Steam 商店链接，已提取 APP ID: {app_id}")
        
        # 如果检测到SteamDB的URL
        elif app_id_match_steamdb:
            app_id = app_id_match_steamdb.group(1)
            log.info(f"检测到 SteamDB 链接，已提取 APP ID: {app_id}")
        
        # 如果用户直接输入了数字作为App ID
        elif user_input.isdigit():
            app_id = user_input
            log.info(f"输入的 APP ID: {app_id}")
        
        # 如果输入无法识别为有效的链接或App ID，可能是游戏名称
        else:
            return None  # 返回None，但不打印错误，因为可能是游戏名称
            
        return app_id

    except Exception as e:
        log.error(f"提取 APP ID 时出错: {e}")
        return None  # 如果发生错误，返回None
       
async def process_Assiw_manifest(app_id: str, steam_path: Path) -> bool:
    """处理来自assiw.cngames.site的清单文件"""
    download_url = f'https://assiw.cngames.site/qindan/{app_id}.zip'  # 修改下载地址
    temp_dir = Path('./temp')
    zip_path = temp_dir / f'{app_id}.zip'
    extract_path = temp_dir / app_id

    try:
        # 创建临时目录
        temp_dir.mkdir(exist_ok=True)
        
        # 下载zip文件
        log.info(f'正在下载清单文件')
        response = await client.get(download_url)
        if response.status_code != 200:
            log.error(f'下载失败，状态码: {response.status_code}')
            log.info('按任意键返回...')
            os.system('pause')
            return False
            
        async with aiofiles.open(zip_path, 'wb') as f:
            await f.write(response.content)
        
        # 解压文件
        log.info('正在解压文件...')
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        
        # 后续处理逻辑与cysaw完全相同
        manifest_files = list(extract_path.glob('*.manifest'))
        lua_files = list(extract_path.glob('*.lua'))
        
        is_steamtools = any(extract_path.glob('*.manifest')) and any(extract_path.glob('*.lua'))
        
        if is_steamtools:
            log.info('检测到SteamTools入库文件')
            steam_depot_path = steam_path / 'config' / 'depotcache'
            steam_depot_path.mkdir(parents=True, exist_ok=True)
            
            for manifest in manifest_files:
                target_path = steam_depot_path / manifest.name
                shutil.copy2(manifest, target_path)
                log.info(f'已复制manifest文件: {manifest.name}')
            
            stplug_path = steam_path / 'config' / 'stplug-in'
            stplug_path.mkdir(parents=True, exist_ok=True)
            
            for lua in lua_files:
                target_path = stplug_path / lua.name
                shutil.copy2(lua, target_path)
                log.info(f'已复制lua文件: {lua.name}')
                    
        else:
            log.info('检测到GreenLuma入库文件')
            steam_depot_path = steam_path / 'depotcache'
            steam_depot_path.mkdir(parents=True, exist_ok=True)
            
            for manifest in manifest_files:
                target_path = steam_depot_path / manifest.name
                shutil.copy2(manifest, target_path)
                log.info(f'已复制manifest文件: {manifest.name}')
            
            for lua in lua_files:
                depots, manifests = parse_lua_file(str(lua))
                if depots:
                    config_path = steam_path / 'config' / 'config.vdf'
                    await depotkey_merge(config_path, {'depots': depots})
                    log.info(f'已合并lua文件内容到config.vdf: {lua.name}')
        
        log.info('清单处理完成')
        os.system('pause')
        return True
        
    except Exception as e:
        log.error(f'处理清单文件时出错: {stack_error(e)}')
        return False
        
    finally:
        if zip_path.exists():
            zip_path.unlink()
        if extract_path.exists():
            shutil.rmtree(extract_path)
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except OSError:
                pass              
                
async def process_steamdatabase_manifest(app_id: str, steam_path: Path) -> bool:
    """处理来自 steamdatabase.s3.eu-north-1.amazonaws.com 的清单文件"""
    download_url = f'https://steamdatabase.s3.eu-north-1.amazonaws.com/{app_id}.zip'
    temp_dir = Path('./temp')
    zip_path = temp_dir / f'{app_id}.zip'
    extract_path = temp_dir / app_id

    try:
        # 创建临时目录
        temp_dir.mkdir(exist_ok=True)

        # 下载zip文件
        log.info(f'正在从 SteamDatabase 下载清单文件')
        response = await client.get(download_url)
        if response.status_code != 200:
            log.error(f'下载失败，状态码: {response.status_code}')
            log.info('按任意键返回...')
            os.system('pause')
            return False

        async with aiofiles.open(zip_path, 'wb') as f:
            await f.write(response.content)

        # 解压文件
        log.info('正在解压文件...')
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        # 后续处理逻辑与4号库完全相同
        manifest_files = list(extract_path.glob('*.manifest'))
        lua_files = list(extract_path.glob('*.lua'))

        is_steamtools = any(extract_path.glob('*.manifest')) and any(extract_path.glob('*.lua'))

        if is_steamtools:
            log.info('检测到SteamTools入库文件')
            steam_depot_path = steam_path / 'config' / 'depotcache'
            steam_depot_path.mkdir(parents=True, exist_ok=True)

            for manifest in manifest_files:
                target_path = steam_depot_path / manifest.name
                shutil.copy2(manifest, target_path)
                log.info(f'已复制manifest文件: {manifest.name}')

            stplug_path = steam_path / 'config' / 'stplug-in'
            stplug_path.mkdir(parents=True, exist_ok=True)

            for lua in lua_files:
                target_path = stplug_path / lua.name
                shutil.copy2(lua, target_path)
                log.info(f'已复制lua文件: {lua.name}')

        else:
            log.info('检测到GreenLuma入库文件')
            steam_depot_path = steam_path / 'depotcache'
            steam_depot_path.mkdir(parents=True, exist_ok=True)

            for manifest in manifest_files:
                target_path = steam_depot_path / manifest.name
                shutil.copy2(manifest, target_path)
                log.info(f'已复制manifest文件: {manifest.name}')

            for lua in lua_files:
                depots, manifests = parse_lua_file(str(lua))
                if depots:
                    config_path = steam_path / 'config' / 'config.vdf'
                    await depotkey_merge(config_path, {'depots': depots})
                    log.info(f'已合并lua文件内容到config.vdf: {lua.name}')

        log.info('清单处理完成')
        os.system('pause')
        return True

    except Exception as e:
        log.error(f'处理清单文件时出错: {stack_error(e)}')
        return False

    finally:
        if zip_path.exists():
            zip_path.unlink()
        if extract_path.exists():
            shutil.rmtree(extract_path)
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except OSError:
                pass
                      
async def process_printedwaste_manifest(app_id: str, steam_path: Path) -> bool:
    """Process manifest files from printedwaste.com"""
    download_url = f'https://api.printedwaste.com/gfk/download/{app_id}'
    temp_dir = Path('./temp')
    zip_path = temp_dir / f'{app_id}.zip'
    extract_path = temp_dir / app_id
    st_converter = STConverter()

    try:
        # Create temp directory
        temp_dir.mkdir(exist_ok=True)
        
        # Download zip file
        log.info(f'正在下载清单文件')
        response = await client.get(download_url)
        if response.status_code != 200:
            log.error(f'下载失败，状态码: {response.status_code}')
            log.info('按任意键返回...')
            os.system('pause')
            return False
            
        async with aiofiles.open(zip_path, 'wb') as f:
            await f.write(response.content)
        
        # Extract files
        log.info('正在解压文件...')
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        
        # Convert .st files to .lua
        st_files = list(extract_path.glob('*.st'))
        for st_file in st_files:
            try:
                lua_content = st_converter.convert_file(str(st_file))
                lua_path = st_file.with_suffix('.lua')
                async with aiofiles.open(lua_path, 'w', encoding='utf-8') as f:
                    await f.write(lua_content)
                log.info(f'已转换ST文件: {st_file.name} -> {lua_path.name}')
            except Exception as e:
                log.error(f'转换ST文件失败: {st_file.name} - {e}')
        
        # Check installation type and process files
        manifest_files = list(extract_path.glob('*.manifest'))
        lua_files = list(extract_path.glob('*.lua'))
        
        # Detect if it's a SteamTools installation
        is_steamtools = any(extract_path.glob('*.manifest')) and any(extract_path.glob('*.lua'))
        
        if is_steamtools:
            log.info('检测到SteamTools入库文件')
            # Process manifest files
            steam_depot_path = steam_path / 'config' / 'depotcache'
            steam_depot_path.mkdir(parents=True, exist_ok=True)
            
            for manifest in manifest_files:
                target_path = steam_depot_path / manifest.name
                shutil.copy2(manifest, target_path)
                log.info(f'已复制manifest文件: {manifest.name}')
            
            # Process lua files - 直接复制，不执行luapacka
            stplug_path = steam_path / 'config' / 'stplug-in'
            stplug_path.mkdir(parents=True, exist_ok=True)
            
            for lua in lua_files:
                target_path = stplug_path / lua.name
                shutil.copy2(lua, target_path)
                log.info(f'已复制lua文件: {lua.name}')
                # 删除第一库和第二库的luapacka操作，直接完成
                
        else:
            log.info('检测到GreenLuma入库文件')
            # Process manifest files
            steam_depot_path = steam_path / 'depotcache'
            steam_depot_path.mkdir(parents=True, exist_ok=True)
            
            for manifest in manifest_files:
                target_path = steam_depot_path / manifest.name
                shutil.copy2(manifest, target_path)
                log.info(f'已复制manifest文件: {manifest.name}')
            
            # Process lua file content into config.vdf
            for lua in lua_files:
                depots, manifests = parse_lua_file(str(lua))
                if depots:
                    config_path = steam_path / 'config' / 'config.vdf'
                    await depotkey_merge(config_path, {'depots': depots})
                    log.info(f'已合并lua文件内容到config.vdf: {lua.name}')
        
        log.info('清单处理完成')
        log.info('按任意键返回...')
        os.system('pause')
        return True
        
    except Exception as e:
        log.error(f'处理清单文件时出错: {stack_error(e)}')
        return False
        
    finally:
        # Clean up temporary files
        if zip_path.exists():
            zip_path.unlink()
        if extract_path.exists():
            shutil.rmtree(extract_path)
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)  # Ensure temp_dir and all its contents are deleted
            except OSError:
                pass

class STConverter:
    """Handles conversion of .st files to .lua files"""
    def __init__(self):
        self.logger = logging.getLogger('STConverter')

    def convert_file(self, st_path: str) -> str:
        """Convert a .st file to lua content"""
        try:
            content, metadata = self.parse_st_file(st_path)
            return content
        except Exception as e:
            self.logger.error(f'转换失败: {st_path} - {e}')
            raise

    def parse_st_file(self, st_file_path: str) -> Tuple[str, dict]:
        """Parse .st file and return content and metadata"""
        try:
            with open(st_file_path, 'rb') as stfile:
                content = stfile.read()
                
            header = content[:12]
            if len(header) < 12:
                raise ValueError("文件头长度不足")
                
            xorkey, size, xorkeyverify = struct.unpack('III', header)
            xorkey ^= 0xFFFEA4C8
            xorkey &= 0xFF
            
            encrypted_data = content[12:12+size]
            if len(encrypted_data) < size:
                raise ValueError(f"数据长度不足")
                
            data = bytearray(encrypted_data)
            for i in range(len(data)):
                data[i] ^= xorkey
                
            decompressed_data = zlib.decompress(data)
            content = decompressed_data[512:].decode('utf-8')
            
            metadata = {
                'original_xorkey': xorkey,
                'size': size,
                'xorkeyverify': xorkeyverify
            }
            
            return content, metadata
            
        except Exception as e:
            self.logger.error(f'处理文件失败: {st_file_path} - {e}')
            raise


async def process_cysaw_manifest(app_id: str, steam_path: Path) -> bool:
    """处理来自cysaw.top的清单文件"""
    download_url = f'https://cysaw.top/uploads/{app_id}.zip'
    temp_dir = Path('./temp')
    zip_path = temp_dir / f'{app_id}.zip'
    extract_path = temp_dir / app_id

    try:
        # 创建临时目录
        temp_dir.mkdir(exist_ok=True)
        
        # 下载zip文件
        log.info(f'正在下载清单文件')
        response = await client.get(download_url)
        if response.status_code != 200:
            log.error(f'下载失败，状态码: {response.status_code}')
            log.info('按任意键返回...')
            os.system('pause')
            return False
            
        async with aiofiles.open(zip_path, 'wb') as f:
            await f.write(response.content)
        
        # 解压文件
        log.info('正在解压文件...')
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        
        # 检查入库类型并处理文件
        manifest_files = list(extract_path.glob('*.manifest'))
        lua_files = list(extract_path.glob('*.lua'))
        
        # 检测是否有steamtools特定文件
        is_steamtools = any(extract_path.glob('*.manifest')) and any(extract_path.glob('*.lua'))
        
        if is_steamtools:
            log.info('检测到SteamTools入库文件')
            # 处理manifest文件
            steam_depot_path = steam_path / 'config' / 'depotcache'
            steam_depot_path.mkdir(parents=True, exist_ok=True)
            
            for manifest in manifest_files:
                target_path = steam_depot_path / manifest.name
                shutil.copy2(manifest, target_path)
                log.info(f'已复制manifest文件: {manifest.name}')
            
            # 处理lua文件 - 直接复制，不执行luapacka
            stplug_path = steam_path / 'config' / 'stplug-in'
            stplug_path.mkdir(parents=True, exist_ok=True)
            
            for lua in lua_files:
                target_path = stplug_path / lua.name
                shutil.copy2(lua, target_path)
                log.info(f'已复制lua文件: {lua.name}')
                # 删除第二库的luapacka操作，直接完成
                    
        else:
            log.info('检测到GreenLuma入库文件')
            # 处理manifest文件
            steam_depot_path = steam_path / 'depotcache'
            steam_depot_path.mkdir(parents=True, exist_ok=True)
            
            for manifest in manifest_files:
                target_path = steam_depot_path / manifest.name
                shutil.copy2(manifest, target_path)
                log.info(f'已复制manifest文件: {manifest.name}')
            
            # 处理lua文件内容到config.vdf
            for lua in lua_files:
                depots, manifests = parse_lua_file(str(lua))
                if depots:
                    config_path = steam_path / 'config' / 'config.vdf'
                    await depotkey_merge(config_path, {'depots': depots})
                    log.info(f'已合并lua文件内容到config.vdf: {lua.name}')
        
        log.info('清单处理完成')
        log.info('按任意键返回...')
        os.system('pause')
        return True
        
    except Exception as e:
        log.error(f'处理清单文件时出错: {stack_error(e)}')
        log.info('按任意键返回...')
        os.system('pause')
        return False
        
    finally:
        # 清理临时文件
        if zip_path.exists():
            zip_path.unlink()
        if extract_path.exists():
            shutil.rmtree(extract_path)  # 确保删除目录及其内容
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)  # 删除临时文件夹及其所有内容
            except OSError:
                pass

async def process_furcate_manifest(app_id: str, steam_path: Path) -> bool:
    """处理来自furcate.eu的清单文件"""
    download_url = f'https://furcate.eu/files/{app_id}.zip'  # 修改下载地址
    temp_dir = Path('./temp')
    zip_path = temp_dir / f'{app_id}.zip'
    extract_path = temp_dir / app_id

    try:
        # 创建临时目录
        temp_dir.mkdir(exist_ok=True)
        
        # 下载zip文件
        log.info(f'正在下载清单文件')
        response = await client.get(download_url)
        if response.status_code != 200:
            log.error(f'下载失败，状态码: {response.status_code}')
            log.info('按任意键返回...')
            os.system('pause')
            return False
            
        async with aiofiles.open(zip_path, 'wb') as f:
            await f.write(response.content)
        
        # 解压文件
        log.info('正在解压文件...')
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        
        # 检查入库类型并处理文件（后续步骤与cysaw相同）
        manifest_files = list(extract_path.glob('*.manifest'))
        lua_files = list(extract_path.glob('*.lua'))
        
        # 检测是否有steamtools特定文件
        is_steamtools = any(extract_path.glob('*.manifest')) and any(extract_path.glob('*.lua'))
        
        if is_steamtools:
            log.info('检测到SteamTools入库文件')
            steam_depot_path = steam_path / 'config' / 'depotcache'
            steam_depot_path.mkdir(parents=True, exist_ok=True)
            
            for manifest in manifest_files:
                target_path = steam_depot_path / manifest.name
                shutil.copy2(manifest, target_path)
                log.info(f'已复制manifest文件: {manifest.name}')
            
            stplug_path = steam_path / 'config' / 'stplug-in'
            stplug_path.mkdir(parents=True, exist_ok=True)
            
            for lua in lua_files:
                target_path = stplug_path / lua.name
                shutil.copy2(lua, target_path)
                log.info(f'已复制lua文件: {lua.name}')
                    
        else:
            log.info('检测到GreenLuma入库文件')
            steam_depot_path = steam_path / 'depotcache'
            steam_depot_path.mkdir(parents=True, exist_ok=True)
            
            for manifest in manifest_files:
                target_path = steam_depot_path / manifest.name
                shutil.copy2(manifest, target_path)
                log.info(f'已复制manifest文件: {manifest.name}')
            
            for lua in lua_files:
                depots, manifests = parse_lua_file(str(lua))
                if depots:
                    config_path = steam_path / 'config' / 'config.vdf'
                    await depotkey_merge(config_path, {'depots': depots})
                    log.info(f'已合并lua文件内容到config.vdf: {lua.name}')
        
        log.info('清单处理完成')
        os.system('pause')
        return True
        
    except Exception as e:
        log.error(f'处理清单文件时出错: {stack_error(e)}')
        return False
        
    finally:
        if zip_path.exists():
            zip_path.unlink()
        if extract_path.exists():
            shutil.rmtree(extract_path)
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except OSError:
                pass



async def cleanup_temp_files():
    """Clean up temporary files and folders"""
    try:
        if temp_path.exists():
            for file in temp_path.glob('*'):
                if file.is_file():
                    file.unlink()
                elif file.is_dir():
                    shutil.rmtree(file)
            temp_path.rmdir()
            log.info('临时文件清理完成')
    except Exception as e:
        log.error(f'清理临时文件失败: {stack_error(e)}')

async def main(app_id: str, repos: list) -> bool:
    try:
        # 获取用户输入
        app_id_input = input(f"{Fore.CYAN}{Back.BLACK}{Style.BRIGHT}请输入游戏AppID、steamdb/steam链接或游戏名称(多个请用英文逗号分隔): {Style.RESET_ALL}").strip()
        
        # 按逗号分割输入
        app_id_inputs = [input_item.strip() for input_item in app_id_input.split(',')]
        
        # 让用户选择如何查找清单
        print(f"{Fore.YELLOW}请选择清单查找方式：")
        print(f"{Fore.CYAN}1. 从指定清单库中选择")
        print(f"{Fore.CYAN}2. 使用游戏名称或appid搜索清单(仅支持github清单库){Style.RESET_ALL}")
        
        try:
            search_choice = int(input(f"{Fore.GREEN}请输入数字选择查找方式: {Style.RESET_ALL}"))
            
            if search_choice == 1:
                # 原有的清单库选择逻辑
                print(f"{Fore.YELLOW}请选择清单库：")
                print(f"{Fore.CYAN}1. SWA V2库")
                print(f"{Fore.CYAN}2. Cysaw库")
                print(f"{Fore.CYAN}3. Furcate库")  
                print(f"{Fore.CYAN}4. CNGS库")
                print(f"{Fore.CYAN}5. SteamDatabase库")
                for index, repo in enumerate(repos, 6):
                    print(f"{Fore.CYAN}{index}. {repo}{Style.RESET_ALL}")
                
                user_choice = int(input(f"{Fore.GREEN}请输入数字选择清单库: {Style.RESET_ALL}"))
                
                # 提取所有有效的AppID
                app_ids = []
                for input_item in app_id_inputs:
                    extracted_id = extract_app_id(input_item)
                    if extracted_id:
                        app_ids.append(extracted_id)
                
                # 如果没有找到有效的AppID，打印错误并退出
                if not app_ids:
                    log.error("无法获取有效的App ID，请重试。")
                    await cleanup_temp_files()
                    return False
                
                log.info(f"成功提取的 App IDs: {', '.join(app_ids)}")
                
                # 处理每个app_id
                overall_success = True
                for app_id in app_ids:
                    log.info(f"正在处理 App ID: {app_id}")
                    
                    if user_choice == 1:
                        # 使用PrintedWaste源 - 修改处理方式
                        if isSteamTools:
                            log.info('检测到SteamTools，将直接处理Lua脚本')
                        success = await process_printedwaste_manifest(app_id, steam_path)
                    elif user_choice == 2:
                        # 使用cysaw.top源 - 修改处理方式
                        if isSteamTools:
                            log.info('检测到SteamTools，将直接处理Lua脚本')
                        success = await process_cysaw_manifest(app_id, steam_path)
                        
                    elif user_choice == 3:  
                        success = await process_furcate_manifest(app_id, steam_path)
                        
                    elif user_choice == 4:
                        success = await process_Assiw_manifest(app_id, steam_path)

                    elif user_choice == 5:
                        success = await process_steamdatabase_manifest(app_id, steam_path)
                    
                    else:
                        # 使用GitHub源
                        selected_repo = repos[user_choice - 6]
                        log.info(f"您选择了仓库: {selected_repo}")
                        
                        # 处理GitHub源
                        github_token = config.get("Github_Personal_Token", "")
                        headers = {'Authorization': f'Bearer {github_token}'} if github_token else None
                        
                        # 只检查一次GitHub API速率限制
                        if app_id == app_ids[0]:
                            await checkcn()
                            await check_github_api_rate_limit(headers)
                        
                        url = f'https://api.github.com/repos/{selected_repo}/branches/{app_id}'
                        r_json = await fetch_branch_info(url, headers)
                        if r_json and 'commit' in r_json:
                            sha = r_json['commit']['sha']
                            url = r_json['commit']['commit']['tree']['url']
                            r2_json = await fetch_branch_info(url, headers)
                            if r2_json and 'tree' in r2_json:
                                collected_depots = []
                                for item in r2_json['tree']:
                                    # 关键修改：传递当前处理的app_id参数给get_manifest函数
                                    result = await get_manifest(sha, item['path'], steam_path, selected_repo, current_app_id=app_id)
                                    collected_depots.extend(result)
                                if collected_depots:
                                    if isSteamTools:
                                        await migrate(st_use=True)
                                        # 不要再调用stool_add，因为get_manifest已经创建并保存了Lua脚本
                                        log.info('找到SteamTools, 已添加解锁文件')
                                    elif isGreenLuma:
                                        await migrate(st_use=False)
                                        await greenluma_add([app_id])
                                        depot_config = {'depots': {depot_id: {'DecryptionKey': depot_key} for depot_id, depot_key in collected_depots}}
                                        await depotkey_merge(steam_path / 'config' / 'config.vdf', depot_config)
                                        if await greenluma_add([int(i) for i in depot_config['depots'] if i.isdecimal()]):
                                            log.info('找到GreenLuma, 已添加解锁文件')
                                    log.info(f'清单最后更新时间: {r_json["commit"]["commit"]["author"]["date"]}')
                                    log.info(f'入库成功: {app_id}')
                                    success = True
                                else:
                                    log.error(f'没有找到有效的清单文件: {app_id}')
                                    success = False
                            else:
                                log.error(f'无法获取仓库文件列表')
                                success = False
                        else:
                            log.error(f'无法获取分支信息,请检查网络或加速')
                            success = False
                    
                    # 更新整体成功状态
                    overall_success = overall_success and success
                
                # 清理临时文件
                await cleanup_temp_files()
                await client.aclose()
                os.system('pause')
                return overall_success
                
            elif search_choice == 2:
                # 修改后的游戏名称搜索逻辑，也需要修改
                github_repos = repos  # 使用所有GitHub仓库
                
                overall_success = True
                # 处理每个输入项
                for input_item in app_id_inputs:
                    app_id = extract_app_id(input_item)
                    
                    if not app_id:
                        app_id = await find_appid_by_name(input_item)
                    
                    if app_id:
                        log.info(f"开始为 App ID: {app_id} 搜索清单")
                        
                        repo_results = await search_all_repos(app_id, github_repos)
                        
                        if repo_results:
                            print(f"{Fore.YELLOW}在以下仓库中找到清单：")
                            for idx, result in enumerate(repo_results, 1):
                                print(f"{Fore.CYAN}{idx}. {result['repo']} (更新时间: {result['update_date']}){Style.RESET_ALL}")
                            
                            try:
                                choice = int(input(f"{Fore.GREEN}请选择要使用的仓库编号: {Style.RESET_ALL}"))
                                if 1 <= choice <= len(repo_results):
                                    selected = repo_results[choice - 1]
                                    log.info(f"选择了仓库: {selected['repo']}")
                                    
                                    sha = selected['sha']
                                    repo = selected['repo']
                                    collected_depots = []
                                    
                                    for item in selected['tree']:
                                        # 关键修改：在这里也传递当前处理的app_id参数
                                        result = await get_manifest(sha, item['path'], steam_path, repo, current_app_id=app_id)
                                        collected_depots.extend(result)
                                    
                                    if collected_depots:
                                        if isSteamTools:
                                            await migrate(st_use=True)
                                            # 不要再调用stool_add，因为get_manifest已经创建并保存了Lua脚本
                                            log.info('找到SteamTools, 已添加解锁文件')
                                        elif isGreenLuma:
                                            await migrate(st_use=False)
                                            await greenluma_add([app_id])
                                            depot_config = {'depots': {depot_id: {'DecryptionKey': depot_key} for depot_id, depot_key in collected_depots}}
                                            await depotkey_merge(steam_path / 'config' / 'config.vdf', depot_config)
                                            if await greenluma_add([int(i) for i in depot_config['depots'] if i.isdecimal()]):
                                                log.info('找到GreenLuma, 已添加解锁文件')
                                        log.info(f'清单最后更新时间: {selected["update_date"]}')
                                        log.info(f'入库成功: {app_id}')
                                        success = True
                                    else:
                                        log.error(f'清单文件处理失败: {app_id}')
                                        success = False
                                else:
                                    log.error("无效的选择")
                                    success = False
                            except ValueError:
                                log.error("请输入有效的数字")
                                success = False
                        else:
                            log.error(f"在所有仓库中未找到 {app_id} 的清单")
                            success = False
                        
                        overall_success = overall_success and success
                    else:
                        log.error(f"无法从 '{input_item}' 获取有效的App ID")
                        overall_success = False
                
                await cleanup_temp_files()
                await client.aclose()
                os.system('pause')
                return overall_success
                
            else:
                log.error("无效的选择，请选择1或2")
                await cleanup_temp_files()
                return False
                
        except (ValueError, IndexError) as e:
            log.error(f"无效的选择，请重试: {e}")
            await cleanup_temp_files()
            return False

    except Exception as e:
        log.error(f'处理过程出错: {stack_error(e)}')
        await cleanup_temp_files()
        return False
        
if __name__ == '__main__':
    try:
        # 检查是否有其他进程调用此软件
        #check_caller_process()
        
        # 显示提示窗口
        show_info_dialog()
        
        # 通过提示后，继续初始化
        init()
        
        repos = [
            'Auiowu/ManifestAutoUpdate',
            'SteamAutoCracks/ManifestHub',
        ]
        asyncio.run(main('', repos))  # 传递空字符串作为默认值
    except KeyboardInterrupt:
        log.info("程序已退出")
    except SystemExit:
        sys.exit()