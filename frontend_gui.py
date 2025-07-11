# --- START OF CORRECTED frontend_gui.py ---

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
from typing import List
import httpx
import subprocess

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

# --- Simple Notepad Dialog ---
class SimpleNotepad(tk.Toplevel):
    def __init__(self, parent, filename, content, file_path):
        super().__init__(parent)
        self.transient(parent)
        self.title(f"编辑文件 - {filename}")
        self.file_path = Path(file_path)
        self.filename = filename
        self.geometry("800x600")
        self.grab_set()
        
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=BOTH, expand=True)

        ttk.Label(main_frame, text=f"文件: {self.filename}", font=("", 11, 'bold')).pack(pady=(0, 10), anchor=W)
        self.text_widget = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.text_widget.pack(fill=BOTH, expand=True)
        self.text_widget.insert(tk.END, content)
        
        button_frame = ttk.Frame(main_frame, padding=(0, 15, 0, 0))
        button_frame.pack(fill=X)
        button_frame.columnconfigure(0, weight=1)
        save_button = ttk.Button(button_frame, text="💾 保存", command=self.save_file, style='success.TButton')
        save_button.grid(row=0, column=1, padx=(10, 0))
        close_button = ttk.Button(button_frame, text="❌ 关闭", command=self.destroy, style='danger.TButton')
        close_button.grid(row=0, column=2, padx=10)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window(self)

    def save_file(self):
        try:
            content = self.text_widget.get("1.0", tk.END)
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("成功", f"文件 {self.filename} 已保存。", parent=self)
        except Exception as e:
            messagebox.showerror("失败", f"保存文件失败: {e}", parent=self)

# --- Game Selection Dialog ---
class GameSelectionDialog(tk.Toplevel):
    def __init__(self, parent, games: List[dict], title="选择游戏"):
        super().__init__(parent)
        self.transient(parent); self.title(title); self.parent = parent
        self.games = games; self.result = None
        self.geometry("600x400"); self.grab_set()
        body = ttk.Frame(self, padding=15)
        self.initial_focus = self.create_body(body)
        body.pack(fill=BOTH, expand=True); self.create_buttons()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.initial_focus.focus_set(); self.wait_window(self)

    def create_body(self, master):
        ttk.Label(master, text=f"找到 {len(self.games)} 个游戏，请选择一个：", font=("", 11, 'bold')).pack(pady=(0, 10), anchor=W)
        list_frame = ttk.Frame(master); list_frame.pack(fill=BOTH, expand=True)
        self.listbox = tk.Listbox(list_frame, font=("", 10), height=10)
        self.listbox.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient=VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=RIGHT, fill=Y); self.listbox.config(yscrollcommand=scrollbar.set)
        self.listbox.configure(bg=self.master.style.colors.get('bg'), fg=self.master.style.colors.get('fg'),
                               selectbackground=self.master.style.colors.primary, selectforeground='white',
                               borderwidth=0, highlightthickness=0)
        for game in self.games:
            name = game.get("schinese_name") or game.get("name", "N/A"); appid = game['appid']
            self.listbox.insert(tk.END, f" {name} (AppID: {appid})")
        self.listbox.bind("<Double-Button-1>", self.ok); return self.listbox

    def create_buttons(self):
        button_frame = ttk.Frame(self, padding=(15, 0, 15, 15)); button_frame.pack(fill=X)
        button_frame.columnconfigure(0, weight=1)
        ok_button = ttk.Button(button_frame, text="确定", command=self.ok, style='success.TButton')
        ok_button.grid(row=0, column=1, padx=(10, 0))
        cancel_button = ttk.Button(button_frame, text="取消", command=self.cancel)
        cancel_button.grid(row=0, column=2, padx=10)

    def ok(self, event=None):
        selections = self.listbox.curselection()
        if not selections: messagebox.showwarning("未选择", "请在列表中选择一个游戏。", parent=self); return
        self.result = self.games[selections[0]]; self.cancel()

    def cancel(self, event=None): self.parent.focus_set(); self.destroy()

