# --- START OF CORRECTED FILE cixGUI1.35b1-fix1.py ---

import sys
import os
import logging
import asyncio
import webbrowser
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog
from pathlib import Path
import json
import threading
from typing import List # <--- Added missing import

# Use ttkbootstrap for modern UI
try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
except ImportError:
    messagebox.showerror("依赖缺失", "错误: ttkbootstrap 库未安装。\n请在命令行中使用 'pip install ttkbootstrap' 命令安装后重试。")
    sys.exit(1)

# Import the backend
try:
    from backend_gui import GuiBackend
except ImportError:
    messagebox.showerror("文件缺失", "错误: backend_gui.py 文件缺失。\n请确保主程序和后端文件在同一个目录下。")
    sys.exit(1)

# --- GUI Application Class ---
class CaiInstallGUI(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly", title="Cai Install XP v1.40-buildnew250707 - GUI Edition")
        self.geometry("850x700")
        self.minsize(700, 550)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- REORDERED INITIALIZATION ---
        
        self.processing_lock = threading.Lock()
        
        # 1. Create all widgets first.
        self.create_widgets()
        
        # 2. Set up the logger, which depends on the text widget created above.
        self.log = self.setup_logging()
        
        # 3. Initialize the backend, passing the now-ready logger.
        self.backend = GuiBackend(self.log)

        # 4. Create the menu and start the final app setup.
        self.create_menu()
        self.after(100, self.initialize_app)

    def setup_logging(self):
        logger = logging.getLogger('CaiInstallGUI')
        logger.setLevel(logging.INFO)
        if logger.hasHandlers(): logger.handlers.clear()

        class GuiHandler(logging.Handler):
            def __init__(self, text_widget): # Simplified to only need the widget
                super().__init__()
                self.text_widget = text_widget
                self.setFormatter(logging.Formatter('%(message)s'))

            def emit(self, record):
                msg = self.format(record)
                level = record.levelname
                is_banner = getattr(record, 'is_banner', False)
                
                # Use after() to make this thread-safe
                self.text_widget.after(0, self.update_log_text, msg, level, is_banner)
            
            # This method now belongs to the GuiHandler
            def update_log_text(self, msg, level, is_banner):
                try:
                    self.text_widget.configure(state='normal')
                    tag = 'BANNER' if is_banner else level.upper()
                    self.text_widget.insert(tk.END, msg + '\n', tag)
                    self.text_widget.configure(state='disabled')
                    self.text_widget.see(tk.END)
                except tk.TclError:
                    # This can happen if the window is closed while a log is pending
                    pass

        # Pass the created text widget to the handler
        gui_handler = GuiHandler(self.log_text_widget)
        logger.addHandler(gui_handler)
        return logger

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
        help_menu.add_command(label="官方公告", command=lambda: webbrowser.open('https://docs.qq.com/doc/DTUp3Z2Fkd2pVRGtX?dver='))
        help_menu.add_command(label="GitHub仓库", command=lambda: webbrowser.open('https://github.com/pvzcxw/cai-install_stloader'))
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
            ("SteamDatabase", "steamdatabase"),
            ("GitHub - Auiowu/ManifestAutoUpdate", "Auiowu/ManifestAutoUpdate"),
            ("GitHub - SteamAutoCracks/ManifestHub", "SteamAutoCracks/ManifestHub"),
        ]
        self.repo_combobox = ttk.Combobox(tab1, state="readonly", values=[name for name, _ in self.repo_options])
        self.repo_combobox.pack(side=LEFT, fill=X, expand=True)
        self.repo_combobox.current(0)
        
        tab2 = ttk.Frame(notebook, padding=10)
        notebook.add(tab2, text=" 搜索所有GitHub库 ")
        ttk.Label(tab2, text="此模式将通过游戏名/AppID搜索所有已知的GitHub清单库。").pack(fill=X)

        self.process_button = ttk.Button(main_frame, text="开始处理", command=self.start_processing, style='success.TButton')
        self.process_button.pack(fill=X, pady=10)
        
        log_frame = ttk.Labelframe(main_frame, text="日志输出", padding=10)
        log_frame.pack(fill=BOTH, expand=True)
        
        # Create the ScrolledText widget here
        self.log_text_widget = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state='disabled', font=("Courier New", 9))
        self.log_text_widget.pack(fill=BOTH, expand=True)
        self.log_text_widget.configure(bg=self.style.colors.get('bg'), fg=self.style.colors.get('fg'))
        
        self.log_text_widget.tag_config('INFO', foreground=self.style.colors.info)
        self.log_text_widget.tag_config('WARNING', foreground=self.style.colors.warning)
        self.log_text_widget.tag_config('ERROR', foreground=self.style.colors.danger)
        self.log_text_widget.tag_config('CRITICAL', foreground=self.style.colors.danger, font=("Courier New", 9, 'bold'))
        self.log_text_widget.tag_config('BANNER', foreground=self.style.colors.primary)
        
        self.status_bar = ttk.Label(self, text=" 正在初始化...", relief=SUNKEN, anchor=W, padding=5)
        self.status_bar.pack(side=BOTTOM, fill=X)
    
    def initialize_app(self):
        """Perform initial setup after the GUI is created."""
        self.print_banner()
        self.log.info("Cai Install XP GUI版 - 正在初始化...")
        self.backend.load_config()
        self.update_unlocker_status()
        self.log.info(f"软件作者: pvzcxw | GUI重制: pvzcxw")
        self.log.warning("本项目采用GNU GPLv3开源许可证，完全免费，请勿用于商业用途。")
        self.log.warning("官方Q群: 993782526 | B站: 菜Games-pvzcxw")
        
    def update_unlocker_status(self):
        """Detects Steam and unlockers and updates the UI accordingly."""
        steam_path = self.backend.detect_steam_path()
        if not steam_path.exists():
            self.status_bar.config(text="Steam路径未找到！请在设置中指定。")
            messagebox.showerror("Steam未找到", "无法自动检测到Steam路径。\n请在“设置”->“编辑配置”中手动指定路径。")
            return
            
        status = self.backend.detect_unlocker()
        
        if status == "conflict":
            messagebox.showerror("环境冲突", "错误: 同时检测到 SteamTools 和 GreenLuma！\n请手动卸载其中一个以避免冲突，然后重启本程序。")
            self.process_button.config(state=DISABLED)
            self.status_bar.config(text="环境冲突！请解决后重启。")
        elif status == "none":
            self.handle_manual_selection()
        
        if self.backend.unlocker_type:
             self.status_bar.config(text=f"Steam路径: {steam_path} | 解锁方式: {self.backend.unlocker_type.title()}")

    def handle_manual_selection(self):
        """Create a dialog to let the user choose the unlocker type."""
        dialog = ManualSelectionDialog(self, title="选择解锁工具")
        self.wait_window(dialog) # Wait for the dialog to close
        
        choice = dialog.result
        if choice in ["steamtools", "greenluma"]:
            self.backend.unlocker_type = choice
            self.log.info(f"已手动选择解锁方式: {choice.title()}")
            self.update_unlocker_status() # Update status bar
        else:
            self.log.error("未选择解锁工具，部分功能可能无法正常工作。")
            self.status_bar.config(text="未选择解锁工具！")
            self.process_button.config(state=DISABLED)

    def start_processing(self):
        if not self.backend.unlocker_type:
            messagebox.showerror("错误", "未确定解锁工具！\n请先通过设置或重启程序解决解锁工具检测问题。")
            return
        
        if not self.processing_lock.acquire(blocking=False):
            self.log.warning("已经在处理中，请等待当前任务完成。")
            return

        notebook_tab = self.notebook.index('current')
        
        def thread_target():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.run_async_tasks(notebook_tab))
            finally:
                loop.close()
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
            self.log.error(self.backend.stack_error(e))
        finally:
            await self.backend.cleanup_temp_files()

    async def resolve_appids(self, inputs: List[str]) -> List[str]:
        resolved_ids = []
        for item in inputs:
            if app_id := self.backend.extract_app_id(item):
                resolved_ids.append(app_id); continue
            self.log.info(f"'{item}' 不是有效的ID或链接，尝试作为游戏名称搜索...")
            if found_id := await self.backend.find_appid_by_name(item):
                resolved_ids.append(found_id)
            else:
                self.log.error(f"无法为 '{item}' 找到匹配的游戏。")
        return list(dict.fromkeys(resolved_ids)) # Remove duplicates

    async def process_from_specific_repo(self, inputs, repo_val):
        app_ids = await self.resolve_appids(inputs)
        if not app_ids:
            self.log.error("未能解析出任何有效的AppID。"); return
        
        self.log.info(f"成功解析的 App IDs: {', '.join(app_ids)}")
        
        is_github = repo_val not in ["swa", "cysaw", "furcate", "cngs", "steamdatabase"]
        if is_github:
            await self.backend.checkcn()
            if not await self.backend.check_github_api_rate_limit(self.backend.get_github_headers()):
                return
        
        for app_id in app_ids:
            self.log.info(f"--- 正在处理 App ID: {app_id} ---")
            success = False
            if repo_val == "swa": success = await self.backend.process_printedwaste_manifest(app_id)
            elif repo_val == "cysaw": success = await self.backend.process_cysaw_manifest(app_id)
            elif repo_val == "furcate": success = await self.backend.process_furcate_manifest(app_id)
            elif repo_val == "cngs": success = await self.backend.process_assiw_manifest(app_id)
            elif repo_val == "steamdatabase": success = await self.backend.process_steamdatabase_manifest(app_id)
            else: success = await self.process_github_repo(app_id, repo_val)
            
            if success: self.log.info(f"App ID: {app_id} 处理成功。")
            else: self.log.error(f"App ID: {app_id} 处理失败。")

    async def process_by_searching_all(self, inputs):
        app_ids = await self.resolve_appids(inputs)
        if not app_ids: self.log.error("未能解析出任何有效的AppID。"); return

        github_repos = [val for _, val in self.repo_options if val not in ["swa", "cysaw", "furcate", "cngs", "steamdatabase"]]
        await self.backend.checkcn()
        if not await self.backend.check_github_api_rate_limit(self.backend.get_github_headers()):
            return
        
        for app_id in app_ids:
            self.log.info(f"--- 正在为 App ID: {app_id} 搜索所有GitHub库 ---")
            repo_results = await self.backend.search_all_repos(app_id, github_repos)
            
            if not repo_results:
                self.log.error(f"在所有GitHub库中均未找到 {app_id} 的清单。"); continue

            repo_results.sort(key=lambda x: x['update_date'], reverse=True)
            selected = repo_results[0]
            self.log.info(f"找到 {len(repo_results)} 个结果，将使用最新的清单: {selected['repo']} (更新于 {selected['update_date']})")

            if await self.process_github_repo(app_id, selected['repo'], selected):
                self.log.info(f"App ID: {app_id} 处理成功。")
            else:
                self.log.error(f"App ID: {app_id} 处理失败。")

    async def process_github_repo(self, app_id: str, repo: str, existing_data: dict = None) -> bool:
        try:
            headers = self.backend.get_github_headers()
            if existing_data:
                sha, tree, date = existing_data['sha'], existing_data['tree'], existing_data['update_date']
            else:
                if not (r_json := await self.backend.fetch_branch_info(f'https://api.github.com/repos/{repo}/branches/{app_id}', headers)):
                    return False
                sha, date = r_json['commit']['sha'], r_json["commit"]["commit"]["author"]["date"]
                if not (r2_json := await self.backend.fetch_branch_info(r_json['commit']['commit']['tree']['url'], headers)):
                    return False
                tree = r2_json['tree']

            manifests = [item['path'] for item in tree if item['path'].endswith('.manifest')]
            tasks = [self.backend.get_manifest_from_github(sha, item['path'], repo, app_id, manifests) for item in tree]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            collected_depots = []
            for res in results:
                if isinstance(res, Exception): self.log.error(f"下载/处理文件时出错: {res}"); return False
                if res: collected_depots.extend(res)

            if not manifests and not collected_depots:
                 self.log.error(f'仓库中没有找到有效的清单文件或密钥文件: {app_id}'); return False

            if self.backend.is_steamtools():
                self.log.info('检测到SteamTools，已自动生成并放置解锁文件。')
            elif collected_depots:
                await self.backend.greenluma_add([app_id] + [depot_id for depot_id, _ in collected_depots])
                await self.backend.depotkey_merge({'depots': {depot_id: {'DecryptionKey': key} for depot_id, key in collected_depots}})

            self.log.info(f'清单最后更新时间: {date}')
            return True
        except Exception as e:
            self.log.error(f"处理GitHub仓库时出错: {self.backend.stack_error(e)}"); return False

    def on_closing(self):
        if self.processing_lock.locked():
            if messagebox.askyesno("退出", "正在处理任务，确定要强制退出吗？"):
                os._exit(0) # Force exit
        else:
            self.destroy()

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
        # Use a special attribute to tell the logger this is a banner
        for line in banner: self.log.info(line, extra={'is_banner': True})

    def show_about_dialog(self):
        messagebox.showinfo("关于", "Cai Install XP v1.40buildnew250707 - GUI Edition\n\n原作者: pvzcxw\nGUI重制: pvzcxw\n\n一个用于Steam游戏清单获取和导入的工具")
    
    def show_settings_dialog(self):
        dialog = ttk.Toplevel(self)
        dialog.title("编辑配置"); dialog.geometry("500x200"); dialog.transient(self); dialog.grab_set()
        frame = ttk.Frame(dialog, padding=15); frame.pack(fill=BOTH, expand=True)
        
        ttk.Label(frame, text="GitHub Personal Token:").grid(row=0, column=0, sticky=W, pady=5)
        token_entry = ttk.Entry(frame, width=50); token_entry.grid(row=0, column=1, sticky=EW, pady=5)
        token_entry.insert(0, self.backend.app_config.get("Github_Personal_Token", ""))

        ttk.Label(frame, text="自定义Steam路径:").grid(row=1, column=0, sticky=W, pady=5)
        path_entry = ttk.Entry(frame, width=50); path_entry.grid(row=1, column=1, sticky=EW, pady=5)
        path_entry.insert(0, self.backend.app_config.get("Custom_Steam_Path", ""))
        
        button_frame = ttk.Frame(frame); button_frame.grid(row=2, column=0, columnspan=2, pady=15)

        def save_and_close():
            self.backend.app_config["Github_Personal_Token"] = token_entry.get()
            self.backend.app_config["Custom_Steam_Path"] = path_entry.get()
            self.backend.save_config()
            self.log.info("配置已保存。Steam路径等设置将在下次启动或手动刷新时生效。")
            self.update_unlocker_status() # Re-detect after changing path
            dialog.destroy()

        ttk.Button(button_frame, text="保存", command=save_and_close, style='success.TButton').pack(side=LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=LEFT, padx=10)
        frame.columnconfigure(1, weight=1)

