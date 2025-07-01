# cai_install_gui_final.py
import sys
import os
import traceback
import time
import logging
import subprocess
import asyncio
import re
import aiofiles
import httpx
import winreg
import vdf
import json
import webbrowser
import zipfile
import shutil
import struct
import zlib
import tkinter as tk
from tkinter import messagebox, scrolledtext
from pathlib import Path
from typing import Tuple, Any, List
from colorama import init as colorama_init
import threading

# 使用 ttkbootstrap 创建现代化UI
try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
except ImportError:
    print("错误: ttkbootstrap 库未安装。")
    print("请使用 'pip install ttkbootstrap' 命令安装。")
    sys.exit(1)

# 全局变量
client = httpx.AsyncClient(verify=False, trust_env=True, timeout=60.0)
LOG_FORMAT = '[%(levelname)s] %(message)s' 
DEFAULT_CONFIG = {
    "Github_Personal_Token": "",
    "Custom_Steam_Path": "",
    "QA1": "温馨提示: Github_Personal_Token 可在Github设置->开发者选项->Personal access tokens中生成, 详情看教程"
}

class STConverter:
    def __init__(self, logger):
        self.logger = logger

    def convert_file(self, st_path: str) -> str:
        try:
            content, _ = self.parse_st_file(st_path)
            return content
        except Exception as e:
            self.logger.error(f'转换失败: {st_path} - {e}')
            raise

    def parse_st_file(self, st_file_path: str) -> Tuple[str, dict]:
        try:
            with open(st_file_path, 'rb') as stfile: content = stfile.read()
            header = content[:12]
            if len(header) < 12: raise ValueError("文件头长度不足")
            xorkey, size, _ = struct.unpack('III', header)
            xorkey ^= 0xFFFEA4C8
            xorkey &= 0xFF
            encrypted_data = content[12:12 + size]
            if len(encrypted_data) < size: raise ValueError(f"数据长度不足")
            data = bytearray(encrypted_data)
            for i in range(len(data)): data[i] ^= xorkey
            decompressed_data = zlib.decompress(data)
            content_str = decompressed_data[512:].decode('utf-8')
            metadata = {'original_xorkey': xorkey, 'size': size}
            return content_str, metadata
        except Exception as e:
            self.logger.error(f'处理ST文件失败: {st_file_path} - {e}')
            raise