# --- Main GUI Class ---
class CaiInstallGUI(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly", title="Cai Install XP v1.52b1 - GUI Edition")
        self.geometry("850x700")
        self.minsize(700, 550)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.processing_lock = threading.Lock()
        self.create_widgets()
        self.log = self.setup_logging()
        self.backend = GuiBackend(self.log)
        self.create_menu()
        self.after(100, self.initialize_app)

    def setup_logging(self):
        logger = logging.getLogger('CaiInstallGUI')
        logger.setLevel(logging.INFO)
        if logger.hasHandlers(): logger.handlers.clear()
        class GuiHandler(logging.Handler):
            def __init__(self, text_widget): super().__init__(); self.text_widget = text_widget; self.setFormatter(logging.Formatter('%(message)s'))
            def emit(self, record):
                msg = self.format(record); level = record.levelname; is_banner = getattr(record, 'is_banner', False)
                self.text_widget.after(0, self.update_log_text, msg, level, is_banner)
            def update_log_text(self, msg, level, is_banner):
                try:
                    self.text_widget.configure(state='normal')
                    self.text_widget.insert(tk.END, msg + '\n', 'BANNER' if is_banner else level.upper())
                    self.text_widget.configure(state='disabled'); self.text_widget.see(tk.END)
                except tk.TclError: pass
        gui_handler = GuiHandler(self.log_text_widget); logger.addHandler(gui_handler)
        return logger

    def create_menu(self):
        menu_bar = ttk.Menu(self); self.config(menu=menu_bar)
        settings_menu = ttk.Menu(menu_bar, tearoff=False); menu_bar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_command(label="编辑配置", command=self.show_settings_dialog); settings_menu.add_separator()
        settings_menu.add_command(label="退出", command=self.on_closing)
        help_menu = ttk.Menu(menu_bar, tearoff=False); menu_bar.add_cascade(label="更多", menu=help_menu)
        help_menu.add_command(label="官方公告", command=lambda: webbrowser.open('https://docs.qq.com/doc/DTUp3Z2Fkd2pVRGtX?dver='))
        help_menu.add_command(label="GitHub仓库", command=lambda: webbrowser.open('https://github.com/pvzcxw/cai-install_stloader'))
        help_menu.add_command(label="关于", command=self.show_about_dialog)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=BOTH, expand=True)
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=LEFT, fill=BOTH, expand=True)
        
        input_frame = ttk.Labelframe(left_frame, text="输入区", padding=10)
        input_frame.pack(fill=X, pady=(0, 10))
        input_subframe = ttk.Frame(input_frame); input_subframe.pack(fill=X, expand=True)
        ttk.Label(input_subframe, text="游戏AppID或名称:").pack(side=LEFT, padx=(0, 10))
        self.appid_entry = ttk.Entry(input_subframe, font=("", 10)); self.appid_entry.pack(side=LEFT, fill=X, expand=True)
        self.search_button = ttk.Button(input_subframe, text="搜索", command=self.start_game_search); self.search_button.pack(side=LEFT, padx=(10, 0))

        notebook = ttk.Notebook(left_frame); notebook.pack(fill=X, pady=5); self.notebook = notebook
        tab1 = ttk.Frame(notebook, padding=10); notebook.add(tab1, text=" 从指定库安装 ")
        ttk.Label(tab1, text="选择清单库:").pack(side=LEFT, padx=(0, 10))
        self.repo_options = [("SWA V2 (printedwaste)", "swa"), ("Cysaw", "cysaw"), ("Furcate", "furcate"), ("CNGS (assiw)", "cngs"),
                             ("SteamDatabase", "steamdatabase"), ("GitHub - Auiowu/ManifestAutoUpdate", "Auiowu/ManifestAutoUpdate"),
                             ("GitHub - SteamAutoCracks/ManifestHub", "SteamAutoCracks/ManifestHub")]
        self.repo_combobox = ttk.Combobox(tab1, state="readonly", values=[name for name, _ in self.repo_options])
        self.repo_combobox.pack(side=LEFT, fill=X, expand=True); self.repo_combobox.current(0)
        tab2 = ttk.Frame(notebook, padding=10); notebook.add(tab2, text=" 搜索所有GitHub库 ")
        ttk.Label(tab2, text="此模式将通过AppID搜索所有已知的GitHub清单库。").pack(fill=X)

        self.process_button = ttk.Button(left_frame, text="开始处理", command=self.start_processing, style='success.TButton')
        self.process_button.pack(fill=X, pady=10)
        
        self.manager_button = ttk.Button(left_frame, text="入库管理", command=self.toggle_file_panel, style="info.Outline.TButton")
        self.manager_button.pack(fill=X, pady=(0, 10))

        log_frame = ttk.Labelframe(left_frame, text="日志输出", padding=10); log_frame.pack(fill=BOTH, expand=True)
        self.log_text_widget = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state='disabled', font=("Courier New", 9))
        self.log_text_widget.pack(fill=BOTH, expand=True); self.log_text_widget.configure(bg=self.style.colors.get('bg'), fg=self.style.colors.get('fg'))
        self.log_text_widget.tag_config('INFO', foreground=self.style.colors.info); self.log_text_widget.tag_config('WARNING', foreground=self.style.colors.warning)
        self.log_text_widget.tag_config('ERROR', foreground=self.style.colors.danger); self.log_text_widget.tag_config('CRITICAL', foreground=self.style.colors.danger, font=("Courier New", 9, 'bold'))
        self.log_text_widget.tag_config('BANNER', foreground=self.style.colors.primary)
        
        self.status_bar = ttk.Label(self, text=" 正在初始化...", relief=SUNKEN, anchor=W, padding=5); self.status_bar.pack(side=BOTTOM, fill=X)
        self.file_panel = self.create_file_panel(main_frame)
        self.file_panel.pack_forget()

    def create_file_panel(self, parent):
        panel = ttk.Labelframe(parent, text="入库管理", padding=10)
        button_frame = ttk.Frame(panel); button_frame.pack(fill=X, pady=(0, 5))
        refresh_btn = ttk.Button(button_frame, text="🔄 刷新", command=self.refresh_file_list, style="info.TButton")
        refresh_btn.pack(side=LEFT, expand=True, fill=X, padx=(0, 2))
        view_btn = ttk.Button(button_frame, text="📝 查看/编辑", command=self.view_selected_file, style="success.TButton")
        view_btn.pack(side=LEFT, expand=True, fill=X, padx=2)
        delete_btn = ttk.Button(button_frame, text="🗑️ 删除", command=self.delete_selected_file, style="danger.TButton")
        delete_btn.pack(side=LEFT, expand=True, fill=X, padx=(2, 0))
        list_frame = ttk.Frame(panel); list_frame.pack(fill=BOTH, expand=True, pady=(5,0))
        self.file_list = tk.Listbox(list_frame, font=("Consolas", 9), selectmode=tk.EXTENDED)
        self.file_list.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient=VERTICAL, command=self.file_list.yview)
        scrollbar.pack(side=RIGHT, fill=Y); self.file_list.config(yscrollcommand=scrollbar.set)
        self.file_list.configure(bg=self.style.colors.get('bg'), fg=self.style.colors.get('fg'),
                                 selectbackground=self.style.colors.primary, selectforeground='white',
                                 borderwidth=0, highlightthickness=0)
        self.file_list.bind("<Button-3>", self.show_file_context_menu)
        self.file_list.bind("<Double-Button-1>", lambda e: self.view_in_steam_library())
        return panel

    def initialize_app(self):
        self.print_banner(); self.log.info("Cai Install XP GUI版 - 正在初始化..."); self.backend.load_config()
        self.update_unlocker_status()
        self.log.info(f"软件作者: pvzcxw | GUI重制: pvzcxw"); self.log.warning("本项目采用GNU GPLv3开源许可证，完全免费，请勿用于商业用途。")
        self.log.warning("官方Q群: 993782526 | B站: 菜Games-pvzcxw")
        
    def toggle_file_panel(self):
        if self.file_panel.winfo_ismapped():
            self.file_panel.pack_forget()
            self.geometry("850x700")
            self.manager_button.configure(style="info.Outline.TButton")
        else:
            self.file_panel.pack(side=RIGHT, fill=Y, padx=(10, 0))
            self.geometry("1200x700")
            self.manager_button.configure(style="info.TButton")
            self.refresh_file_list()

    def refresh_file_list(self):
        self.file_list.delete(0, tk.END)
        if not self.backend.steam_path or not self.backend.steam_path.exists():
            self.file_list.insert(tk.END, " 未找到Steam安装路径"); return
        plugin_dir = self.backend.steam_path / "config" / "stplug-in"
        if not plugin_dir.exists():
            self.file_list.insert(tk.END, " 插件目录不存在"); return
        try:
            lua_files = [f for f in os.listdir(plugin_dir) if f.endswith(".lua")]
            if not lua_files:
                self.file_list.insert(tk.END, " 暂无入库文件"); return
            lua_files.sort(key=lambda f: (plugin_dir / f).stat().st_mtime, reverse=True)
            for file in lua_files: self.file_list.insert(tk.END, f" {file}")
        except Exception as e:
            self.file_list.insert(tk.END, f" 读取失败: {e}")

    def get_selected_files(self):
        selected_indices = self.file_list.curselection()
        if not selected_indices: return []
        return [self.file_list.get(i).strip() for i in selected_indices]

    def delete_selected_file(self):
        filenames = self.get_selected_files()
        if not filenames: messagebox.showinfo("提示", "请先在列表中选择要删除的文件。", parent=self); return
        msg = f"确定要删除这 {len(filenames)} 个文件吗？\n此操作不可恢复！" if len(filenames) > 1 else f"确定要删除 {filenames[0]} 吗？\n此操作不可恢复！"
        if not messagebox.askyesno("确认删除", msg, parent=self): return
        plugin_dir = self.backend.steam_path / "config" / "stplug-in"
        deleted_count, failed_files = 0, []
        for filename in filenames:
            try:
                file_path = plugin_dir / filename
                if file_path.exists(): os.remove(file_path); deleted_count += 1
                else: failed_files.append(f"{filename} (不存在)")
            except Exception as e: failed_files.append(f"{filename} ({e})")
        if deleted_count > 0: self.log.info(f"成功删除 {deleted_count} 个文件，重启Steam后生效。"); self.refresh_file_list()
        if failed_files: messagebox.showwarning("部分失败", "以下文件删除失败:\n" + "\n".join(failed_files), parent=self)

    def view_selected_file(self):
        filenames = self.get_selected_files()
        if not filenames: messagebox.showinfo("提示", "请选择一个文件进行查看。", parent=self); return
        if len(filenames) > 1: messagebox.showinfo("提示", "请只选择一个文件进行查看。", parent=self); return
        filename = filenames[0]
        try:
            file_path = self.backend.steam_path / "config" / "stplug-in" / filename
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f: content = f.read()
                SimpleNotepad(self, filename, content, str(file_path))
            else: messagebox.showerror("错误", "文件不存在。", parent=self)
        except Exception as e: messagebox.showerror("错误", f"读取文件失败: {e}", parent=self)

    def show_file_context_menu(self, event):
        filenames = self.get_selected_files()
        if not filenames: return
        menu = tk.Menu(self, tearoff=0)
        if len(filenames) == 1:
            filename = filenames[0]
            appid = filename[:-4] if filename.endswith(".lua") else filename
            menu.add_command(label=f"📚 在库中查看 ({appid})", command=lambda: self.view_in_steam_library(filename))
            menu.add_command(label="📁 定位文件", command=lambda: self.locate_file(filename))
            menu.add_separator()
            menu.add_command(label="📝 编辑文件", command=self.view_selected_file)
        menu.add_command(label=f"🗑️ 删除 {len(filenames)} 个文件", command=self.delete_selected_file)
        menu.add_separator()
        menu.add_command(label="🔄 刷新列表", command=self.refresh_file_list)
        menu.tk_popup(event.x_root, event.y_root)

    def locate_file(self, filename):
        file_path = str(self.backend.steam_path / "config" / "stplug-in" / filename)
        if os.path.exists(file_path): subprocess.run(['explorer', '/select,', file_path])
        else: messagebox.showerror("错误", "文件不存在。", parent=self)

    def view_in_steam_library(self, filename=None):
        if not filename: filenames = self.get_selected_files(); filename = filenames[0] if filenames else None
        if not filename: return
        appid = filename[:-4] if filename.endswith(".lua") else filename
        if appid.isdigit(): webbrowser.open(f"steam://nav/games/details/{appid}")
        
    def update_unlocker_status(self):
        steam_path = self.backend.detect_steam_path()
        if not steam_path.exists():
            self.status_bar.config(text="Steam路径未找到！请在设置中指定。"); messagebox.showerror("Steam未找到", "无法自动检测到Steam路径。\n请在“设置”->“编辑配置”中手动指定路径。"); return
        status = self.backend.detect_unlocker()
        if status == "conflict":
            messagebox.showerror("环境冲突", "错误: 同时检测到 SteamTools 和 GreenLuma！\n请手动卸载其中一个以避免冲突，然后重启本程序。")
            self.process_button.config(state=DISABLED); self.status_bar.config(text="环境冲突！请解决后重启。")
        elif status == "none": self.handle_manual_selection()
        if self.backend.unlocker_type: self.status_bar.config(text=f"Steam路径: {steam_path} | 解锁方式: {self.backend.unlocker_type.title()}")

    def handle_manual_selection(self):
        dialog = ManualSelectionDialog(self, title="选择解锁工具"); self.wait_window(dialog)
        if dialog.result in ["steamtools", "greenluma"]:
            self.backend.unlocker_type = dialog.result; self.log.info(f"已手动选择解锁方式: {dialog.result.title()}"); self.update_unlocker_status()
        else:
            self.log.error("未选择解锁工具，部分功能可能无法正常工作。"); self.status_bar.config(text="未选择解锁工具！"); self.process_button.config(state=DISABLED)

    def start_game_search(self):
        if not self.processing_lock.acquire(blocking=False): self.log.warning("已在处理中，请等待当前任务完成。"); return
        search_term = self.appid_entry.get().strip()
        if not search_term: self.log.error("搜索框不能为空！"); self.processing_lock.release(); return
        def thread_target():
            loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
            client = httpx.AsyncClient(verify=False, trust_env=True, timeout=60.0)
            try:
                games = loop.run_until_complete(self.backend.search_games_by_name(client, search_term))
                self.after(0, self.show_game_selection_dialog, games)
            finally:
                loop.run_until_complete(client.aclose()); loop.close(); self.processing_lock.release(); self.after(0, self.search_finished)
        self.search_button.config(state=DISABLED, text="搜索中...")
        thread = threading.Thread(target=thread_target, daemon=True); thread.start()
        
    def search_finished(self): self.search_button.config(state=NORMAL, text="搜索")

    def show_game_selection_dialog(self, games):
        if not games: self.log.warning("未找到匹配的游戏。"); messagebox.showinfo("未找到", "未找到与搜索词匹配的游戏。", parent=self); return
        dialog = GameSelectionDialog(self, games=games)
        if dialog.result:
            selected_game = dialog.result; self.appid_entry.delete(0, tk.END); self.appid_entry.insert(0, selected_game['appid'])
            name = selected_game.get("schinese_name") or selected_game.get("name", "N/A")
            self.log.info(f"已选择游戏: {name} (AppID: {selected_game['appid']})")

    def start_processing(self):
        if not self.backend.unlocker_type: messagebox.showerror("错误", "未确定解锁工具！\n请先通过设置或重启程序解决解锁工具检测问题。"); return
        if not self.processing_lock.acquire(blocking=False): self.log.warning("已在处理中，请等待当前任务完成。"); return
        
        # When ST auto-update is on, default to floating version without asking.
        is_st_auto_update_mode = self.backend.is_steamtools() and self.backend.app_config.get("steamtools_only_lua", False)
        if is_st_auto_update_mode:
            self.backend.st_lock_manifest_version = False # Ensure floating version is used
            self.log.info("SteamTools自动更新模式已启用，将使用浮动版本（不锁定清单版本号）。")
            
        notebook_tab = self.notebook.index('current')
        def thread_target():
            loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
            client = httpx.AsyncClient(verify=False, trust_env=True, timeout=60.0)
            try: loop.run_until_complete(self.run_async_tasks(client, notebook_tab))
            finally:
                loop.run_until_complete(client.aclose()); loop.close()
                self.processing_lock.release(); self.after(0, self.processing_finished)
        self.process_button.config(state=DISABLED, text="正在处理..."); self.appid_entry.config(state=DISABLED); self.search_button.config(state=DISABLED)
        self.status_bar.config(text="正在处理..."); thread = threading.Thread(target=thread_target, daemon=True); thread.start()

    def processing_finished(self):
        self.process_button.config(state=NORMAL, text="开始处理"); self.appid_entry.config(state=NORMAL)
        self.search_button.config(state=NORMAL); self.status_bar.config(text="处理完成，准备就绪。")
        self.log.info("="*80 + "\n处理完成！您可以开始新的任务。")
    
    async def run_async_tasks(self, client: httpx.AsyncClient, tab_index: int):
        user_input = self.appid_entry.get().strip()
        if not user_input: self.log.error("输入不能为空！"); return
        app_id_inputs = [item.strip() for item in user_input.split(',')]
        try:
            if tab_index == 0:
                repo_name, repo_val = self.repo_options[self.repo_combobox.current()]
                self.log.info(f"选择了清单库: {repo_name}")
                await self.process_from_specific_repo(client, app_id_inputs, repo_val)
            elif tab_index == 1:
                self.log.info("模式: 搜索所有GitHub库")
                await self.process_by_searching_all(client, app_id_inputs)
        finally: await self.backend.cleanup_temp_files()

    async def resolve_appids(self, inputs: List[str]) -> List[str]:
        resolved_ids = []
        for item in inputs:
            if app_id := self.backend.extract_app_id(item): resolved_ids.append(app_id)
            else: self.log.warning(f"输入项 '{item}' 不是有效的AppID或链接，已跳过。请使用搜索按钮查找游戏。")
        return list(dict.fromkeys(resolved_ids))

    async def process_from_specific_repo(self, client: httpx.AsyncClient, inputs: List[str], repo_val: str):
        app_ids = await self.resolve_appids(inputs)
        if not app_ids: self.log.error("未能解析出任何有效的AppID。"); return
        self.log.info(f"成功解析的 App IDs: {', '.join(app_ids)}")
        is_github = repo_val not in ["swa", "cysaw", "furcate", "cngs", "steamdatabase"]
        if is_github:
            await self.backend.checkcn(client)
            if not await self.backend.check_github_api_rate_limit(client, self.backend.get_github_headers()): return
        for app_id in app_ids:
            self.log.info(f"--- 正在处理 App ID: {app_id} ---"); success = False
            if repo_val == "swa": success = await self.backend._process_zip_based_manifest(client, app_id, f'https://api.printedwaste.com/gfk/download/{app_id}', "SWA V2")
            elif repo_val == "cysaw": success = await self.backend._process_zip_based_manifest(client, app_id, f'https://cysaw.top/uploads/{app_id}.zip', "Cysaw")
            elif repo_val == "furcate": success = await self.backend._process_zip_based_manifest(client, app_id, f'https://furcate.eu/files/{app_id}.zip', "Furcate")
            elif repo_val == "cngs": success = await self.backend._process_zip_based_manifest(client, app_id, f'https://assiw.cngames.site/qindan/{app_id}.zip', "CNGS")
            elif repo_val == "steamdatabase": success = await self.backend._process_zip_based_manifest(client, app_id, f'https://steamdatabase.s3.eu-north-1.amazonaws.com/{app_id}.zip', "SteamDatabase")
            else: success = await self.process_github_repo(client, app_id, repo_val)
            if success: self.log.info(f"App ID: {app_id} 处理成功。")
            else: self.log.error(f"App ID: {app_id} 处理失败。")

    async def process_by_searching_all(self, client: httpx.AsyncClient, inputs: List[str]):
        app_ids = await self.resolve_appids(inputs)
        if not app_ids: self.log.error("未能解析出任何有效的AppID。"); return
        github_repos = [val for _, val in self.repo_options if val not in ["swa", "cysaw", "furcate", "cngs", "steamdatabase"]]
        await self.backend.checkcn(client)
        if not await self.backend.check_github_api_rate_limit(client, self.backend.get_github_headers()): return
        for app_id in app_ids:
            self.log.info(f"--- 正在为 App ID: {app_id} 搜索所有GitHub库 ---")
            repo_results = await self.backend.search_all_repos(client, app_id, github_repos)
            if not repo_results: self.log.error(f"在所有GitHub库中均未找到 {app_id} 的清单。"); continue
            repo_results.sort(key=lambda x: x['update_date'], reverse=True)
            selected = repo_results[0]
            self.log.info(f"找到 {len(repo_results)} 个结果，将使用最新的清单: {selected['repo']} (更新于 {selected['update_date']})")
            if await self.process_github_repo(client, app_id, selected['repo'], selected): self.log.info(f"App ID: {app_id} 处理成功。")
            else: self.log.error(f"App ID: {app_id} 处理失败。")

    async def process_github_repo(self, client: httpx.AsyncClient, app_id: str, repo: str, existing_data: dict = None) -> bool:
        try:
            headers = self.backend.get_github_headers()
            if existing_data: sha, tree, date = existing_data['sha'], existing_data['tree'], existing_data['update_date']
            else:
                branch_url = f'https://api.github.com/repos/{repo}/branches/{app_id}'
                if not (r_json := await self.backend.fetch_branch_info(client, branch_url, headers)): return False
                sha, date = r_json['commit']['sha'], r_json["commit"]["commit"]["author"]["date"]
                if not (r2_json := await self.backend.fetch_branch_info(client, r_json['commit']['commit']['tree']['url'], headers)): return False
                tree = r2_json['tree']
            all_manifests_in_repo = [item['path'] for item in tree if item['path'].endswith('.manifest')]
            tasks = [self.backend.get_manifest_from_github(client, sha, item['path'], repo, app_id, all_manifests_in_repo) for item in tree]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            collected_depots = []
            for res in results:
                if isinstance(res, Exception): self.log.error(f"下载/处理文件时出错: {res}"); return False
                if res: collected_depots.extend(res)
            if not any(isinstance(res, list) and res is not None for res in results) and not collected_depots:
                 self.log.error(f'仓库中没有找到有效的清单文件或密钥文件: {app_id}'); return False
            if self.backend.is_steamtools(): self.log.info('检测到SteamTools，已自动生成并放置解锁文件。')
            elif collected_depots:
                await self.backend.greenluma_add([app_id] + [depot_id for depot_id, _ in collected_depots])
                await self.backend.depotkey_merge({'depots': {depot_id: {'DecryptionKey': key} for depot_id, key in collected_depots}})
            self.log.info(f'清单最后更新时间: {date}'); return True
        except Exception as e: self.log.error(f"处理GitHub仓库时出错: {self.backend.stack_error(e)}"); return False

    def on_closing(self):
        if self.processing_lock.locked():
            if messagebox.askyesno("退出", "正在处理任务，确定要强制退出吗？"): os._exit(0)
        else: self.destroy()

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
        for line in banner: self.log.info(line, extra={'is_banner': True})

    def show_about_dialog(self):
        messagebox.showinfo("关于", "Cai Install XP v1.52b1 - GUI Edition\n\n原作者: pvzcxw\nGUI重制: pvzcxw\n\n一个用于Steam游戏清单获取和导入的工具")
    
    def show_settings_dialog(self):
        dialog = ttk.Toplevel(self); dialog.title("编辑配置"); dialog.geometry("550x250"); dialog.transient(self); dialog.grab_set()
        frame = ttk.Frame(dialog, padding=15); frame.pack(fill=BOTH, expand=True)
        ttk.Label(frame, text="GitHub Personal Token:").grid(row=0, column=0, sticky=W, pady=5)
        token_entry = ttk.Entry(frame, width=50); token_entry.grid(row=0, column=1, sticky=EW, pady=5); token_entry.insert(0, self.backend.app_config.get("Github_Personal_Token", ""))
        ttk.Label(frame, text="自定义Steam路径:").grid(row=1, column=0, sticky=W, pady=5)
        path_entry = ttk.Entry(frame, width=50); path_entry.grid(row=1, column=1, sticky=EW, pady=5); path_entry.insert(0, self.backend.app_config.get("Custom_Steam_Path", ""))
        st_lua_only_var = tk.BooleanVar(value=self.backend.app_config.get("steamtools_only_lua", False))
        st_lua_only_check = ttk.Checkbutton(frame, text="使用SteamTools进行清单更新 (仅下载LUA，D加密勿选)", variable=st_lua_only_var, bootstyle="round-toggle")
        st_lua_only_check.grid(row=2, column=0, columnspan=2, sticky=W, pady=10)
        button_frame = ttk.Frame(frame); button_frame.grid(row=3, column=0, columnspan=2, pady=15)
        def save_and_close():
            self.backend.app_config["Github_Personal_Token"] = token_entry.get().strip()
            self.backend.app_config["Custom_Steam_Path"] = path_entry.get().strip()
            self.backend.app_config["steamtools_only_lua"] = st_lua_only_var.get()
            self.backend.save_config(); self.log.info("配置已保存。Steam路径等设置将在下次启动或手动刷新时生效。")
            if self.backend.app_config.get("steamtools_only_lua"): self.log.info("已启用 [SteamTools LUA-Only] 模式。")
            self.update_unlocker_status(); dialog.destroy()
        ttk.Button(button_frame, text="保存", command=save_and_close, style='success.TButton').pack(side=LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=LEFT, padx=10)
        frame.columnconfigure(1, weight=1)