class ManualSelectionDialog(tk.Toplevel):
    """A dialog for manually selecting the unlocker tool."""
    def __init__(self, parent, title=None):
        super().__init__(parent)
        self.transient(parent)
        if title: self.title(title)
        self.parent = parent
        self.result = None
        self.grab_set()

        body = ttk.Frame(self, padding=20)
        self.initial_focus = self.body(body)
        body.pack()

        self.buttonbox()
        if not self.initial_focus:
            self.initial_focus = self

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.geometry(f"+{parent.winfo_rootx()+50}+{parent.winfo_rooty()+50}")
        self.initial_focus.focus_set()
        self.wait_window(self)

    def body(self, master):
        ttk.Label(master, text="未能自动检测到解锁工具。\n请根据您的实际情况选择：", justify=LEFT).pack(pady=10)
        
        st_button = ttk.Button(master, text="我是 SteamTools 用户", command=lambda: self.ok("steamtools"))
        st_button.pack(fill=X, pady=5)
        
        gl_button = ttk.Button(master, text="我是 GreenLuma 用户", command=lambda: self.ok("greenluma"))
        gl_button.pack(fill=X, pady=5)
        
        return st_button

    def buttonbox(self):
        pass # Buttons are in the body for this specific dialog

    def ok(self, result):
        self.result = result
        self.withdraw()
        self.update_idletasks()
        self.parent.focus_set()
        self.destroy()

    def cancel(self, event=None):
        self.parent.focus_set()
        self.destroy()