# --- GUI Application Class ---
class CaiInstallGUI(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly", title="Cai Install XP v1.34b1 - GUI Edition")
        self.geometry("850x700") # Increased size for better banner display
        self.minsize(700, 550)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.app_config = {}
        self.steam_path = Path()
        self.isGreenLuma = False
        self.isSteamTools = False
        self.processing_lock = threading.Lock()
        
        self.create_widgets()
        self.log = self.setup_logging()
        self.st_converter = STConverter(self.log)
        
        self.create_menu()
        self.init_app()

    def setup_logging(self):
        logger = logging.getLogger('CaiInstall')
        logger.setLevel(logging.DEBUG)
        if logger.hasHandlers(): logger.handlers.clear()

        class GuiHandler(logging.Handler):
            def __init__(self, gui_app_instance):
                super().__init__()
                self.gui_app = gui_app_instance
                self.setFormatter(logging.Formatter(LOG_FORMAT))

            def emit(self, record):
                if self.gui_app:
                    msg = self.format(record)
                    self.gui_app.after(0, self.gui_app.update_log, msg, record.levelname)

        gui_handler = GuiHandler(self)
        logger.addHandler(gui_handler)
        return logger

    def update_log(self, msg, level, is_banner=False):
        try:
            self.log_text.configure(state='normal')
            tag = 'BANNER' if is_banner else level.upper()
            self.log_text.insert(tk.END, msg + '\n', tag)
            self.log_text.configure(state='disabled')
            self.log_text.see(tk.END)
        except tk.TclError: pass

    def create_menu(self):
        menu_bar = ttk.Menu(self)
        self.config(menu=menu_bar)

        settings_menu = ttk.Menu(menu_bar, tearoff=False)
        menu_bar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_command(label="编辑配置", command=self.show_settings_dialog)
        settings_menu.add_separator()
        settings_menu.add_command(label="退出", command=self.on_closing)

        help_menu = ttk.Menu(menu_bar, tearoff=False)
        menu_bar.add_cascade(label="更多", menu=help_menu)
        help_menu.add_command(label="公告提示", command=lambda: webbrowser.open('https://docs.qq.com/doc/DTUp3Z2Fkd2pVRGtX?dver='))
        help_menu.add_command(label="开源GitHub仓库", command=lambda: webbrowser.open('https://github.com/pvzcxw/cai-install_stloader'))
        help_menu.add_command(label="关于", command=self.show_about_dialog)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=BOTH, expand=True)
        
        input_frame = ttk.Labelframe(main_frame, text="输入区", padding=10)
        input_frame.pack(fill=X, pady=(0, 10))
        
        ttk.Label(input_frame, text="游戏AppID、链接或名称 (多个用英文逗号隔开):").pack(side=LEFT, padx=(0, 10))
        self.appid_entry = ttk.Entry(input_frame, font=("", 10))
        self.appid_entry.pack(side=LEFT, fill=X, expand=True)

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=X, pady=5)
        self.notebook = notebook

        tab1 = ttk.Frame(notebook, padding=10)
        notebook.add(tab1, text=" 从指定库安装 ")
        ttk.Label(tab1, text="选择清单库:").pack(side=LEFT, padx=(0, 10))
        self.repo_options = [
            ("SWA V2 (printedwaste)", "swa"), ("Cysaw", "cysaw"), ("Furcate", "furcate"), ("CNGS (assiw)", "cngs"),
            ("SteamDatabase", "steamdatabase"), # <-- 新增的清单库
            ("GitHub - Auiowu/ManifestAutoUpdate", "Auiowu/ManifestAutoUpdate"),
            ("GitHub - SteamAutoCracks/ManifestHub", "SteamAutoCracks/ManifestHub"),
        ]
        self.repo_combobox = ttk.Combobox(tab1, state="readonly", values=[name for name, val in self.repo_options])
        self.repo_combobox.pack(side=LEFT, fill=X, expand=True)
        self.repo_combobox.current(0)
        
        tab2 = ttk.Frame(notebook, padding=10)
        notebook.add(tab2, text=" 搜索所有GitHub库 ")
        ttk.Label(tab2, text="此模式将通过游戏名/AppID搜索所有已知的GitHub清单库。").pack(fill=X)

        self.process_button = ttk.Button(main_frame, text="开始处理", command=self.start_processing, style='success.TButton')
        self.process_button.pack(fill=X, pady=10)
        
        log_frame = ttk.Labelframe(main_frame, text="日志输出", padding=10)
        log_frame.pack(fill=BOTH, expand=True)
        # UPDATE: Set font to a monospace font for better ASCII art display
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state='disabled', font=("Courier New", 9), bg=self.style.colors.get('bg'), fg=self.style.colors.get('fg'))
        self.log_text.pack(fill=BOTH, expand=True)
        
        # Define tags for coloring
        self.log_text.tag_config('INFO', foreground=self.style.colors.info)
        self.log_text.tag_config('WARNING', foreground=self.style.colors.warning)
        self.log_text.tag_config('ERROR', foreground=self.style.colors.danger)
        self.log_text.tag_config('CRITICAL', foreground=self.style.colors.danger, font=("Courier New", 9, 'bold'))
        self.log_text.tag_config('BANNER', foreground=self.style.colors.primary) # Banner color
        
        self.status_bar = ttk.Label(self, text=" 准备就绪", relief=SUNKEN, anchor=W, padding=5)
        self.status_bar.pack(side=BOTTOM, fill=X)

    def init_app(self):
        self.print_banner() # Print banner first
        self.log.info("Cai Install XP GUI Edition - 正在初始化...")
        self.load_config()
        self.detect_steam()
        self.log.info(f"软件作者: pvzcxw | GUI重制:pvzcxw")
        self.log.warning("本项目采用GNU GPLv3开源许可证，完全免费，请勿用于商业用途。")
        self.log.warning("官方Q群: 993782526 | B站: 菜Games-pvzcxw")
        self.log.info(f"SteamTools模式: {'已启用' if self.isSteamTools else '未检测到'}")
        self.log.info(f"GreenLuma模式: {'已启用' if self.isGreenLuma else '未检测到'}")

    def start_processing(self):
        if not self.processing_lock.acquire(blocking=False):
            self.log.warning("已经在处理中，请等待当前任务完成。")
            return

        notebook_tab = self.notebook.index('current')
        
        def thread_target():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.run_async_tasks(notebook_tab))
            finally:
                self.processing_lock.release()
                self.after(0, self.processing_finished)
        
        self.process_button.config(state=DISABLED, text="正在处理...")
        self.appid_entry.config(state=DISABLED)
        self.status_bar.config(text="正在处理...")
        thread = threading.Thread(target=thread_target, daemon=True)
        thread.start()

    def processing_finished(self):
        self.process_button.config(state=NORMAL, text="开始处理")
        self.appid_entry.config(state=NORMAL)
        self.status_bar.config(text="处理完成，准备就绪。")
        self.log.info("="*80)
        self.log.info("处理完成！您可以开始新的任务。")
    
    async def run_async_tasks(self, tab_index):
        user_input = self.appid_entry.get().strip()
        if not user_input:
            self.log.error("输入不能为空！")
            return

        app_id_inputs = [item.strip() for item in user_input.split(',')]
        
        try:
            if tab_index == 0:
                repo_choice_index = self.repo_combobox.current()
                repo_name, repo_val = self.repo_options[repo_choice_index]
                self.log.info(f"选择了清单库: {repo_name}")
                await self.process_from_specific_repo(app_id_inputs, repo_val)
            elif tab_index == 1:
                self.log.info("模式: 搜索所有GitHub库")
                await self.process_by_searching_all(app_id_inputs)
        except Exception as e:
            self.log.error(f"处理过程中发生未知错误: {e}")
            self.log.error(self.stack_error(e))
        finally:
            await self.cleanup_temp_files()

    async def process_from_specific_repo(self, inputs, repo_val):
        app_ids = await self.resolve_appids(inputs)
        if not app_ids:
            self.log.error("未能解析出任何有效的AppID。")
            return
        
        self.log.info(f"成功解析的 App IDs: {', '.join(app_ids)}")
        
        # <-- 更新了这里的列表
        if repo_val not in ["swa", "cysaw", "furcate", "cngs", "steamdatabase"]:
            await self.checkcn()
            await self.check_github_api_rate_limit(self.get_github_headers())

        for app_id in app_ids:
            self.log.info(f"--- 正在处理 App ID: {app_id} ---")
            success = False
            if repo_val == "swa": success = await self.process_printedwaste_manifest(app_id, self.steam_path)
            elif repo_val == "cysaw": success = await self.process_cysaw_manifest(app_id, self.steam_path)
            elif repo_val == "furcate": success = await self.process_furcate_manifest(app_id, self.steam_path)
            elif repo_val == "cngs": success = await self.process_assiw_manifest(app_id, self.steam_path)
            elif repo_val == "steamdatabase": success = await self.process_steamdatabase_manifest(app_id, self.steam_path) # <-- 新增的逻辑分支
            else: success = await self.process_github_repo(app_id, repo_val)
            
            if success: self.log.info(f"App ID: {app_id} 处理成功。")
            else: self.log.error(f"App ID: {app_id} 处理失败。")

    async def process_by_searching_all(self, inputs):
        app_ids = await self.resolve_appids(inputs)
        if not app_ids: self.log.error("未能解析出任何有效的AppID。"); return

        # <-- 更新了这里的列表
        github_repos = [val for _, val in self.repo_options if val not in ["swa", "cysaw", "furcate", "cngs", "steamdatabase"]]
        await self.checkcn()
        await self.check_github_api_rate_limit(self.get_github_headers())
        
        for app_id in app_ids:
            self.log.info(f"--- 正在为 App ID: {app_id} 搜索所有GitHub库 ---")
            repo_results = await self.search_all_repos(app_id, github_repos)
            
            if not repo_results:
                self.log.error(f"在所有GitHub库中均未找到 {app_id} 的清单。"); continue

            repo_results.sort(key=lambda x: x['update_date'], reverse=True)
            selected = repo_results[0]
            self.log.info(f"找到 {len(repo_results)} 个结果，将使用最新的清单: {selected['repo']} (更新于 {selected['update_date']})")

            if await self.process_github_repo(app_id, selected['repo'], selected): self.log.info(f"App ID: {app_id} 处理成功。")
            else: self.log.error(f"App ID: {app_id} 处理失败。")

    async def resolve_appids(self, inputs: List[str]) -> List[str]:
        resolved_ids = []
        for item in inputs:
            if app_id := self.extract_app_id(item):
                resolved_ids.append(app_id); continue
            self.log.info(f"'{item}' 不是有效的ID或链接，尝试作为游戏名称搜索...")
            if found_id := await self.find_appid_by_name(item): resolved_ids.append(found_id)
            else: self.log.error(f"无法为 '{item}' 找到匹配的游戏。")
        return list(dict.fromkeys(resolved_ids))

    async def process_github_repo(self, app_id: str, repo: str, existing_data: dict = None) -> bool:
        try:
            if existing_data:
                sha, tree, date = existing_data['sha'], existing_data['tree'], existing_data['update_date']
            else:
                if not (r_json := await self.fetch_branch_info(f'https://api.github.com/repos/{repo}/branches/{app_id}', self.get_github_headers())):
                    self.log.error(f'无法获取分支信息，请检查网络或AppID是否存在于该仓库。'); return False
                sha, date = r_json['commit']['sha'], r_json["commit"]["commit"]["author"]["date"]
                if not (r2_json := await self.fetch_branch_info(r_json['commit']['commit']['tree']['url'], self.get_github_headers())):
                    self.log.error('无法获取仓库文件列表。'); return False
                tree = r2_json['tree']

            manifests = [item['path'] for item in tree if item['path'].endswith('.manifest')]
            tasks = [self.get_manifest(sha, item['path'], self.steam_path, repo, app_id, manifests) for item in tree]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            collected_depots = []
            for res in results:
                if isinstance(res, Exception): self.log.error(f"下载/处理文件时出错: {res}"); return False
                if res: collected_depots.extend(res)

            if not manifests and not collected_depots:
                 self.log.error(f'仓库中没有找到有效的清单文件或密钥文件: {app_id}'); return False

            if self.isSteamTools: self.log.info('检测到SteamTools，已自动生成并放置解锁文件。')
            elif collected_depots:
                if self.isGreenLuma: await self.greenluma_add([app_id])
                depot_cfg = {'depots': {depot_id: {'DecryptionKey': key} for depot_id, key in collected_depots}}
                await self.depotkey_merge(self.steam_path / 'config' / 'config.vdf', depot_cfg)
                if self.isGreenLuma: await self.greenluma_add([int(i) for i in depot_cfg['depots'] if i.isdecimal()])

            self.log.info(f'清单最后更新时间: {date}')
            return True
        except Exception as e:
            self.log.error(f"处理GitHub仓库时出错: {self.stack_error(e)}"); return False

    def on_closing(self):
        if self.processing_lock.locked():
            if messagebox.askyesno("退出", "正在处理任务，确定要强制退出吗？"):
                self.destroy(); os._exit(0)
        else:
            self.destroy(); sys.exit()

    def print_banner(self):
        banner = [
            r"                     /$$ /$$                       /$$               /$$ /$$",
            r"                    |__/|__/                      | $$              | $$| $$",
            r"  /$$$$$$$  /$$$$$$  /$$ /$$ /$$$$$$$   /$$$$$$$ /$$$$$$    /$$$$$$ | $$| $$",
            r" /$$_____/ |____  $$| $$| $$| $$__  $$ /$$_____/|_  $$_/   |____  $$| $$| $$",
            r"| $$        /$$$$$$$| $$| $$| $$  \ $$|  $$$$$$   | $$      /$$$$$$$| $$| $$",
            r"| $$       /$$__  $$| $$| $$| $$  | $$ \____  $$  | $$ /$$ /$$__  $$| $$| $$",
            r"|  $$$$$$$|  $$$$$$$| $$| $$| $$  | $$ /$$$$$$$/  |  $$$$/|  $$$$$$$| $$| $$",
            r" \_______/ \_______/|__/|__/|__/  |__/|_______/    \___/   \_______/|__/|__/",
        ]
        for line in banner: self.update_log(line, 'BANNER', is_banner=True)

    def show_about_dialog(self):
        messagebox.showinfo("关于", "Cai Install XP v1.35b1-fix1 - GUI Edition\n\n原作者: pvzcxw\nGUI重制:pvzcxw\n\n一个用于Steam游戏清单获取和导入的工具")
    
    def show_settings_dialog(self):
        dialog = ttk.Toplevel(self)
        dialog.title("编辑配置"); dialog.geometry("500x200"); dialog.transient(self); dialog.grab_set()
        frame = ttk.Frame(dialog, padding=15); frame.pack(fill=BOTH, expand=True)
        
        ttk.Label(frame, text="GitHub Personal Token:").grid(row=0, column=0, sticky=W, pady=5)
        token_entry = ttk.Entry(frame, width=50); token_entry.grid(row=0, column=1, sticky=EW, pady=5)
        token_entry.insert(0, self.app_config.get("Github_Personal_Token", ""))

        ttk.Label(frame, text="自定义Steam路径:").grid(row=1, column=0, sticky=W, pady=5)
        path_entry = ttk.Entry(frame, width=50); path_entry.grid(row=1, column=1, sticky=EW, pady=5)
        path_entry.insert(0, self.app_config.get("Custom_Steam_Path", ""))
        
        button_frame = ttk.Frame(frame); button_frame.grid(row=2, column=0, columnspan=2, pady=15)

        def save_and_close():
            self.app_config["Github_Personal_Token"] = token_entry.get()
            self.app_config["Custom_Steam_Path"] = path_entry.get()
            self.save_config()
            self.log.info("配置已保存。部分设置可能需要重启程序生效。"); self.detect_steam(); dialog.destroy()

        ttk.Button(button_frame, text="保存", command=save_and_close, style='success.TButton').pack(side=LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=LEFT, padx=10)
        frame.columnconfigure(1, weight=1)

    def gen_config_file(self):
        try:
            with open("./config.json", mode="w", encoding="utf-8") as f: json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
            self.log.info('首次启动或配置重置，已生成config.json，请在"设置"中填写。')
        except Exception as e: self.log.error(f'配置文件生成失败: {self.stack_error(e)}')
    
    def load_config(self):
        config_path = Path('./config.json')
        if not config_path.exists(): self.gen_config_file()
        try:
            with open(config_path, "r", encoding="utf-8") as f: self.app_config = json.load(f)
        except Exception as e:
            self.log.error(f"配置文件加载失败，将重置: {self.stack_error(e)}")
            if config_path.exists(): os.remove(config_path)
            self.gen_config_file(); self.load_config()
    
    def save_config(self):
        try:
            with open("./config.json", mode="w", encoding="utf-8") as f: json.dump(self.app_config, f, indent=2, ensure_ascii=False)
        except Exception as e: self.log.error(f'保存配置失败: {self.stack_error(e)}')

    def detect_steam(self):
        try:
            custom_path = self.app_config.get("Custom_Steam_Path", "").strip()
            if custom_path and Path(custom_path).exists():
                self.steam_path = Path(custom_path)
                self.log.info(f"使用自定义Steam路径: {self.steam_path}")
            else:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
                self.steam_path = Path(winreg.QueryValueEx(key, 'SteamPath')[0])
                self.log.info(f"自动检测到Steam路径: {self.steam_path}")

            self.isGreenLuma = any((self.steam_path / dll).exists() for dll in ['GreenLuma_2024_x86.dll', 'GreenLuma_2024_x64.dll', 'User32.dll'])
            self.isSteamTools = (self.steam_path / 'config' / 'stUI').is_dir()
            self.status_bar.config(text=f"Steam路径: {self.steam_path} | SteamTools: {'是' if self.isSteamTools else '否'}")
        except Exception:
            self.log.error('Steam路径获取失败，请检查Steam是否安装或在设置中指定路径。')
            self.status_bar.config(text="Steam路径未找到！"); self.steam_path = Path()

    def get_github_headers(self):
        return {'Authorization': f'Bearer {token}'} if (token := self.app_config.get("Github_Personal_Token", "")) else {}
    
    def stack_error(self, e: Exception) -> str: return ''.join(traceback.format_exception(type(e), e, e.__traceback__))

    async def check_github_api_rate_limit(self, headers):
        if headers: self.log.info("已配置Github Token。")
        else: self.log.warning("未配置Github Token，API请求次数有限，建议在设置中添加。")
        try:
            r = await client.get('https://api.github.com/rate_limit', headers=headers); r.raise_for_status()
            rate = r.json().get('rate', {})
            remaining, reset = rate.get('remaining', 0), time.strftime('%H:%M:%S', time.localtime(rate.get('reset', 0)))
            self.log.info(f'GitHub API 剩余请求次数: {remaining}')
            if remaining == 0: self.log.warning(f'API请求数已用尽，将在 {reset} 重置。')
        except Exception as e: self.log.error(f'检查GitHub API速率时出错: {e}')

    async def checkcn(self):
        try:
            r = await client.get('https://mips.kugou.com/check/iscn?&format=json')
            if not bool(r.json().get('flag')):
                self.log.info(f"检测到您在非中国大陆地区 ({r.json().get('country')})，将使用GitHub官方下载源。")
                os.environ['IS_CN'] = 'no'
            else: os.environ['IS_CN'] = 'yes'
        except Exception:
            os.environ['IS_CN'] = 'yes'; self.log.warning('检查服务器位置失败，将默认使用国内加速CDN。')

    def extract_app_id(self, user_input: str):
        for p in [r"store\.steampowered\.com/app/(\d+)", r"steamdb\.info/app/(\d+)"]:
            if m := re.search(p, user_input): return m.group(1)
        return user_input if user_input.isdigit() else None

    async def find_appid_by_name(self, game_name):
        try:
            r = await client.get(f'https://steamui.com/loadGames.php?search={game_name}'); r.raise_for_status()
            games = r.json().get('games', [])
            if not games: return None
            game = games[0]
            name, appid = game.get('schinese_name') or game.get('name', ''), game['appid']
            self.log.info(f"通过名称 '{game_name}' 找到游戏: {name} (AppID: {appid})"); return appid
        except Exception as e:
            self.log.error(f"通过游戏名搜索AppID时出错: {e}"); return None

    async def fetch_branch_info(self, url, headers):
        try:
            r = await client.get(url, headers=headers); r.raise_for_status(); return r.json()
        except httpx.HTTPStatusError as e:
            self.log.error(f'获取信息失败: {e.request.url} - Status {e.response.status_code}')
            if e.response.status_code == 404: self.log.error("404 Not Found: 请检查AppID是否正确，以及该清单是否存在于所选仓库中。")
            return None
        except Exception as e: self.log.error(f'获取信息失败: {self.stack_error(e)}'); return None

    async def get(self, sha: str, path: str, repo: str):
        urls = [f'https://cdn.jsdmirror.com/gh/{repo}@{sha}/{path}', f'https://raw.gitmirror.com/{repo}/{sha}/{path}'] if os.environ.get('IS_CN') == 'yes' else [f'https://raw.githubusercontent.com/{repo}/{sha}/{path}']
        for url in urls:
            try:
                self.log.info(f"尝试下载: {path} from {url.split('/')[2]}")
                r = await client.get(url)
                if r.status_code == 200: return r.content
                self.log.warning(f"下载失败 (状态码 {r.status_code}) from {url.split('/')[2]}，尝试下一个源...")
            except Exception as e: self.log.warning(f"下载时连接错误 from {url.split('/')[2]}: {e}，尝试下一个源...")
        raise Exception(f'所有下载源均失败: {path}')

    async def get_manifest(self, sha: str, path: str, steam_path: Path, repo: str, app_id: str, all_manifests: List[str]):
        content, depots = await self.get(sha, path, repo), []
        depot_cache, cfg_depot_cache, stplug = steam_path/'depotcache', steam_path/'config'/'depotcache', steam_path/'config'/'stplug-in'
        for p in [depot_cache, cfg_depot_cache, stplug]: p.mkdir(parents=True, exist_ok=True)
        
        if path.endswith('.manifest'):
            for p in [depot_cache, cfg_depot_cache]:
                async with aiofiles.open(p / path, 'wb') as f: await f.write(content)
            self.log.info(f'清单已保存: {path}')
        elif path.endswith('.lua'):
            async with aiofiles.open(stplug/path,'wb') as f: await f.write(content)
            self.log.info(f'Lua脚本已保存: {stplug/path}')
        elif "key.vdf" in path.lower():
            depots_cfg = vdf.loads(content.decode('utf-8'))
            depots = [(depot_id, info['DecryptionKey']) for depot_id, info in depots_cfg['depots'].items()]
            if self.isSteamTools and app_id:
                lua_path = stplug / f"{app_id}.lua"
                self.log.info(f'为SteamTools创建Lua脚本: {lua_path}')
                async with aiofiles.open(lua_path, "w", encoding="utf-8") as f:
                    await f.write(f'addappid({app_id}, 1, "None")\n')
                    for depot_id, key in depots: await f.write(f'addappid({depot_id}, 1, "{key}")\n')
                    for mf in all_manifests:
                        if m := re.search(r'(\d+)_(\w+)\.manifest', mf): await f.write(f'setManifestid({m.group(1)}, "{m.group(2)}")\n')
                self.log.info('Lua脚本创建成功。')
        return depots

    async def depotkey_merge(self, config_path: Path, depots_config: dict):
        if not config_path.exists(): self.log.error('Steam默认配置(config.vdf)不存在'); return False
        try:
            async with aiofiles.open(config_path, 'r', encoding='utf-8') as f: config = vdf.loads(await f.read())
            steam = (config.get('InstallConfigStore',{}).get('Software',{}).get('Valve') or 
                     config.get('InstallConfigStore',{}).get('Software',{}).get('valve'))
            if not steam: self.log.error('找不到Steam配置节'); return False
            steam.setdefault('depots', {}).update(depots_config.get('depots', {}))
            async with aiofiles.open(config_path, 'w', encoding='utf-8') as f: await f.write(vdf.dumps(config, pretty=True))
            self.log.info('密钥成功合并到 config.vdf。'); return True
        except Exception as e: self.log.error(f'合并密钥失败: {self.stack_error(e)}'); return False
    
    async def greenluma_add(self, depot_id_list: list):
        try:
            (app_list_path := self.steam_path / 'AppList').mkdir(parents=True, exist_ok=True)
            with open(app_list_path / f'{depot_id_list[0]}.txt', 'w') as f: f.write(str(depot_id_list[0]))
            self.log.info(f"已为GreenLuma添加AppID: {depot_id_list[0]}"); return True
        except Exception as e: self.log.error(f'为GreenLuma添加解锁文件时出错: {e}'); return False

    async def search_all_repos(self, app_id, repos):
        results = []
        for repo in repos:
            self.log.info(f"搜索仓库: {repo}")
            if r1 := await self.fetch_branch_info(f'https://api.github.com/repos/{repo}/branches/{app_id}', self.get_github_headers()):
                if 'commit' in r1 and (r2 := await self.fetch_branch_info(r1['commit']['commit']['tree']['url'], self.get_github_headers())):
                    if 'tree' in r2:
                        results.append({'repo':repo, 'sha':r1['commit']['sha'], 'tree':r2['tree'], 'update_date':r1["commit"]["commit"]["author"]["date"]})
                        self.log.info(f"在仓库 {repo} 中找到清单。")
        return results

    async def _process_zip_based_manifest(self, app_id: str, steam_path: Path, download_url: str, source_name: str):
        temp_dir = Path('./temp_cai_install')
        try:
            temp_dir.mkdir(exist_ok=True)
            self.log.info(f'[{source_name}] 正在下载清单文件: {download_url}')
            async with client.stream("GET", download_url) as r:
                if r.status_code != 200: self.log.error(f'[{source_name}] 下载失败: {r.status_code}'); return False
                async with aiofiles.open(temp_dir/f'{app_id}.zip', 'wb') as f:
                    async for chunk in r.aiter_bytes(): await f.write(chunk)
            
            self.log.info(f'[{source_name}] 正在解压文件...')
            with zipfile.ZipFile(temp_dir/f'{app_id}.zip', 'r') as zf: zf.extractall(temp_dir/app_id)
            
            extract_path = temp_dir/app_id
            manifests, luas, sts = list(extract_path.glob('*.manifest')), list(extract_path.glob('*.lua')), list(extract_path.glob('*.st'))

            for st_file in sts:
                try:
                    lua_path = st_file.with_suffix('.lua')
                    async with aiofiles.open(lua_path, 'w', encoding='utf-8') as f: await f.write(self.st_converter.convert_file(str(st_file)))
                    luas.append(lua_path); self.log.info(f'已转换ST文件: {st_file.name}')
                except Exception: self.log.error(f'转换ST文件失败: {st_file.name}')

            if not manifests: self.log.warning(f"[{source_name}] 未找到 .manifest 文件。"); return False
            
            if luas:
                self.log.info(f'[{source_name}] 检测到SteamTools入库文件。')
                (st_depot := steam_path/'config'/'depotcache').mkdir(parents=True, exist_ok=True)
                (st_plug := steam_path/'config'/'stplug-in').mkdir(parents=True, exist_ok=True)
                for f in manifests: shutil.copy2(f, st_depot)
                for f in luas: shutil.copy2(f, st_plug)
                self.log.info(f"已复制 {len(manifests)} 个清单和 {len(luas)} 个脚本到SteamTools目录。")
            else:
                self.log.info(f'[{source_name}] 检测到GreenLuma/标准入库文件。')
                (gl_depot := steam_path / 'depotcache').mkdir(parents=True, exist_ok=True)
                for f in manifests: shutil.copy2(f, gl_depot)
                self.log.info(f"已复制 {len(manifests)} 个清单到Steam目录。")
            return True
        except Exception as e:
            self.log.error(f'[{source_name}] 处理清单时出错: {self.stack_error(e)}'); return False
        finally:
            if temp_dir.exists(): shutil.rmtree(temp_dir, ignore_errors=True)

    async def process_printedwaste_manifest(self, app_id: str, steam_path: Path):
        return await self._process_zip_based_manifest(app_id, steam_path, f'https://api.printedwaste.com/gfk/download/{app_id}', "SWA V2")
        
    async def process_cysaw_manifest(self, app_id: str, steam_path: Path):
        return await self._process_zip_based_manifest(app_id, steam_path, f'https://cysaw.top/uploads/{app_id}.zip', "Cysaw")

    async def process_furcate_manifest(self, app_id: str, steam_path: Path):
        return await self._process_zip_based_manifest(app_id, steam_path, f'https://furcate.eu/files/{app_id}.zip', "Furcate")

    async def process_assiw_manifest(self, app_id: str, steam_path: Path):
        return await self._process_zip_based_manifest(app_id, steam_path, f'https://assiw.cngames.site/qindan/{app_id}.zip', "CNGS")

    # <-- 新增的处理函数
    async def process_steamdatabase_manifest(self, app_id: str, steam_path: Path):
        return await self._process_zip_based_manifest(app_id, steam_path, f'https://steamdatabase.s3.eu-north-1.amazonaws.com/{app_id}.zip', "SteamDatabase")

    async def cleanup_temp_files(self):
        if (temp_path := Path('./temp_cai_install')).exists():
            shutil.rmtree(temp_path, ignore_errors=True); self.log.info('临时文件清理完成。')
            
def show_info_dialog():
    settings_path = Path('./settings.json')
    if settings_path.exists():
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                if not json.load(f).get('show_notification', True): return
        except Exception: pass
    
    webbrowser.open('https://docs.qq.com/doc/DTUp3Z2Fkd2pVRGtX?dver=')
    root = tk.Tk(); root.title("Cai Install 信息提示"); root.geometry("400x200"); root.resizable(False, False); root.attributes('-topmost', True)
    tk.Label(root, text="请加入官方群聊以获取最新公告及更新:\n993782526\n关注官方b站:菜Games-pvzcxw", font=("Arial", 12)).pack(pady=20)
    dont_show = tk.BooleanVar(value=False); tk.Checkbutton(root, text="不再显示此消息", variable=dont_show).pack(pady=5)
    
    def on_confirm():
        if dont_show.get():
            try:
                with open(settings_path, 'w', encoding='utf-8') as f: json.dump({'show_notification': False}, f)
            except Exception as e: print(f"保存设置失败: {e}")
        root.destroy()

    tk.Button(root, text="确认", command=on_confirm).pack(pady=10); root.mainloop()

if __name__ == '__main__':
    colorama_init()
    show_info_dialog()
    app = CaiInstallGUI()
    app.mainloop()