class ManualSelectionDialog(tk.Toplevel):
    def __init__(self, parent, title=None):
        super().__init__(parent); self.transient(parent); self.title(title); self.parent = parent; self.result = None; self.grab_set()
        body = ttk.Frame(self, padding=20); self.initial_focus = self.body(body); body.pack()
        self.protocol("WM_DELETE_WINDOW", self.cancel); self.geometry(f"+{parent.winfo_rootx()+50}+{parent.winfo_rooty()+50}"); self.initial_focus.focus_set(); self.wait_window(self)
    def body(self, master):
        ttk.Label(master, text="未能自动检测到解锁工具。\n请根据您的实际情况选择：", justify=LEFT).pack(pady=10)
        st_button = ttk.Button(master, text="我是 SteamTools 用户", command=lambda: self.ok("steamtools")); st_button.pack(fill=X, pady=5)
        gl_button = ttk.Button(master, text="我是 GreenLuma 用户", command=lambda: self.ok("greenluma")); gl_button.pack(fill=X, pady=5)
        return st_button
    def ok(self, result): self.result = result; self.cancel()
    def cancel(self, event=None): self.parent.focus_set(); self.destroy()

def show_startup_info_dialog(parent):
    settings_path = Path('./settings.json'); show_dialog = True
    if settings_path.exists():
        try:
            if not json.loads(settings_path.read_text(encoding='utf-8')).get('show_notification', True): show_dialog = False
        except Exception: pass
    if not show_dialog: return
    dialog = tk.Toplevel(parent); dialog.title("Cai Install 信息提示"); dialog.geometry("400x200"); dialog.resizable(False, False); dialog.transient(parent); dialog.grab_set(); parent.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - 400) // 2; y = parent.winfo_rooty() + (parent.winfo_height() - 200) // 2
    dialog.geometry(f'400x200+{x}+{y}')
    ttk.Label(dialog, text="请加入官方群聊以获取最新公告及更新:\n993782526\n关注官方b站:菜Games-pvzcxw", font=("Arial", 12), justify=CENTER).pack(pady=20)
    dont_show = tk.BooleanVar(value=False); ttk.Checkbutton(dialog, text="不再显示此消息", variable=dont_show, bootstyle="round-toggle").pack(pady=5)
    def on_confirm():
        if dont_show.get():
            try:
                with open(settings_path, 'w', encoding='utf-8') as f: json.dump({'show_notification': False}, f, indent=2)
            except Exception as e: print(f"保存设置失败: {e}")
       # webbrowser.open('https://docs.qq.com/doc/DTUp3Z2Fkd2pVRGtX?dver='); dialog.destroy()
        dialog.destroy()
    ttk.Button(dialog, text="确认", command=on_confirm, bootstyle="success").pack(pady=10)
    parent.wait_window(dialog)

if __name__ == '__main__':
    try: from ctypes import windll; windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    app = CaiInstallGUI()
    show_startup_info_dialog(app)
    app.mainloop()