# --- START OF FILE frontend_gui.py ---

import sys
import os
import re
import asyncio
import logging
import threading
import webbrowser
import json
import tkinter as tk
from tkinter import messagebox, scrolledtext
from pathlib import Path

# Import UI library and the backend core
try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
except ImportError:
    print("Error: ttkbootstrap is not installed. Please run 'pip install ttkbootstrap'.")
    sys.exit(1)

from backend import CaiCore

# --- GUI Application Class ---
class CaiInstallGUI(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly", title="Cai Install XP v1.35b1 - GUI Edition")
        self.geometry("850x700")
        self.minsize(700, 550)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # The backend core is now an attribute of the GUI
        self.core = CaiCore()
        self.processing_lock = threading.Lock()
        
        self.create_widgets()
        self.log = self.setup_logging()
        self.create_menu()
        
        # Start the initialization process in a separate thread
        threading.Thread(target=self.initialize_core_in_thread, daemon=True).start()

    def setup_logging(self):
        # This remains the same, as it's purely for the GUI
        logger = logging.getLogger('CaiInstallGUI')
        logger.setLevel(logging.INFO)
        if logger.hasHandlers(): logger.handlers.clear()

        class GuiHandler(logging.Handler):
            def __init__(self, gui_app_instance):
                super().__init__()
                self.gui_app = gui_app_instance
            def emit(self, record):
                msg = f"[{record.levelname}] {record.message}"
                self.gui_app.after(0, self.gui_app.update_log, msg, record.levelname)

        logger.addHandler(GuiHandler(self))
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
        help_menu = ttk.Menu(menu_bar, tearoff=False)
        menu_bar.add_cascade(label="更多", menu=help_menu)
        help_menu.add_command(label="官方公告", command=lambda: webbrowser.open('https://docs.qq.com/doc/DTUp3Z2Fkd2pVRGtX?dver='))
        help_menu.add_command(label="GitHub仓库", command=lambda: webbrowser.open('https://github.com/pvzcxw/cai-install_stloader'))
        help_menu.add_command(label="关于", command=self.show_about_dialog)

    def create_widgets(self):
        # Widget creation is a UI concern, so it stays here.
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=BOTH, expand=True)
        
        input_frame = ttk.Labelframe(main_frame, text="输入区", padding=10)
        input_frame.pack(fill=X, pady=(0, 10))
        ttk.Label(input_frame, text="游戏AppID、链接或名称 (多个用英文逗号隔开):").pack(side=LEFT, padx=(0, 10))
        self.appid_entry = ttk.Entry(input_frame, font=("", 10))
        self.appid_entry.pack(side=LEFT, fill=X, expand=True)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=X, pady=5)
        
        tab1 = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab1, text=" 从指定库安装 ")
        ttk.Label(tab1, text="选择清单库:").pack(side=LEFT, padx=(0, 10))
        self.repo_options = [
            ("SWA", "SWA"), ("Cysaw", "Cysaw"), ("Furcate", "Furcate"), ("CNGS", "CNGS"),
            ("SteamDB", "SteamDB"),
            ("GitHub - Auiowu/ManifestAutoUpdate", "Auiowu/ManifestAutoUpdate"),
            ("GitHub - SteamAutoCracks/ManifestHub", "SteamAutoCracks/ManifestHub"),
        ]
        self.repo_combobox = ttk.Combobox(tab1, state="readonly", values=[name for name, val in self.repo_options])
        self.repo_combobox.pack(side=LEFT, fill=X, expand=True)
        self.repo_combobox.current(0)
        
        tab2 = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab2, text=" 搜索所有GitHub库 ")
        ttk.Label(tab2, text="此模式将通过游戏名/AppID搜索所有已知的GitHub清单库。").pack(fill=X)

        self.process_button = ttk.Button(main_frame, text="初始化中...", command=self.start_processing, style='success.TButton', state=DISABLED)
        self.process_button.pack(fill=X, pady=10)
        
        log_frame = ttk.Labelframe(main_frame, text="日志输出", padding=10)
        log_frame.pack(fill=BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state='disabled', font=("Courier New", 9), bg=self.style.colors.get('bg'), fg=self.style.colors.get('fg'))
        self.log_text.pack(fill=BOTH, expand=True)
        
        self.log_text.tag_config('INFO', foreground=self.style.colors.info)
        self.log_text.tag_config('WARNING', foreground=self.style.colors.warning)
        self.log_text.tag_config('ERROR', foreground=self.style.colors.danger)
        self.log_text.tag_config('BANNER', foreground=self.style.colors.primary)
        
        self.status_bar = ttk.Label(self, text=" 正在初始化...", relief=SUNKEN, anchor=W, padding=5)
        self.status_bar.pack(side=BOTTOM, fill=X)

    def initialize_core_in_thread(self):
        """Runs the async initialization of the backend and updates the UI."""
        self.print_banner()
        self.log.info("Cai Install XP GUI - 正在初始化...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success, message = loop.run_until_complete(self.core.initialize())
        
        # Use `self.after` to safely update GUI from this thread
        def update_ui():
            if success:
                self.log.info(message)
                self.log.info(f"SteamTools模式: {'已启用' if self.core.isSteamTools else '未检测到'}")
                self.log.info(f"GreenLuma模式: {'已启用' if self.core.isGreenLuma else '未检测到'}")
                status_text = f"Steam: {self.core.steam_path.name} | ST: {'Yes' if self.core.isSteamTools else 'No'}"
                self.status_bar.config(text=status_text)
                self.process_button.config(text="开始处理", state=NORMAL)
            else:
                self.log.error(message)
                self.status_bar.config(text="初始化失败，请检查配置！")
            self.log.info("="*80)
            self.log.info("初始化完成，可以开始任务。")

        self.after(0, update_ui)

    def start_processing(self):
        if not self.processing_lock.acquire(blocking=False):
            self.log.warning("已经在处理中，请等待当前任务完成。")
            return

        def thread_target():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.run_async_tasks())
            finally:
                self.processing_lock.release()
                self.after(0, self.processing_finished)
        
        self.process_button.config(state=DISABLED, text="正在处理...")
        self.status_bar.config(text="正在处理...")
        threading.Thread(target=thread_target, daemon=True).start()

    def processing_finished(self):
        self.process_button.config(state=NORMAL, text="开始处理")
        self.status_bar.config(text="处理完成，准备就绪。")
        self.log.info("="*80)
        self.log.info("处理完成！您可以开始新的任务。")

    async def run_async_tasks(self):
        user_input = self.appid_entry.get().strip()
        if not user_input:
            self.log.error("输入不能为空！")
            return

        app_id_inputs = [item.strip() for item in user_input.split(',')]
        
        tab_index = self.notebook.index('current')
        
        try:
            # Resolve all inputs to AppIDs first
            app_ids = await self.resolve_appids(app_id_inputs)
            if not app_ids:
                self.log.error("未能解析出任何有效的AppID。")
                return
            self.log.info(f"成功解析的 App IDs: {', '.join(app_ids)}")

            # Now, process them based on the selected tab
            if tab_index == 0:
                _, repo_val = self.repo_options[self.repo_combobox.current()]
                await self.process_from_specific_source(app_ids, repo_val)
            elif tab_index == 1:
                await self.process_by_searching_all(app_ids)

        except Exception as e:
            self.log.error(f"处理过程中发生未知错误: {e}\n{traceback.format_exc()}")
        finally:
            await self.core.close() # Use the core's cleanup method

    async def process_from_specific_source(self, app_ids, source_val):
        self.log.info(f"选择模式: 从 '{source_val}' 安装")
        for app_id in app_ids:
            self.log.info(f"--- 正在处理 App ID: {app_id} ---")
            if "GitHub" in self.repo_combobox.get():
                success, message = await self.core.install_from_github_repo(app_id, source_val)
            else:
                success, message = await self.core.install_from_source(app_id, source_val)
            
            if success: self.log.info(message)
            else: self.log.error(message)
    
    async def process_by_searching_all(self, app_ids):
        self.log.info("选择模式: 搜索所有GitHub库")
        github_repos = [val for _, val in self.repo_options if "GitHub" in _]
        for app_id in app_ids:
            # In a real GUI, you might want to show a selection dialog here.
            # For simplicity, we'll just pick the first one found.
            self.log.info(f"--- 正在为 App ID: {app_id} 搜索所有GitHub库 ---")
            found = False
            for repo in github_repos:
                self.log.info(f"正在尝试仓库: {repo}...")
                success, message = await self.core.install_from_github_repo(app_id, repo)
                if success:
                    self.log.info(message)
                    found = True
                    break # Stop after the first success
            if not found:
                self.log.error(f"在所有已知的GitHub库中均未找到 {app_id} 的清单。")

    async def resolve_appids(self, inputs):
        """Uses backend to resolve names/links to AppIDs."""
        resolved = []
        for item in inputs:
            if app_id := self.extract_app_id(item):
                resolved.append(app_id)
                continue
            
            self.log.info(f"'{item}' 不是ID/链接，尝试作为游戏名搜索...")
            games = await self.core.search_games_by_name(item)
            if not games:
                self.log.warning(f"找不到名为 '{item}' 的游戏。")
                continue
            
            # For a GUI, we should ideally show a selection box.
            # For simplicity, we'll auto-pick the first result.
            game = games[0]
            name = game.get('schinese_name') or game.get('name', '')
            self.log.info(f"自动选择: {name} (AppID: {game['appid']})")
            resolved.append(str(game['appid']))
            
        return list(dict.fromkeys(resolved)) # Return unique IDs

    def extract_app_id(self, user_input: str):
        """Simple regex kept in UI to quickly identify links/IDs."""
        match = re.search(r"/app/(\d+)", user_input)
        return match.group(1) if match else user_input if user_input.isdigit() else None
    
    def on_closing(self):
        if self.processing_lock.locked():
            if messagebox.askyesno("退出", "正在处理任务，确定要强制退出吗？"):
                os._exit(0) # Force exit
        else:
            self.destroy()

    def show_settings_dialog(self):
        dialog = ttk.Toplevel(self)
        dialog.title("编辑配置"); dialog.transient(self); dialog.grab_set()
        frame = ttk.Frame(dialog, padding=15); frame.pack(fill=BOTH, expand=True)
        
        ttk.Label(frame, text="GitHub Personal Token:").grid(row=0, column=0, sticky=W, pady=5)
        token_entry = ttk.Entry(frame, width=50)
        token_entry.grid(row=0, column=1, sticky=EW, pady=5)
        token_entry.insert(0, self.core.config.get("Github_Personal_Token", ""))

        ttk.Label(frame, text="自定义Steam路径:").grid(row=1, column=0, sticky=W, pady=5)
        path_entry = ttk.Entry(frame, width=50)
        path_entry.grid(row=1, column=1, sticky=EW, pady=5)
        path_entry.insert(0, self.core.config.get("Custom_Steam_Path", ""))
        
        button_frame = ttk.Frame(frame); button_frame.grid(row=2, columnspan=2, pady=15)
        
        def save_and_close():
            # Update the config in the core object
            self.core.config["Github_Personal_Token"] = token_entry.get().strip()
            self.core.config["Custom_Steam_Path"] = path_entry.get().strip()
            
            # Tell the core to save the file
            asyncio.run(self.core.save_config())
            self.log.info("配置已保存。部分设置需要重启程序才能完全生效。")
            dialog.destroy()
            
            # Re-run initialization to detect new path etc.
            threading.Thread(target=self.initialize_core_in_thread, daemon=True).start()

        ttk.Button(button_frame, text="保存", command=save_and_close, style='success.TButton').pack(side=LEFT)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=LEFT, padx=10)

    def print_banner(self):
        # UI-specific function
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
        messagebox.showinfo("关于", "Cai Install XP v1.35b1 - GUI Edition\n\n原作者: pvzcxw\n本程序为开源免费工具，仅供学习交流。")

def show_initial_info_dialog():
    # This is a standalone function before the main app loop, so it's fine here.
    settings_path = Path('./settings.json')
    if settings_path.exists():
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                if not json.load(f).get('show_notification', True): return
        except Exception: pass
    
    webbrowser.open('https://docs.qq.com/doc/DTUp3Z2Fkd2pVRGtX?dver=')
    root = tk.Tk(); root.title("信息提示"); root.geometry("400x200"); root.attributes('-topmost', True)
    tk.Label(root, text="请加入官方群聊以获取最新公告及更新:\n993782526", font=("Arial", 12)).pack(pady=20)
    dont_show = tk.BooleanVar(); tk.Checkbutton(root, text="不再显示此消息", variable=dont_show).pack(pady=5)
    
    def on_confirm():
        if dont_show.get():
            with open(settings_path, 'w') as f: json.dump({'show_notification': False}, f)
        root.destroy()
    tk.Button(root, text="确认", command=on_confirm).pack(pady=10); root.mainloop()

if __name__ == '__main__':
    show_initial_info_dialog()
    app = CaiInstallGUI()
    app.mainloop()