# REPLACE the existing show_startup_info_dialog function with this one.
def show_startup_info_dialog(parent):
    """Creates a modal Toplevel dialog on top of the parent window."""
    settings_path = Path('./settings.json')
    # Default to showing the dialog unless the settings file says not to
    show_dialog = True
    if settings_path.exists():
        try:
            # Check the setting in the json file
            if not json.loads(settings_path.read_text(encoding='utf-8')).get('show_notification', True):
                show_dialog = False
        except Exception:
            pass  # If file is corrupt, just show the dialog

    if not show_dialog:
        return

    # Create a Toplevel window. It's a child of the 'parent' (the main app).
    # All variable references are to 'dialog'.
    dialog = tk.Toplevel(parent)
    dialog.title("Cai Install 信息提示")
    dialog.geometry("400x200")
    dialog.resizable(False, False)
    
    # These two lines make the dialog "modal" - the user must close it first.
    dialog.transient(parent)
    dialog.grab_set()

    # Center the dialog over the main window
    parent.update_idletasks() # Ensure parent window dimensions are up to date
    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_w = parent.winfo_width()
    parent_h = parent.winfo_height()
    dialog_w, dialog_h = 400, 200
    x = parent_x + (parent_w - dialog_w) // 2
    y = parent_y + (parent_h - dialog_h) // 2
    dialog.geometry(f'{dialog_w}x{dialog_h}+{x}+{y}')

    label = ttk.Label(dialog, text="请加入官方群聊以获取最新公告及更新:\n993782526\n关注官方b站:菜Games-pvzcxw", font=("Arial", 12), justify=CENTER)
    label.pack(pady=20)
    
    dont_show = tk.BooleanVar(value=False)
    checkbox = ttk.Checkbutton(dialog, text="不再显示此消息", variable=dont_show, bootstyle="round-toggle")
    checkbox.pack(pady=5)
    
    def on_confirm():
        if dont_show.get():
            try:
                with open(settings_path, 'w', encoding='utf-8') as f:
                    json.dump({'show_notification': False}, f, indent=2)
            except Exception as e:
                print(f"保存设置失败: {e}")
        webbrowser.open('https://docs.qq.com/doc/DTUp3Z2Fkd2pVRGtX?dver=')
        dialog.destroy()

    button = ttk.Button(dialog, text="确认", command=on_confirm, bootstyle="success")
    button.pack(pady=10)
    
    # This crucial line pauses the main script until the dialog is closed.
    parent.wait_window(dialog)


if __name__ == '__main__':
    # Set DPI awareness for a sharper GUI on Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

    # 1. Create the main application window instance.
    app = CaiInstallGUI()

    # 2. Show the startup dialog.
    show_startup_info_dialog(app)
    
    # 3. Start the main event loop.
    app.mainloop()
