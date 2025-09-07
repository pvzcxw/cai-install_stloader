import sys
import os
import traceback
import time
import logging
import subprocess
import asyncio
import random
import string
import re
import aiofiles
import colorlog
import httpx
import winreg
import ujson as json
import vdf
import zipfile
import shutil
import struct
import zlib
import io  # Added for ZIP handling
from pathlib import Path
from typing import Tuple, Any, List, Dict, Literal

CURRENT_VERSION = "1.58p1"  # 当前版本号
GITHUB_REPO = "pvzcxw/cai-install_stloader" 

# --- LOGGING SETUP ---
LOG_FORMAT = '%(log_color)s%(message)s'
LOG_COLORS = {
    'INFO': 'cyan',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'purple',
}

# --- DEFAULT CONFIG ---
# --- MODIFIED: Added Custom_Repos setting ---
DEFAULT_CONFIG = {
    "Github_Personal_Token": "",
    "Custom_Steam_Path": "",
    "Force_Unlocker": "",
    "Custom_Repos": {
        "github": [],
        "zip": []
    },
    "QA1": "温馨提示: Github_Personal_Token(个人访问令牌)可在Github设置的最底下开发者选项中找到, 详情请看教程。",
    "QA2": "Force_Unlocker: 强制指定解锁工具, 填入 'steamtools' 或 'greenluma'。留空则自动检测。",
    "QA3": "Custom_Repos: 自定义清单库配置。github数组用于添加GitHub仓库，zip数组用于添加ZIP清单库。",
    "QA4": "GitHub仓库格式: {\"name\": \"显示名称\", \"repo\": \"用户名/仓库名\"}",
    "QA5": "ZIP清单库格式: {\"name\": \"显示名称\", \"url\": \"下载URL，用{app_id}作为占位符\"}"
}

class STConverter:
    def __init__(self):
        self.logger = logging.getLogger('STConverter')

    def convert_file(self, st_path: str) -> str:
        try:
            content, _ = self.parse_st_file(st_path)
            return content
        except Exception as e:
            self.logger.error(f'ST文件转换失败: {st_path} - {e}')
            raise

    def parse_st_file(self, st_file_path: str) -> Tuple[str, dict]:
        with open(st_file_path, 'rb') as stfile:
            content = stfile.read()
        if len(content) < 12: raise ValueError("文件头过短")
        header = content[:12]
        xorkey, size, xorkeyverify = struct.unpack('III', header)
        xorkey ^= 0xFFFEA4C8
        xorkey &= 0xFF
        encrypted_data = content[12:12+size]
        if len(encrypted_data) < size: raise ValueError("加密数据小于预期大小")
        data = bytearray(encrypted_data)
        for i in range(len(data)):
            data[i] ^= xorkey
        decompressed_data = zlib.decompress(data)
        lua_content = decompressed_data[512:].decode('utf-8')
        metadata = {'original_xorkey': xorkey, 'size': size, 'xorkeyverify': xorkeyverify}
        return lua_content, metadata

class CaiBackend:
    def __init__(self):
        self.client = httpx.AsyncClient(verify=False, trust_env=True, timeout=30)
        self.config = {}
        self.steam_path = None
        self.unlocker_type = None
        self.use_st_auto_update = False
        self.lock = asyncio.Lock()
        self.temp_path = Path('./temp')
        self.log = self._init_log()

    def _init_log(self, level=logging.DEBUG) -> logging.Logger:
        logger = logging.getLogger(' Cai install')
        logger.setLevel(level)
        if not logger.handlers:
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(level)
            fmt = colorlog.ColoredFormatter(LOG_FORMAT, log_colors=LOG_COLORS)
            stream_handler.setFormatter(fmt)
            logger.addHandler(stream_handler)
        return logger
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        try:
            import re
            
            def parse_version(v):
                # 分离主版本号和后缀
                match = re.match(r'(\d+(?:\.\d+)*)(.*)', v)
                if not match:
                    return (0, 0, 0), ''
                
                version_nums = match.group(1)
                suffix = match.group(2)
                
                # 解析版本号
                parts = version_nums.split('.')
                # 填充到3位
                while len(parts) < 3:
                    parts.append('0')
                
                # 转换为整数元组
                version_tuple = tuple(int(p) for p in parts[:3])
                
                return version_tuple, suffix
            
            v1_tuple, v1_suffix = parse_version(v1)
            v2_tuple, v2_suffix = parse_version(v2)
            
            # 首先比较主版本号
            if v1_tuple < v2_tuple:
                return -1
            elif v1_tuple > v2_tuple:
                return 1
            
            # 版本号相同，比较后缀
            # 空后缀被认为是正式版本，高于带后缀的版本
            if not v1_suffix and v2_suffix:
                return 1
            elif v1_suffix and not v2_suffix:
                return -1
            elif v1_suffix < v2_suffix:
                return -1
            elif v1_suffix > v2_suffix:
                return 1
            
            return 0
            
        except Exception as e:
            self.log.warning(f"版本比较失败: {e}")
            return 0
    
    async def download_update(self, download_url: str, save_path: Path) -> bool:
        try:
            self.log.info(f"开始下载更新: {download_url}")
            
            # 创建保存目录
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 下载文件
            response = await self.client.get(download_url, follow_redirects=True, timeout=300)
            response.raise_for_status()
            
            # 保存文件
            async with aiofiles.open(save_path, 'wb') as f:
                await f.write(response.content)
            
            self.log.info(f"更新下载完成: {save_path}")
            return True
            
        except Exception as e:
            self.log.error(f"下载更新失败: {e}")
            return False
        
    async def check_for_updates(self) -> Tuple[bool, Dict]:
        """
        检查是否有新版本可用
        返回: (是否有更新, 版本信息字典)
        """
        try:
            self.log.info("正在检查更新...")
            
            # GitHub API URL
            api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            
            # 获取 GitHub token（如果有的话）
            github_token = self.config.get("Github_Personal_Token", "").strip()
            headers = {'Authorization': f'Bearer {github_token}'} if github_token else {}
            
            # 添加 User-Agent 以避免 API 限制
            headers['User-Agent'] = 'Cai-Install-Updater'
            
            # 发送请求
            response = await self.client.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 404:
                # 没有发布版本
                self.log.info("未找到发布版本")
                return False, {}
            
            response.raise_for_status()
            release_data = response.json()
            
            # 提取版本信息
            latest_version = release_data.get('tag_name', '').strip()
            if latest_version.startswith('v'):
                latest_version = latest_version[1:]  # 去掉 'v' 前缀
            
            release_name = release_data.get('name', '')
            release_body = release_data.get('body', '')
            release_url = release_data.get('html_url', '')
            published_at = release_data.get('published_at', '')
            
            # 获取下载链接
            download_urls = []
            assets = release_data.get('assets', [])
            for asset in assets:
                download_urls.append({
                    'name': asset.get('name', ''),
                    'url': asset.get('browser_download_url', ''),
                    'size': asset.get('size', 0)
                })
            
            # 如果没有 assets，使用 zipball_url
            if not download_urls and release_data.get('zipball_url'):
                download_urls.append({
                    'name': 'Source code (zip)',
                    'url': release_data.get('zipball_url', ''),
                    'size': 0
                })
            
            # 比较版本
            if self._compare_versions(CURRENT_VERSION, latest_version) < 0:
                self.log.info(f"发现新版本: {latest_version} (当前版本: {CURRENT_VERSION})")
                return True, {
                    'current_version': CURRENT_VERSION,
                    'latest_version': latest_version,
                    'release_name': release_name,
                    'release_body': release_body,
                    'release_url': release_url,
                    'published_at': published_at,
                    'download_urls': download_urls
                }
            else:
                self.log.info(f"当前已是最新版本 ({CURRENT_VERSION})")
                return False, {}
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                self.log.warning("GitHub API 请求次数已用尽，跳过更新检查")
            else:
                self.log.warning(f"检查更新时 HTTP 错误: {e}")
            return False, {}
        except httpx.TimeoutException:
            self.log.warning("检查更新超时，跳过")
            return False, {}
        except Exception as e:
            self.log.warning(f"检查更新失败: {e}")
            return False, {}

    # --- MODIFIED: Added logic to handle forced unlocker from config ---
    async def initialize(self) -> Literal["steamtools", "greenluma", "conflict", "none", None]:
        self.config = await self.load_config()
        if self.config is None:
            return None

        self.steam_path = self.get_steam_path()
        if not self.steam_path or not self.steam_path.exists():
            self.log.error('无法确定有效的Steam路径。正在退出。')
            return None

        # --- NEW: Check for forced unlocker setting ---
        forced_unlocker = str(self.config.get("Force_Unlocker", "")).strip().lower()
        if forced_unlocker in ["steamtools", "greenluma"]:
            self.unlocker_type = forced_unlocker
            self.log.warning(f"已根据配置文件强制使用解锁工具: {self.unlocker_type.capitalize()}")
            # By returning the type directly, we bypass the auto-detection logic below.
            # The processing functions will then create necessary directories if they don't exist.
            return self.unlocker_type
        # --- END OF NEW LOGIC ---

        self.log.info(f"Steam路径: {self.steam_path}")

        is_steamtools = (self.steam_path / 'config' / 'stplug-in').is_dir()
        is_greenluma = any((self.steam_path / dll).exists() for dll in ['GreenLuma_2025_x86.dll', 'GreenLuma_2025_x64.dll'])

        if is_steamtools and is_greenluma:
            self.log.error("环境冲突：同时检测到SteamTools和GreenLuma！")
            return "conflict"
        elif is_steamtools:
            self.log.info("检测到解锁工具: SteamTools")
            self.unlocker_type = "steamtools"
            return "steamtools"
        elif is_greenluma:
            self.log.info("检测到解锁工具: GreenLuma")
            self.unlocker_type = "greenluma"
            return "greenluma"
        else:
            self.log.warning("未能自动检测到解锁工具。")
            return "none"

    def is_steamtools(self):
        return self.unlocker_type == "steamtools"

    async def close_resources(self):
        await self.client.aclose()

    def stack_error(self, exception: Exception) -> str:
        return ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))

    async def gen_config_file(self):
        try:
            async with aiofiles.open("./config.json", mode="w", encoding="utf-8") as f:
                await f.write(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False))
            self.log.info('未识别到config.json，可能为首次启动，已自动生成，若进行配置重启生效')
        except Exception as e:
            self.log.error(f'生成配置文件失败: {self.stack_error(e)}')

    async def load_config(self) -> Dict | None:
        if not os.path.exists('./config.json'):
            await self.gen_config_file()
            return DEFAULT_CONFIG

        try:
            async with aiofiles.open("./config.json", mode="r", encoding="utf-8") as f:
                # --- MODIFIED: Load config and merge with defaults to handle new keys ---
                user_config = json.loads(await f.read())
                config = DEFAULT_CONFIG.copy()
                config.update(user_config)
                
                # --- NEW: Ensure Custom_Repos structure exists ---
                if 'Custom_Repos' not in config:
                    config['Custom_Repos'] = {"github": [], "zip": []}
                elif not isinstance(config['Custom_Repos'], dict):
                    config['Custom_Repos'] = {"github": [], "zip": []}
                else:
                    if 'github' not in config['Custom_Repos']:
                        config['Custom_Repos']['github'] = []
                    if 'zip' not in config['Custom_Repos']:
                        config['Custom_Repos']['zip'] = []
                
                return config
        except Exception as e:
            self.log.error(f"加载配置文件失败: {self.stack_error(e)}。正在重置配置文件...")
            if os.path.exists("./config.json"):
                os.remove("./config.json")
            await self.gen_config_file()
            self.log.error("配置文件已损坏并被重置。请重启程序。")
            return None

    def get_steam_path(self) -> Path | None:
        try:
            custom_steam_path = self.config.get("Custom_Steam_Path", "").strip()
            if custom_steam_path:
                self.log.info(f"正使用配置文件中的自定义Steam路径: {custom_steam_path}")
                return Path(custom_steam_path)

            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
            return Path(winreg.QueryValueEx(key, 'SteamPath')[0])
        except Exception as e:
            self.log.error(f'获取Steam路径失败: {self.stack_error(e)}。请检查Steam是否正确安装，或在config.json中设置Custom_Steam_Path。')
            return None

    # --- NEW: Custom repository support functions ---
    def get_custom_github_repos(self) -> List[Dict]:
        """获取自定义GitHub仓库列表"""
        custom_repos = self.config.get("Custom_Repos", {}).get("github", [])
        validated_repos = []
        
        for repo in custom_repos:
            if isinstance(repo, dict) and 'name' in repo and 'repo' in repo:
                validated_repos.append(repo)
            else:
                self.log.warning(f"无效的自定义GitHub仓库配置: {repo}")
        
        return validated_repos

    def get_custom_zip_repos(self) -> List[Dict]:
        """获取自定义ZIP仓库列表"""
        custom_repos = self.config.get("Custom_Repos", {}).get("zip", [])
        validated_repos = []
        
        for repo in custom_repos:
            if isinstance(repo, dict) and 'name' in repo and 'url' in repo:
                # 验证URL中是否包含{app_id}占位符
                if '{app_id}' in repo['url']:
                    validated_repos.append(repo)
                else:
                    self.log.warning(f"自定义ZIP仓库URL缺少{{app_id}}占位符: {repo}")
            else:
                self.log.warning(f"无效的自定义ZIP仓库配置: {repo}")
        
        return validated_repos

    async def process_custom_zip_manifest(self, app_id: str, repo_config: Dict, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        """处理自定义ZIP清单库"""
        repo_name = repo_config.get('name', '未知仓库')
        url_template = repo_config.get('url', '')
        
        # 替换占位符
        download_url = url_template.replace('{app_id}', app_id)
        
        return await self._process_zip_manifest_generic(app_id, download_url, f"自定义ZIP库 ({repo_name})", add_all_dlc, patch_depot_key)

    def get_all_github_repos(self) -> List[str]:
        """获取所有GitHub仓库（内置+自定义）"""
        builtin_repos = ['Auiowu/ManifestAutoUpdate', 'SteamAutoCracks/ManifestHub']
        custom_repos = [repo['repo'] for repo in self.get_custom_github_repos()]
        return builtin_repos + custom_repos

    # --- NEW: DepotKey patching methods (ported from web version) ---
    async def download_depotkeys_json(self) -> Dict | None:
        """Download depotkeys.json from SteamAutoCracks repository with mirror support"""
        try:
            self.log.info("正在从 SteamAutoCracks 仓库下载 depotkeys.json...")
            
            # Define multiple mirror URLs
            urls = ["https://raw.githubusercontent.com/SteamAutoCracks/ManifestHub/main/depotkeys.json"]
            
            # Add Chinese mirrors if in China
            if os.environ.get('IS_CN') == 'yes':
                urls = [
                    "https://cdn.jsdmirror.com/gh/SteamAutoCracks/ManifestHub@main/depotkeys.json",
                    "https://raw.gitmirror.com/SteamAutoCracks/ManifestHub/main/depotkeys.json", 
                    "https://raw.dgithub.xyz/SteamAutoCracks/ManifestHub/main/depotkeys.json",
                    "https://gh.akass.cn/SteamAutoCracks/ManifestHub/main/depotkeys.json",
                    "https://raw.githubusercontent.com/SteamAutoCracks/ManifestHub/main/depotkeys.json"
                ]
            
            # Try each URL with retries
            for attempt, url in enumerate(urls, 1):
                try:
                    self.log.info(f"尝试从源 {attempt}/{len(urls)} 下载: {url.split('/')[2]}")
                    
                    # Use shorter timeout for each attempt, with retries
                    for retry in range(2):  # 2 retries per URL
                        try:
                            response = await self.client.get(url, timeout=15)
                            response.raise_for_status()
                            
                            depotkeys_data = response.json()
                            self.log.info(f"成功下载 depotkeys.json，包含 {len(depotkeys_data)} 个条目。(来源: {url.split('/')[2]})")
                            return depotkeys_data
                            
                        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as timeout_err:
                            if retry == 0:  # First retry
                                self.log.warning(f"连接超时，正在重试... (源: {url.split('/')[2]})")
                                await asyncio.sleep(1)  # Brief delay before retry
                                continue
                            else:
                                raise timeout_err
                        
                except Exception as e:
                    error_msg = str(e)
                    if "timeout" in error_msg.lower() or "ConnectTimeout" in str(type(e)):
                        self.log.warning(f"源 {url.split('/')[2]} 连接超时，尝试下一个源...")
                    else:
                        self.log.warning(f"源 {url.split('/')[2]} 下载失败: {error_msg}")
                    
                    # Don't immediately fail, try next URL
                    if attempt < len(urls):
                        continue
                    else:
                        # This was the last URL, re-raise the exception
                        raise e
            
            # If we get here, all URLs failed
            raise Exception("所有镜像源均不可用")
            
        except Exception as e:
            self.log.error(f"下载 depotkeys.json 失败: {self.stack_error(e)}")
            self.log.error("建议检查网络连接或稍后重试。")
            return None

    async def patch_lua_with_depotkey(self, app_id: str, lua_file_path: Path) -> bool:
        """Patch LUA file with depotkey from SteamAutoCracks repository"""
        try:
            # Ensure network environment is detected for mirror selection
            if 'IS_CN' not in os.environ:
                self.log.info("检测网络环境以优化下载源选择...")
                await self.checkcn()
            
            # Download depotkeys.json
            depotkeys_data = await self.download_depotkeys_json()
            if not depotkeys_data:
                self.log.error("无法获取 depotkeys 数据，跳过 depotkey 修补。")
                return False
            
            # Check if app_id exists in depotkeys
            if app_id not in depotkeys_data:
                self.log.warning(f"没有此AppID的depotkey: {app_id}")
                return False
            
            depotkey = depotkeys_data[app_id]
            
            # Check if depotkey is valid (not empty, not None, not just whitespace)
            if not depotkey or not str(depotkey).strip():
                self.log.warning(f"AppID {app_id} 的 depotkey 为空或无效，跳过修补: '{depotkey}'")
                return False
            
            # Make sure depotkey is string and strip whitespace
            depotkey = str(depotkey).strip()
            self.log.info(f"找到 AppID {app_id} 的有效 depotkey: {depotkey}")
            
            # Read existing LUA file
            if not lua_file_path.exists():
                self.log.error(f"LUA文件不存在: {lua_file_path}")
                return False
            
            async with aiofiles.open(lua_file_path, 'r', encoding='utf-8') as f:
                lua_content = await f.read()
            
            # Parse lines
            lines = lua_content.strip().split('\n')
            new_lines = []
            app_id_line_removed = False
            
            # Remove existing addappid({app_id}) line and add new one with depotkey
            for line in lines:
                line = line.strip()
                # Check if this is the simple addappid line we need to replace
                if line == f"addappid({app_id})":
                    # Replace with depotkey version
                    new_lines.append(f'addappid({app_id},1,"{depotkey}")')
                    app_id_line_removed = True
                    self.log.info(f"已替换: addappid({app_id}) -> addappid({app_id},1,\"{depotkey}\")")
                else:
                    new_lines.append(line)
            
            # If we didn't find the simple addappid line, add the depotkey version
            if not app_id_line_removed:
                new_lines.append(f'addappid({app_id},1,"{depotkey}")')
                self.log.info(f"已添加新的 depotkey 条目: addappid({app_id},1,\"{depotkey}\")")
            
            # Write back to file
            async with aiofiles.open(lua_file_path, 'w', encoding='utf-8') as f:
                await f.write('\n'.join(new_lines) + '\n')
            
            self.log.info(f"成功修补 LUA 文件的 depotkey: {lua_file_path.name}")
            return True
            
        except Exception as e:
            self.log.error(f"修补 LUA depotkey 时出错: {self.stack_error(e)}")
            return False

    async def _get_buqiuren_session_token(self) -> str | None:
        """获取不求人接口的会话令牌"""
        backup_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://manifest.steam.run/",
                "Origin": "https://manifest.steam.run",
                "Accept": "application/json, text/plain, */*",
            }
            
            session_resp = await self.client.post(
                "https://manifest.steam.run/api/session", 
                headers=headers,
                timeout=30
            )
            
            if session_resp.status_code == 200:
                data = session_resp.json()
                if "token" in data:
                    token = data["token"]
                    self.log.info(f"成功获取不求人会话令牌: ...{token[-6:]}")
                    return token
            
            self.log.warning("使用备用令牌")
            
        except Exception as e:
            self.log.warning(f"获取不求人会话令牌时出错: {e}")
        
        return backup_token

    async def _download_manifest_buqiuren(self, depot_id: str, manifest_id: str, depot_name: str) -> bool:
        """使用不求人接口下载清单"""
        output_filename = f"{depot_id}_{manifest_id}.manifest"
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # 获取session token
                session_token = await self._get_buqiuren_session_token()
                if not session_token:
                    self.log.error("无法获取会话令牌")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(5)
                        continue
                    return False
                
                # 请求下载链接
                self.log.info(f"正在请求清单下载链接... [Depot: {depot_id}, Manifest: {manifest_id}]")
                
                request_payload = {
                    "depot_id": str(depot_id),
                    "manifest_id": str(manifest_id),
                    "token": session_token
                }
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://manifest.steam.run/",
                    "Origin": "https://manifest.steam.run",
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json"
                }
                
                # 等待避免频率限制
                await asyncio.sleep(random.uniform(2, 5))
                
                code_response = await self.client.post(
                    "https://manifest.steam.run/api/request-code",
                    json=request_payload,
                    headers=headers,
                    timeout=60
                )
                
                if code_response.status_code == 429:
                    self.log.warning(f"请求频率过高，等待后重试...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(30)
                        continue
                    return False
                
                if code_response.status_code != 200:
                    self.log.error(f"请求失败，状态码: {code_response.status_code}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(10)
                        continue
                    return False
                
                try:
                    code_data = code_response.json()
                except:
                    self.log.error("服务器返回无效的JSON响应")
                    if attempt < max_retries - 1:
                        continue
                    return False
                
                download_url = code_data.get("download_url")
                if not download_url:
                    error_msg = code_data.get('error', code_data.get('message', '未知错误'))
                    self.log.error(f"请求下载链接失败: {error_msg}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(15)
                        continue
                    return False
                
                self.log.info(f"获取到下载链接")
                
                # 下载清单文件
                self.log.info("正在下载清单文件...")
                manifest_response = await self.client.get(download_url, timeout=180)
                
                if manifest_response.status_code != 200:
                    self.log.error(f"下载失败，状态码: {manifest_response.status_code}")
                    if attempt < max_retries - 1:
                        continue
                    return False
                
                manifest_content = manifest_response.content
                
                # 处理文件内容（检查是否为ZIP）
                final_content = None
                
                if manifest_content.startswith(b'PK\x03\x04'):
                    self.log.info("检测到ZIP文件，正在自动解压...")
                    try:
                        with io.BytesIO(manifest_content) as mem_zip:
                            with zipfile.ZipFile(mem_zip, 'r') as z:
                                file_list = z.namelist()
                                if len(file_list) == 1:
                                    target_file = file_list[0]
                                    self.log.info(f"从ZIP中提取文件: {target_file}")
                                    final_content = z.read(target_file)
                                else:
                                    self.log.warning(f"ZIP包中文件数量不为1: {len(file_list)}")
                                    final_content = manifest_content
                    except Exception as e:
                        self.log.warning(f"处理ZIP文件时出错: {e}")
                        final_content = manifest_content
                else:
                    final_content = manifest_content
                
                if not final_content:
                    self.log.error("最终文件内容为空")
                    if attempt < max_retries - 1:
                        continue
                    return False
                
                # 保存文件到depotcache目录
                if self.is_steamtools():
                    st_depot_path = self.steam_path / 'config' / 'depotcache'
                    gl_depot_path = self.steam_path / 'depotcache'
                    
                    st_depot_path.mkdir(parents=True, exist_ok=True)
                    gl_depot_path.mkdir(parents=True, exist_ok=True)
                    
                    (st_depot_path / output_filename).write_bytes(final_content)
                    self.log.info(f"清单已保存到: {st_depot_path / output_filename}")
                    
                    (gl_depot_path / output_filename).write_bytes(final_content)
                    self.log.info(f"清单已保存到: {gl_depot_path / output_filename}")
                else:
                    # GreenLuma
                    depot_path = self.steam_path / 'depotcache'
                    depot_path.mkdir(parents=True, exist_ok=True)
                    (depot_path / output_filename).write_bytes(final_content)
                    self.log.info(f"清单已保存到: {depot_path / output_filename}")
                
                self.log.info(f"成功下载清单: {depot_name} ({output_filename})")
                return True
                
            except Exception as e:
                self.log.error(f"下载过程中出错: {e}")
                if attempt < max_retries - 1:
                    self.log.info(f"等待后重试... (尝试 {attempt + 2}/{max_retries})")
                    await asyncio.sleep(15)
                    continue
        
        self.log.error(f"下载清单 {output_filename} 失败：所有重试都失败了")
        return False

    async def process_buqiuren_manifest(self, app_id: str) -> bool:
        """处理不求人库清单下载"""
        try:
            self.log.info(f'正从 清单不求人库 处理 AppID {app_id} 的清单...')
            
            # 使用steamui API获取depot和manifest信息（复用现有逻辑）
            depot_manifest_map = await self._get_depots_and_manifests_from_steamui(app_id)
            if not depot_manifest_map:
                self.log.error(f"未能从 steamui API 获取到 AppID {app_id} 的 depot 信息")
                return False
            
            self.log.info(f"从 steamui API 获取到 {len(depot_manifest_map)} 个 depot 及其 manifest")
            
            # 下载所有depot的清单
            success_count = 0
            total_count = len(depot_manifest_map)
            
            for i, (depot_id, manifest_id) in enumerate(depot_manifest_map.items(), 1):
                self.log.info(f"处理进度: {i}/{total_count}")
                depot_name = f"Depot {depot_id}"
                
                # 使用不求人接口下载
                if await self._download_manifest_buqiuren(depot_id, manifest_id, depot_name):
                    success_count += 1
                else:
                    self.log.warning(f"下载 depot {depot_id} 的清单失败")
                
                # 添加延迟避免频率限制
                if i < total_count:
                    delay = random.uniform(10, 20)
                    self.log.info(f"等待 {delay:.1f} 秒后继续...")
                    await asyncio.sleep(delay)
            
            if success_count == 0:
                self.log.error(f"AppID {app_id} 没有成功下载任何清单")
                return False
            
            self.log.info(f"成功处理不求人库清单: 成功 {success_count}/{total_count}")
            return True
            
        except Exception as e:
            self.log.error(f'处理不求人库清单时出错: {self.stack_error(e)}')
            return False

    def _extract_workshop_id(self, input_text: str) -> str | None:
        """从URL或ID字符串中提取创意工坊ID"""
        input_text = input_text.strip()
        if not input_text:
            return None
        # 尝试从URL中提取ID
        url_match = re.search(r"https?://steamcommunity\.com/sharedfiles/filedetails/\?id=(\d+)", input_text)
        if url_match:
            return url_match.group(1)
        # 如果输入就是数字，直接返回
        if input_text.isdigit():
            return input_text
        return None

    async def _get_workshop_details(self, workshop_id: str) -> Tuple[str, str, str] | None:
        """异步获取创意工坊物品的Depot和Manifest信息"""
        self.log.info(f"正在查询创意工坊物品 {workshop_id} 的信息...")
        api_url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
        data = {'itemcount': 1, 'publishedfileids[0]': workshop_id}
        
        max_retries, retry_delay = 3, 2
        for attempt in range(max_retries):
            try:
                response = await self.client.post(api_url, data=data)
                response.raise_for_status()
                result = response.json()

                if 'response' not in result or 'publishedfiledetails' not in result['response'] or not result['response']['publishedfiledetails']:
                    self.log.error("API响应格式不正确或未找到物品详情")
                    return None
                
                details = result['response']['publishedfiledetails'][0]
                if int(details.get('result', 0)) != 1:
                    self.log.error(f"未找到创意工坊物品: {workshop_id}")
                    return None
                
                consumer_app_id = details.get('consumer_app_id')
                hcontent_file = details.get('hcontent_file')
                title = details.get('title', '未知标题')

                if not consumer_app_id or not hcontent_file:
                    self.log.error(f"创意工坊物品 '{title}' 缺少必要的信息 (App ID 或 Manifest ID)。")
                    return None
                
                self.log.info(f"成功获取创意工坊物品信息:")
                self.log.info(f"  标题: {title}")
                self.log.info(f"  所属游戏 AppID: {consumer_app_id}")
                self.log.info(f"  清单 ManifestID: {hcontent_file}")
                return str(consumer_app_id), str(hcontent_file), title

            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    self.log.warning(f"API请求失败，正在重试 ({attempt+1}/{max_retries})...")
                    await asyncio.sleep(retry_delay)
                else:
                    self.log.error(f"API请求失败: {e}")
                    return None
            except Exception as e:
                self.log.error(f"获取创意工坊物品信息出错: {self.stack_error(e)}")
                return None

# 在 backend.py 中替换 _download_and_place_workshop_manifest 方法

    async def _download_and_place_workshop_manifest(self, depot_id: str, manifest_id: str) -> bool:
        """下载清单文件并放置到正确的文件夹"""
        output_filename = f"{depot_id}_{manifest_id}.manifest"
        self.log.info(f"准备下载清单: {output_filename}")
        
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Step 1: 获取 session token
                session_token = await self._get_session_token()
                if not session_token:
                    self.log.error("无法获取会话令牌")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(5)
                        continue
                    return False
                
                # Step 2: 请求下载代码
                self.log.info(f"正在请求清单下载链接... [Depot: {depot_id}, Manifest: {manifest_id}]")
                
                request_payload = {
                    "depot_id": str(depot_id),
                    "manifest_id": str(manifest_id),
                    "token": session_token
                }
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://manifest.steam.run/",
                    "Origin": "https://manifest.steam.run",
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json"
                }
                
                # 等待避免频率限制
                await asyncio.sleep(2)
                
                code_response = await self.client.post(
                    "https://manifest.steam.run/api/request-code",
                    json=request_payload,
                    headers=headers,
                    timeout=60
                )
                
                if code_response.status_code == 429:
                    self.log.warning(f"请求频率过高，等待后重试...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(30)
                        continue
                    return False
                
                if code_response.status_code != 200:
                    self.log.error(f"请求失败，状态码: {code_response.status_code}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(10)
                        continue
                    return False
                
                try:
                    code_data = code_response.json()
                except:
                    self.log.error("服务器返回无效的JSON响应")
                    if attempt < max_retries - 1:
                        continue
                    return False
                
                download_url = code_data.get("download_url")
                if not download_url:
                    error_msg = code_data.get('error', code_data.get('message', '未知错误'))
                    self.log.error(f"请求下载链接失败: {error_msg}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(15)
                        continue
                    return False
                
                self.log.info(f"获取到下载链接")
                
                # Step 3: 下载清单文件
                self.log.info("正在下载清单文件...")
                manifest_response = await self.client.get(download_url, timeout=180)
                
                if manifest_response.status_code != 200:
                    self.log.error(f"下载失败，状态码: {manifest_response.status_code}")
                    if attempt < max_retries - 1:
                        continue
                    return False
                
                manifest_content = manifest_response.content
                
                # Step 4: 处理文件内容（检查是否为ZIP）
                final_content = None
                
                # 检查是否为ZIP文件
                if manifest_content.startswith(b'PK\x03\x04'):
                    self.log.info("检测到ZIP文件，正在自动解压...")
                    import io
                    import zipfile
                    try:
                        with io.BytesIO(manifest_content) as mem_zip:
                            with zipfile.ZipFile(mem_zip, 'r') as z:
                                file_list = z.namelist()
                                if len(file_list) == 1:
                                    target_file = file_list[0]
                                    self.log.info(f"从ZIP中提取文件: {target_file}")
                                    final_content = z.read(target_file)
                                else:
                                    self.log.warning(f"ZIP包中文件数量不为1: {len(file_list)}")
                                    final_content = manifest_content
                    except Exception as e:
                        self.log.warning(f"处理ZIP文件时出错: {e}")
                        final_content = manifest_content
                else:
                    self.log.info("文件不是ZIP，将直接保存。")
                    final_content = manifest_content
                
                if not final_content:
                    self.log.error("最终文件内容为空")
                    if attempt < max_retries - 1:
                        continue
                    return False
                
                # Step 5: 保存文件
                st_depot_path = self.steam_path / 'config' / 'depotcache'
                gl_depot_path = self.steam_path / 'depotcache'
                
                st_depot_path.mkdir(parents=True, exist_ok=True)
                gl_depot_path.mkdir(parents=True, exist_ok=True)
                
                (st_depot_path / output_filename).write_bytes(final_content)
                self.log.info(f"清单已保存到: {st_depot_path / output_filename}")
                
                (gl_depot_path / output_filename).write_bytes(final_content)
                self.log.info(f"清单已保存到: {gl_depot_path / output_filename}")
                
                self.log.info(f"成功处理创意工坊清单 {output_filename}。")
                return True
                
            except Exception as e:
                self.log.error(f"下载过程中出错: {e}")
                if attempt < max_retries - 1:
                    self.log.info(f"等待后重试... (尝试 {attempt + 2}/{max_retries})")
                    await asyncio.sleep(15)
                    continue
        
        self.log.error(f"下载清单 {output_filename} 失败：所有重试都失败了")
        return False
    
    async def _get_session_token(self) -> str | None:
        """获取manifest.steam.run会话令牌"""
        
        backup_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        
        try:
            self.log.info("正在获取会话令牌...")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://manifest.steam.run/",
                "Origin": "https://manifest.steam.run",
                "Accept": "application/json, text/plain, */*",
            }
            
            session_resp = await self.client.post(
                "https://manifest.steam.run/api/session", 
                headers=headers,
                timeout=30
            )
            
            if session_resp.status_code == 200:
                data = session_resp.json()
                if "token" in data:
                    token = data["token"]
                    self.log.info(f"成功获取会话令牌: ...{token[-6:]}")
                    return token
            
            self.log.warning("会话令牌获取失败，使用备用令牌")
            
        except Exception as e:
            self.log.warning(f"获取会话令牌时出错: {e}，使用备用令牌")
        
        return backup_token

    async def process_workshop_manifest(self, workshop_input: str) -> bool:
        """处理单个创意工坊物品的完整流程"""
        workshop_id = self._extract_workshop_id(workshop_input)
        if not workshop_id:
            self.log.error(f"无效的创意工坊物品ID或URL: '{workshop_input}'")
            return False
            
        details = await self._get_workshop_details(workshop_id)
        if not details:
            return False # 错误已在 _get_workshop_details 中记录
        
        consumer_app_id, hcontent_file, _ = details
        
        # 创意工坊的 Depot ID 就是其所属游戏的 App ID
        return await self._download_and_place_workshop_manifest(consumer_app_id, hcontent_file)

    # --- END OF WORKSHOP FUNCTIONALITY (FIXED) ---
    
    async def check_github_api_rate_limit(self) -> bool:
        github_token = self.config.get("Github_Personal_Token", "").strip()
        headers = {'Authorization': f'Bearer {github_token}'} if github_token else None

        if github_token:
            self.log.info("已配置GitHub Token。")
        else:
            self.log.warning("未找到GitHub Token。您的API请求将受到严格的速率限制。")

        url = 'https://api.github.com/rate_limit'
        try:
            r = await self.client.get(url, headers=headers)
            r.raise_for_status()
            rate_limit = r.json().get('resources', {}).get('core', {})
            remaining = rate_limit.get('remaining', 0)
            reset_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(rate_limit.get('reset', 0)))
            self.log.info(f'GitHub API剩余请求次数: {remaining}')

            if remaining == 0:
                self.log.error("GitHub API请求次数已用尽。")
                self.log.error(f"您的请求次数将于 {reset_time} 重置。")
                self.log.error("要提升请求上限，请在config.json文件中添加您的'Github_Personal_Token'。")
                return False
            return True
        except Exception as e:
            self.log.error(f'检查GitHub API速率限制失败: {self.stack_error(e)}')
            return False

    async def checkcn(self) -> bool:
        try:
            req = await self.client.get('https://mips.kugou.com/check/iscn?&format=json', timeout=5)
            body = req.json()
            is_cn = bool(body['flag'])
            os.environ['IS_CN'] = 'yes' if is_cn else 'no'
            if is_cn: self.log.info(f"检测到区域为中国大陆 ({body['country']})。将使用国内镜像。")
            else: self.log.info(f"检测到区域为非中国大陆 ({body['country']})。将直接使用GitHub。")
            return is_cn
        except Exception:
            os.environ['IS_CN'] = 'yes'
            self.log.warning('无法确定服务器位置，默认您在中国大陆。')
            return True

    def parse_lua_file_for_depots(self, lua_file_path: str) -> Dict:
        addappid_pattern = re.compile(r'addappid\((\d+),\s*1,\s*"([^"]+)"\)')
        depots = {}
        try:
            with open(lua_file_path, 'r', encoding='utf-8') as file:
                lua_content = file.read()
                for match in addappid_pattern.finditer(lua_content):
                    depots[match.group(1)] = {"DecryptionKey": match.group(2)}
        except Exception as e:
            self.log.error(f"解析lua文件 {lua_file_path} 出错: {e}")
        return depots

    async def depotkey_merge(self, config_path: Path, depots_config: dict) -> bool:
        if not config_path.exists():
            self.log.error('未找到Steam默认配置文件，您可能尚未登录。')
            return False
        try:
            async with aiofiles.open(config_path, encoding='utf-8') as f: content = await f.read()
            config_vdf = vdf.loads(content)
            steam = config_vdf.get('InstallConfigStore', {}).get('Software', {}).get('Valve') or \
                    config_vdf.get('InstallConfigStore', {}).get('Software', {}).get('valve')
            if steam is None:
                self.log.error('找不到Steam配置节。')
                return False
            depots = steam.setdefault('depots', {})
            depots.update(depots_config.get('depots', {}))
            async with aiofiles.open(config_path, mode='w', encoding='utf-8') as f:
                await f.write(vdf.dumps(config_vdf, pretty=True))
            self.log.info('成功将密钥合并到config.vdf。')
            return True
        except Exception as e:
            self.log.error(f'合并失败: {self.stack_error(e)}')
            return False

    async def _get_from_mirrors(self, sha: str, path: str, repo: str) -> bytes:
        urls = [f'https://raw.githubusercontent.com/{repo}/{sha}/{path}']
        if os.environ.get('IS_CN') == 'yes':
            urls = [
                f'https://cdn.jsdmirror.com/gh/{repo}@{sha}/{path}',
                f'https://raw.gitmirror.com/{repo}/{sha}/{path}',
                f'https://raw.dgithub.xyz/{repo}/{sha}/{path}',
                f'https://gh.akass.cn/{repo}/{sha}/{path}'
            ]
        for url in urls:
            try:
                r = await self.client.get(url, timeout=30)
                if r.status_code == 200:
                    self.log.info(f'下载成功: {path} (来自 {url.split("/")[2]})')
                    return r.content
                self.log.error(f'下载失败: {path} (来自 {url.split("/")[2]}) - 状态码: {r.status_code}')
            except httpx.RequestError as e:
                self.log.error(f'下载失败: {path} (来自 {url.split("/")[2]}) - 错误: {e}')
        raise Exception(f'尝试所有镜像后仍无法下载文件: {path}')

    async def greenluma_add(self, depot_id_list: list) -> bool:
        app_list_path = self.steam_path / 'AppList'
        try:
            app_list_path.mkdir(parents=True, exist_ok=True)
            for file in app_list_path.glob('*.txt'): file.unlink(missing_ok=True)
            depot_dict = {
                int(i.stem): int(i.read_text(encoding='utf-8').strip())
                for i in app_list_path.iterdir() if i.is_file() and i.stem.isdecimal() and i.suffix == '.txt'
            }
            for depot_id in map(int, depot_id_list):
                if depot_id not in depot_dict.values():
                    index = max(depot_dict.keys(), default=-1) + 1
                    (app_list_path / f'{index}.txt').write_text(str(depot_id), encoding='utf-8')
                    depot_dict[index] = depot_id
            return True
        except Exception as e:
            self.log.error(f'GreenLuma添加 AppID失败: {e}')
            return False

    # --- UPDATED: New safer DLC retrieval functions ---
    async def _http_get_safe(self, url: str) -> httpx.Response | None:
        """Safe HTTP GET with error handling"""
        try:
            response = await self.client.get(url, timeout=20)
            response.raise_for_status()
            return response
        except Exception as e:
            self.log.error(f"HTTP请求失败 {url}: {e}")
            return None

    async def _get_dlc_ids_safe(self, appid: str) -> List[str]:
        """Get DLC IDs with fallback mechanism - SteamCMD API first, then Steam Store API"""
        # 先尝试 SteamCMD API
        data = await self._http_get_safe(f"https://api.steamcmd.net/v1/info/{appid}")
        if data:
            try:
                j = data.json()
                info = j.get("data", {}).get(str(appid), {})
                dlc_str = info.get("extended", {}).get("listofdlc", "")
                if dlc_str:
                    dlc_ids = sorted(filter(str.isdigit, map(str.strip, dlc_str.split(","))), key=int)
                    if dlc_ids:
                        self.log.info(f"从 SteamCMD API 获取到 {len(dlc_ids)} 个DLC")
                        return dlc_ids
            except Exception as e:
                self.log.warning(f"解析 SteamCMD API 响应失败: {e}")
        
        # 降级：使用官方 Steam Store API
        data = await self._http_get_safe(f"https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese")
        if data:
            try:
                j = data.json()
                if j.get(str(appid), {}).get("success") and "data" in j[str(appid)]:
                    dlc_list = j[str(appid)]["data"].get("dlc", [])
                    dlc_ids = [str(d) for d in dlc_list]
                    if dlc_ids:
                        self.log.info(f"从 Steam Store API 获取到 {len(dlc_ids)} 个DLC")
                        return dlc_ids
            except Exception as e:
                self.log.warning(f"解析 Steam Store API 响应失败: {e}")
        
        self.log.warning(f"未能从任何API获取到 AppID {appid} 的DLC信息")
        return []

    async def _get_depots_safe(self, appid: str) -> List[Tuple[str, str, int, str]]:
        """Get depot information with fallback mechanism - returns (depot_id, manifest_id, size, source)"""
        # 先尝试 SteamCMD API
        data = await self._http_get_safe(f"https://api.steamcmd.net/v1/info/{appid}")
        if data:
            try:
                j = data.json()
                info = j.get("data", {}).get(str(appid), {})
                depots = info.get("depots", {})
                if depots:
                    out = []
                    for depot_id, depot_info in depots.items():
                        if not isinstance(depot_info, dict):
                            continue
                        manifest_info = depot_info.get("manifests", {}).get("public")
                        if not isinstance(manifest_info, dict):
                            continue
                        manifest_id = manifest_info.get("gid")
                        size = int(manifest_info.get("download", 0))
                        dlc_appid = depot_info.get("dlcappid")
                        source = f"DLC:{dlc_appid}" if dlc_appid else "主游戏"
                        if manifest_id:
                            out.append((depot_id, manifest_id, size, source))
                    if out:
                        self.log.info(f"从 SteamCMD API 获取到 {len(out)} 个Depot")
                        return out
            except Exception as e:
                self.log.warning(f"解析 SteamCMD API Depot 信息失败: {e}")
        
        # 降级：使用官方 Steam Store API
        data = await self._http_get_safe(f"https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese")
        if data:
            try:
                j = data.json()
                if j.get(str(appid), {}).get("success") and "data" in j[str(appid)]:
                    depots = j[str(appid)]["data"].get("depots", {})
                    out = []
                    for depot_id, depot_info in depots.items():
                        if not isinstance(depot_info, dict):
                            continue
                        manifest_info = depot_info.get("manifests", {}).get("public")
                        if not isinstance(manifest_info, dict):
                            continue
                        manifest_id = manifest_info.get("gid")
                        size = int(manifest_info.get("download", 0))
                        dlc_appid = depot_info.get("dlcappid")
                        source = f"DLC:{dlc_appid}" if dlc_appid else "主游戏"
                        if manifest_id:
                            out.append((depot_id, manifest_id, size, source))
                    if out:
                        self.log.info(f"从 Steam Store API 获取到 {len(out)} 个Depot")
                        return out
            except Exception as e:
                self.log.warning(f"解析 Steam Store API Depot 信息失败: {e}")
        
        self.log.warning(f"未能从任何API获取到 AppID {appid} 的Depot信息")
        return []

    # --- UPDATED: Use the new safer functions ---
    async def _get_steamcmd_api_data(self, appid: str) -> Dict:
        """Helper to fetch data from steamcmd.net API."""
        try:
            resp = await self.client.get(f"https://api.steamcmd.net/v1/info/{appid}", timeout=20)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.log.error(f"从 api.steamcmd.net 获取 AppID {appid} 数据失败: {e}")
            return {}

    async def _get_dlc_ids(self, appid: str) -> List[str]:
        """Gets all DLC IDs for a given AppID - UPDATED to use safer function"""
        return await self._get_dlc_ids_safe(appid)

    async def _get_depots(self, appid: str) -> List[Dict]:
        """Gets all depot information for a given AppID - UPDATED to use safer function and maintain compatibility"""
        depot_tuples = await self._get_depots_safe(appid)
        # Convert to the old format for compatibility with existing code
        depots = []
        for depot_id, manifest_id, size, source in depot_tuples:
            # Extract dlc_appid from source if it's a DLC
            dlc_appid = None
            if source.startswith("DLC:"):
                dlc_appid = source.split(":", 1)[1]
            
            depots.append({
                "depot_id": depot_id,
                "size": size,
                "dlc_appid": dlc_appid
            })
        return depots

    async def _add_free_dlcs_to_lua(self, app_id: str, lua_filepath: Path):
        """Finds all free/no-key DLCs that have NO depots and merges them into an existing LUA file, avoiding duplicates."""
        self.log.info(f"开始为 AppID {app_id} 查找无密钥/无Depot的DLC...")
        try:
            # 1. Get all potential DLC IDs for the main game
            all_dlc_ids = await self._get_dlc_ids(app_id)
            if not all_dlc_ids:
                self.log.info(f"AppID {app_id} 未找到任何DLC。")
                return

            # 2. Asynchronously check each DLC to see if it has ANY depots
            tasks = [self._get_depots(dlc_id) for dlc_id in all_dlc_ids]
            results = await asyncio.gather(*tasks)

            # 3. Filter for DLCs that have NO depots at all (stricter definition)
            depot_less_dlc_ids = []
            for dlc_id, dlc_depots in zip(all_dlc_ids, results):
                if not dlc_depots:
                    depot_less_dlc_ids.append(dlc_id)
            
            if not depot_less_dlc_ids:
                self.log.info(f"未找到适用于 AppID {app_id} 的无密钥/无Depot的DLC。")
                return

            # 4. Read the existing LUA file and perform intelligent merging to avoid duplicates
            async with self.lock:
                if not lua_filepath.exists():
                    self.log.error(f"目标LUA文件 {lua_filepath} 不存在，无法合并DLC。")
                    return

                # Read existing lines and extract all AppIDs already present
                async with aiofiles.open(lua_filepath, 'r', encoding='utf-8') as f:
                    existing_lines = [line.strip() for line in await f.readlines() if line.strip()]
                
                existing_appids = set()
                for line in existing_lines:
                    match = re.search(r'addappid\((\d+)', line)
                    if match:
                        existing_appids.add(match.group(1))

                # Find which of the depot-less DLCs are genuinely new
                new_dlcs_to_add = [dlc_id for dlc_id in depot_less_dlc_ids if dlc_id not in existing_appids]
                
                if not new_dlcs_to_add:
                    self.log.info(f"所有找到的无Depot DLC均已存在于解锁文件中。无需添加。")
                    return

                self.log.info(f"找到 {len(new_dlcs_to_add)} 个新的无密钥/无Depot DLC，正在合并到 LUA 文件...")

                # Add only the new, non-duplicate DLCs
                final_lines = set(existing_lines)
                for dlc_id in new_dlcs_to_add:
                    final_lines.add(f"addappid({dlc_id})")

                # Sort to maintain a clean structure (addappid first, then setManifestid)
                def sort_key(line):
                    match_add = re.search(r'addappid\((\d+)', line)
                    if match_add: return (0, int(match_add.group(1))) # Group 0, sort by ID
                    match_set = re.search(r'setManifestid\((\d+)', line)
                    if match_set: return (1, int(match_set.group(1))) # Group 1, sort by ID
                    return (2, line) # Other lines at the end
                
                sorted_lines = sorted(list(final_lines), key=sort_key)

                async with aiofiles.open(lua_filepath, 'w', encoding='utf-8') as f:
                    await f.write('\n'.join(sorted_lines) + '\n')
            
            self.log.info(f"成功将 {len(new_dlcs_to_add)} 个新的无密钥/无Depot DLC合并到 {lua_filepath.name}")

        except Exception as e:
            self.log.error(f"添加无密钥DLC时出错: {self.stack_error(e)}")

    # --- MODIFIED: Added patch_depot_key parameter to processing functions ---
    async def _process_zip_manifest_generic(self, app_id: str, download_url: str, source_name: str, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        zip_path = self.temp_path / f'{app_id}.zip'
        extract_path = self.temp_path / app_id
        try:
            self.temp_path.mkdir(exist_ok=True, parents=True)
            self.log.info(f'正从 {source_name} 下载 AppID {app_id} 的清单...')
            response = await self.client.get(download_url, timeout=60)
            if response.status_code != 200:
                self.log.error(f'从 {source_name} 下载失败，状态码: {response.status_code}')
                return False
            async with aiofiles.open(zip_path, 'wb') as f: await f.write(response.content)
            self.log.info('正在解压...')
            with zipfile.ZipFile(zip_path, 'r') as zip_ref: zip_ref.extractall(extract_path)

            st_files = list(extract_path.glob('*.st'))
            if st_files:
                st_converter = STConverter()
                for st_file in st_files:
                    try:
                        lua_content = st_converter.convert_file(str(st_file))
                        (st_file.with_suffix('.lua')).write_text(lua_content, encoding='utf-8')
                        self.log.info(f'已转换 {st_file.name} -> {st_file.with_suffix(".lua").name}')
                    except Exception as e:
                        self.log.error(f'转换 .st 文件 {st_file.name} 失败: {e}')

            manifest_files = list(extract_path.glob('*.manifest'))
            lua_files = list(extract_path.glob('*.lua'))

            is_auto_update_mode = self.is_steamtools() and self.use_st_auto_update

            if self.is_steamtools():
                stplug_path = self.steam_path / 'config' / 'stplug-in'
                stplug_path.mkdir(parents=True, exist_ok=True)
                
                if not is_auto_update_mode:
                    st_depot_path = self.steam_path / 'config' / 'depotcache'
                    gl_depot_path = self.steam_path / 'depotcache'
                    st_depot_path.mkdir(parents=True, exist_ok=True)
                    gl_depot_path.mkdir(parents=True, exist_ok=True)
                    if not manifest_files: self.log.warning(f"在来自 {source_name} 的压缩包中未找到 .manifest 文件。")
                    for f in manifest_files:
                        shutil.copy2(f, st_depot_path / f.name)
                        self.log.info(f'已复制清单到: {st_depot_path / f.name}')
                        shutil.copy2(f, gl_depot_path / f.name)
                        self.log.info(f'已同时复制清单到: {gl_depot_path / f.name}')
                else:
                    self.log.info('已启用SteamTools自动更新，跳过复制 .manifest 文件。')

                all_depots = {}
                for lua_f in lua_files:
                    depots = self.parse_lua_file_for_depots(str(lua_f))
                    all_depots.update(depots)

                lua_filename = f"{app_id}.lua"
                lua_filepath = stplug_path / lua_filename

                addappid_lines = [f'addappid({app_id})']
                for depot_id, info in all_depots.items():
                    key = info.get("DecryptionKey", "None")
                    if key.lower() == "none" or not key:
                        addappid_lines.append(f'addappid({depot_id})')
                    else:
                        addappid_lines.append(f'addappid({depot_id}, 1, "{key}")')
                
                setmanifestid_lines = []
                for manifest_f in manifest_files:
                    match = re.search(r'(\d+)_(\w+)\.manifest', manifest_f.name)
                    if match:
                        line = f'setManifestid({match.group(1)}, "{match.group(2)}")'
                        if is_auto_update_mode:
                            setmanifestid_lines.append('--' + line)
                        else:
                            setmanifestid_lines.append(line)

                async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                    await lua_file.write('\n'.join(addappid_lines) + '\n')
                    if setmanifestid_lines:
                        await lua_file.write('\n-- Manifests\n')
                        await lua_file.write('\n'.join(setmanifestid_lines) + '\n')
                
                self.log.info(f"已为SteamTools生成解锁文件: {lua_filename}")

                if add_all_dlc:
                    await self._add_free_dlcs_to_lua(app_id, lua_filepath)

                # NEW: Apply depotkey patch if requested
                if patch_depot_key:
                    self.log.info("开始修补创意工坊depotkey...")
                    await self.patch_lua_with_depotkey(app_id, lua_filepath)

            else: # GreenLuma 或其他
                if not manifest_files:
                    self.log.warning(f"在来自 {source_name} 的压缩包中未找到 .manifest 文件。")
                    return False

                self.log.info(f'为GreenLuma/标准模式处理来自 {source_name} 的文件。')
                steam_depot_path = self.steam_path / 'depotcache'
                steam_depot_path.mkdir(parents=True, exist_ok=True)
                for f in manifest_files: shutil.copy2(f, steam_depot_path / f.name); self.log.info(f'已复制清单: {f.name}')

                all_depots = {}
                for lua in lua_files:
                    depots = self.parse_lua_file_for_depots(str(lua))
                    all_depots.update(depots)
                if all_depots:
                    await self.depotkey_merge(self.steam_path / 'config' / 'config.vdf', {'depots': all_depots})

            self.log.info(f'成功处理来自 {source_name} 的清单。')
            return True
        except Exception as e:
            self.log.error(f'处理来自 {source_name} 的清单时出错: {self.stack_error(e)}')
            return False
        finally:
            if zip_path.exists(): zip_path.unlink()
            if extract_path.exists(): shutil.rmtree(extract_path)

    async def process_printedwaste_manifest(self, app_id: str, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        return await self._process_zip_manifest_generic(app_id, f'https://api.printedwaste.com/gfk/download/{app_id}', "SWA V2 (printedwaste)", add_all_dlc, patch_depot_key)

    async def process_cysaw_manifest(self, app_id: str, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        return await self._process_zip_manifest_generic(app_id, f'https://cysaw.top/uploads/{app_id}.zip', "Cysaw", add_all_dlc, patch_depot_key)

    async def process_furcate_manifest(self, app_id: str, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        return await self._process_zip_manifest_generic(app_id, f'https://furcate.eu/files/{app_id}.zip', "Furcate", add_all_dlc, patch_depot_key)

    async def process_assiw_manifest(self, app_id: str, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        return await self._process_zip_manifest_generic(app_id, f'https://assiw.cngames.site/qindan/{app_id}.zip', "CNGS (assiw)", add_all_dlc, patch_depot_key)

    async def process_steamdatabase_manifest(self, app_id: str, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        return await self._process_zip_manifest_generic(app_id, f'https://steamdatabase.s3.eu-north-1.amazonaws.com/{app_id}.zip', "SteamDatabase", add_all_dlc, patch_depot_key)

    async def process_steamautocracks_v2_manifest(self, app_id: str, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        """处理 SteamAutoCracks/ManifestHub(2) 清单库 - 使用 steamui API 获取 depot 和 manifest 信息"""
        try:
            self.log.info(f'正从 SteamAutoCracks/ManifestHub(2) 处理 AppID {app_id} 的清单...')
            
            # 1. 从 steamui API 获取 depot 和 manifest 信息
            depot_manifest_map = await self._get_depots_and_manifests_from_steamui(app_id)
            if not depot_manifest_map:
                self.log.error(f"未能从 steamui API 获取到 AppID {app_id} 的 depot 信息")
                return False
            
            self.log.info(f"从 steamui API 获取到 {len(depot_manifest_map)} 个 depot 及其 manifest")
            
            # 2. 下载 depotkeys.json（复用现有方法）
            if 'IS_CN' not in os.environ:
                self.log.info("检测网络环境以优化下载源选择...")
                await self.checkcn()
            
            depotkeys_data = await self.download_depotkeys_json()
            if not depotkeys_data:
                self.log.error("无法获取 depotkeys 数据")
                return False
            
            # 3. 匹配 depot 与 depotkey
            valid_depots = {}
            for depot_id in depot_manifest_map.keys():
                if depot_id in depotkeys_data:
                    depotkey = depotkeys_data[depot_id]
                    # 检查 depotkey 是否有效（不为空字符串）
                    if depotkey and str(depotkey).strip():
                        valid_depots[depot_id] = str(depotkey).strip()
                        self.log.info(f"找到 depot {depot_id} 的有效 depotkey: {depotkey}")
                    else:
                        self.log.warning(f"depot {depot_id} 的 depotkey 为空，自动跳过")
                else:
                    self.log.warning(f"未找到 depot {depot_id} 的 depotkey，自动跳过")
            
            if not valid_depots:
                self.log.warning(f"AppID {app_id} 没有找到任何有效的 depot 密钥")
                return False
            
            # 4. 根据解锁工具类型处理
            if self.is_steamtools():
                return await self._process_steamautocracks_v2_for_steamtools(app_id, valid_depots, depot_manifest_map, add_all_dlc, patch_depot_key, depotkeys_data)
            else:
                return await self._process_steamautocracks_v2_for_greenluma(app_id, valid_depots)
                
        except Exception as e:
            self.log.error(f'处理 SteamAutoCracks/ManifestHub(2) 清单时出错: {self.stack_error(e)}')
            return False

    async def _get_depots_and_manifests_from_steamui(self, app_id: str) -> Dict[str, str]:
        """从 steamui API 获取 depot 和对应的 manifest 信息"""
        try:
            url = f"https://steamui.com/api/get_appinfo.php?appid={app_id}"
            response = await self.client.get(url, timeout=20)
            response.raise_for_status()
            
            # steamui API 返回的是VDF格式，不是JSON格式
            vdf_content = response.text
            self.log.info(f"steamui API 原始响应内容预览: {vdf_content[:200]}...")
            
            # 使用VDF解析器解析内容
            import vdf
            data = vdf.loads(vdf_content)
            
            self.log.info(f"VDF解析后的数据结构键: {list(data.keys())}")
            
            depot_manifest_map = {}
            
            # 遍历所有键，找到数字格式的depot ID
            for key, value in data.items():
                # 检查是否是数字格式的 depot ID
                if key.isdigit() and isinstance(value, dict):
                    # 检查是否有 manifests 信息（确认是有效的 depot）
                    if 'manifests' in value and value['manifests']:
                        manifests = value['manifests']
                        if isinstance(manifests, dict) and 'public' in manifests:
                            public_manifest = manifests['public']
                            if isinstance(public_manifest, dict) and 'gid' in public_manifest:
                                manifest_id = public_manifest['gid']
                                depot_manifest_map[key] = manifest_id
                                self.log.info(f"发现有效 depot: {key}, manifest: {manifest_id}")
            
            if depot_manifest_map:
                self.log.info(f"总共找到 {len(depot_manifest_map)} 个有效的 depot 及其 manifest")
                return depot_manifest_map
            else:
                # 如果没有找到depot，尝试查找其他可能的结构
                self.log.warning("在根级别未找到depot，尝试查找嵌套结构...")
                
                # 检查是否有 'depots' 键（某些情况下可能存在）
                if 'depots' in data:
                    depots = data['depots']
                    for depot_id, depot_info in depots.items():
                        if depot_id.isdigit() and isinstance(depot_info, dict):
                            if 'manifests' in depot_info and depot_info['manifests']:
                                manifests = depot_info['manifests']
                                if isinstance(manifests, dict) and 'public' in manifests:
                                    public_manifest = manifests['public']
                                    if isinstance(public_manifest, dict) and 'gid' in public_manifest:
                                        manifest_id = public_manifest['gid']
                                        depot_manifest_map[depot_id] = manifest_id
                                        self.log.info(f"在depots键下发现有效 depot: {depot_id}, manifest: {manifest_id}")
                
                # 如果还是没找到，检查是否有应用信息的嵌套结构
                if not depot_manifest_map:
                    for key, value in data.items():
                        if isinstance(value, dict) and 'depots' in value:
                            depots = value['depots']
                            for depot_id, depot_info in depots.items():
                                if depot_id.isdigit() and isinstance(depot_info, dict):
                                    if 'manifests' in depot_info and depot_info['manifests']:
                                        manifests = depot_info['manifests']
                                        if isinstance(manifests, dict) and 'public' in manifests:
                                            public_manifest = manifests['public']
                                            if isinstance(public_manifest, dict) and 'gid' in public_manifest:
                                                manifest_id = public_manifest['gid']
                                                depot_manifest_map[depot_id] = manifest_id
                                                self.log.info(f"在嵌套depots键下发现有效 depot: {depot_id}, manifest: {manifest_id}")
                
                if not depot_manifest_map:
                    self.log.error(f"经过多种尝试后，仍未在steamui API响应中找到 AppID {app_id} 的depot信息")
                    self.log.error(f"VDF数据结构: {list(data.keys())}")
                    return {}
                
                return depot_manifest_map
            
        except vdf.VDFError as e:
            self.log.error(f"解析 steamui API VDF 响应失败: {e}")
            self.log.error(f"原始VDF内容: {vdf_content[:500]}...")
            return {}
        except Exception as e:
            self.log.error(f"从 steamui API 获取 depot 信息失败: {e}")
            return {}

    async def _process_steamautocracks_v2_for_steamtools(self, app_id: str, valid_depots: Dict[str, str], depot_manifest_map: Dict[str, str], add_all_dlc: bool, patch_depot_key: bool, depotkeys_data: Dict) -> bool:
        """为 SteamTools 处理 SteamAutoCracks/ManifestHub(2) 清单"""
        try:
            stplug_path = self.steam_path / 'config' / 'stplug-in'
            stplug_path.mkdir(parents=True, exist_ok=True)
            
            lua_filename = f"{app_id}.lua"
            lua_filepath = stplug_path / lua_filename
            
            # 检查是否启用了自动更新模式
            is_auto_update_mode = self.use_st_auto_update
            
            # 生成 lua 文件内容
            lines = []
            
            # 第一行：主游戏 appid
            lines.append(f'addappid({app_id})')
            
            # 添加所有有效的 depot 及其密钥
            for depot_id, depotkey in valid_depots.items():
                lines.append(f'addappid({depot_id}, 1, "{depotkey}")')
            
            # 添加 setManifestid 行（使用从 steamui API 获取的 manifest 信息）
            manifest_lines = []
            for depot_id in valid_depots.keys():
                if depot_id in depot_manifest_map:
                    manifest_id = depot_manifest_map[depot_id]
                    # 根据是否启用自动更新决定是否注释掉 manifest 行
                    if is_auto_update_mode:
                        # 自动更新模式：注释掉 setManifestid 行
                        manifest_lines.append(f'--setManifestid({depot_id}, "{manifest_id}")')
                        self.log.info(f"添加注释的 manifest 映射（自动更新模式）: depot {depot_id} -> manifest {manifest_id}")
                    else:
                        # 固定版本模式：正常添加 setManifestid 行
                        manifest_lines.append(f'setManifestid({depot_id}, "{manifest_id}")')
                        self.log.info(f"添加 manifest 映射（固定版本）: depot {depot_id} -> manifest {manifest_id}")
            
            # 写入文件
            async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                await lua_file.write('\n'.join(lines) + '\n')
                if manifest_lines:
                    await lua_file.write('\n-- Manifests\n')
                    await lua_file.write('\n'.join(manifest_lines) + '\n')
            
            self.log.info(f"已为SteamTools生成解锁文件: {lua_filename}")
            
            # 处理 DLC
            if add_all_dlc:
                await self._add_free_dlcs_to_lua(app_id, lua_filepath)
            
            # 处理创意工坊密钥修补（复用已下载的 depotkeys_data）
            if patch_depot_key:
                self.log.info("开始修补创意工坊depotkey...")
                await self._patch_lua_with_existing_depotkeys(app_id, lua_filepath, depotkeys_data)
            
            return True
            
        except Exception as e:
            self.log.error(f'为 SteamTools 处理 SteamAutoCracks/ManifestHub(2) 清单时出错: {e}')
            return False
            
    async def _process_steamautocracks_v2_for_greenluma(self, app_id: str, valid_depots: Dict[str, str]) -> bool:
        """为 GreenLuma 处理 SteamAutoCracks/ManifestHub(2) 清单"""
        try:
            # GreenLuma needs the depotkeys merged into config.vdf
            depots_config = {'depots': {depot_id: {"DecryptionKey": key} for depot_id, key in valid_depots.items()}}
            
            # Merge depotkeys
            config_vdf_path = self.steam_path / 'config' / 'config.vdf'
            if await self.depotkey_merge(config_vdf_path, depots_config):
                self.log.info("已将密钥合并到 config.vdf")
            
            # Add app IDs to GreenLuma
            gl_ids = list(valid_depots.keys())
            gl_ids.append(app_id)
            await self.greenluma_add(list(set(gl_ids)))
            self.log.info("已添加到 GreenLuma")
            
            return True
            
        except Exception as e:
            self.log.error(f'为 GreenLuma 处理 SteamAutoCracks/ManifestHub(2) 清单时出错: {e}')
            return False
        
    
    async def _patch_lua_with_existing_depotkeys(self, app_id: str, lua_file_path: Path, depotkeys_data: Dict) -> bool:
        """使用已有的 depotkeys 数据修补 LUA 文件（避免重复下载）"""
        try:
            # 检查 app_id 是否在 depotkeys 中
            if app_id not in depotkeys_data:
                self.log.warning(f"没有此AppID的depotkey: {app_id}")
                return False
            
            depotkey = depotkeys_data[app_id]
            
            # 检查 depotkey 是否有效
            if not depotkey or not str(depotkey).strip():
                self.log.warning(f"AppID {app_id} 的 depotkey 为空或无效，跳过修补: '{depotkey}'")
                return False
            
            depotkey = str(depotkey).strip()
            self.log.info(f"找到 AppID {app_id} 的有效 depotkey: {depotkey}")
            
            # 读取现有 LUA 文件
            if not lua_file_path.exists():
                self.log.error(f"LUA文件不存在: {lua_file_path}")
                return False
            
            async with aiofiles.open(lua_file_path, 'r', encoding='utf-8') as f:
                lua_content = await f.read()
            
            # 解析行
            lines = lua_content.strip().split('\n')
            new_lines = []
            app_id_line_removed = False
            
            # 移除现有的 addappid({app_id}) 行并添加带 depotkey 的新行
            for line in lines:
                line = line.strip()
                # 检查是否是需要替换的简单 addappid 行
                if line == f"addappid({app_id})":
                    # 替换为带 depotkey 的版本
                    new_lines.append(f'addappid({app_id},1,"{depotkey}")')
                    app_id_line_removed = True
                    self.log.info(f"已替换: addappid({app_id}) -> addappid({app_id},1,\"{depotkey}\")")
                else:
                    new_lines.append(line)
            
            # 如果没有找到简单的 addappid 行，添加 depotkey 版本
            if not app_id_line_removed:
                new_lines.append(f'addappid({app_id},1,"{depotkey}")')
                self.log.info(f"已添加新的 depotkey 条目: addappid({app_id},1,\"{depotkey}\")")
            
            # 写回文件
            async with aiofiles.open(lua_file_path, 'w', encoding='utf-8') as f:
                await f.write('\n'.join(new_lines) + '\n')
            
            self.log.info(f"成功修补 LUA 文件的 depotkey: {lua_file_path.name}")
            return True
            
        except Exception as e:
            self.log.error(f"修补 LUA depotkey 时出错: {self.stack_error(e)}")
            return False
    
    async def fetch_branch_info(self, url: str, headers: Dict) -> Dict | None:
        try:
            r = await self.client.get(url, headers=headers)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                self.log.error("GitHub API请求次数已用尽。")
            elif e.response.status_code != 404:
                self.log.error(f"从 {url} 获取信息失败: {self.stack_error(e)}")
            return None
        except Exception as e:
            self.log.error(f'从 {url} 获取信息时发生意外错误: {self.stack_error(e)}')
            return None

    # --- MODIFIED: Updated to use all github repos including custom ones ---
    async def search_all_repos_for_appid(self, app_id: str, repos: List[str] = None) -> List[Dict]:
        """Search for app_id in all GitHub repositories (builtin + custom)"""
        if repos is None:
            repos = self.get_all_github_repos()
        
        github_token = self.config.get("Github_Personal_Token", "")
        headers = {'Authorization': f'Bearer {github_token}'} if github_token else None
        tasks = [self._search_single_repo(app_id, repo, headers) for repo in repos]
        results = await asyncio.gather(*tasks)
        return [res for res in results if res]

    async def _search_single_repo(self, app_id: str, repo: str, headers: Dict) -> Dict | None:
        self.log.info(f"正在仓库 {repo} 中搜索 AppID: {app_id}")
        url = f'https://api.github.com/repos/{repo}/branches/{app_id}'
        r_json = await self.fetch_branch_info(url, headers)
        if r_json and 'commit' in r_json:
            tree_url = r_json['commit']['commit']['tree']['url']
            r2_json = await self.fetch_branch_info(tree_url, headers)
            if r2_json and 'tree' in r2_json:
                self.log.info(f"在 {repo} 中找到清单。")
                return {
                    'repo': repo, 'sha': r_json['commit']['sha'],
                    'tree': r2_json['tree'], 'update_date': r_json["commit"]["commit"]["author"]["date"]
                }
        return None

    async def process_github_manifest(self, app_id: str, repo: str, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        github_token = self.config.get("Github_Personal_Token", "")
        headers = {'Authorization': f'Bearer {github_token}'} if github_token else None

        url = f'https://api.github.com/repos/{repo}/branches/{app_id}'
        r_json = await self.fetch_branch_info(url, headers)
        if not (r_json and 'commit' in r_json):
            self.log.error(f'无法获取 {repo} 中 {app_id} 的分支信息。如果该清单在此仓库中不存在，这是正常现象。')
            return False

        sha = r_json['commit']['sha']
        tree_url = r_json['commit']['commit']['tree']['url']
        r2_json = await self.fetch_branch_info(tree_url, headers)
        if not (r2_json and 'tree' in r2_json):
            self.log.error(f'无法获取 {repo} 中 {app_id} 的文件列表。')
            return False

        all_files_in_tree = r2_json.get('tree', [])
        files_to_download = all_files_in_tree[:]

        is_auto_update_mode = self.is_steamtools() and self.use_st_auto_update

        if is_auto_update_mode:
            files_to_download = [item for item in all_files_in_tree if not item['path'].endswith('.manifest')]

        if not all_files_in_tree:
            self.log.warning(f"仓库 {repo} 的分支 {app_id} 为空。")
            return True

        try:
            if files_to_download:
                tasks = [self._get_from_mirrors(sha, item['path'], repo) for item in files_to_download]
                downloaded_contents = await asyncio.gather(*tasks)
                downloaded_files = {item['path']: content for item, content in zip(files_to_download, downloaded_contents)}
            else:
                downloaded_files = {}
        except Exception as e:
            self.log.error(f"下载文件失败，正在中止对 {app_id} 的处理: {e}")
            return False

        all_manifest_paths_in_tree = [item['path'] for item in all_files_in_tree if item['path'].endswith('.manifest')]
        downloaded_manifest_paths = [p for p in downloaded_files if p.endswith('.manifest')]
        key_vdf_path = next((p for p in downloaded_files if "key.vdf" in p.lower()), None)
        all_depots = {}
        if key_vdf_path:
            depots_config = vdf.loads(downloaded_files[key_vdf_path].decode('utf-8'))
            all_depots = depots_config.get('depots', {})

        if self.is_steamtools():
            stplug_path = self.steam_path / 'config' / 'stplug-in'
            stplug_path.mkdir(parents=True, exist_ok=True)

            if not is_auto_update_mode:
                if downloaded_manifest_paths:
                    st_depot_path = self.steam_path / 'config' / 'depotcache'
                    gl_depot_path = self.steam_path / 'depotcache'
                    st_depot_path.mkdir(parents=True, exist_ok=True)
                    gl_depot_path.mkdir(parents=True, exist_ok=True)
                    for path in downloaded_manifest_paths:
                        filename = Path(path).name
                        file_content = downloaded_files[path]
                        (st_depot_path / filename).write_bytes(file_content)
                        self.log.info(f"已为 SteamTools 保存清单到: {st_depot_path / filename}")
                        (gl_depot_path / filename).write_bytes(file_content)
                        self.log.info(f"已同时为 SteamTools 保存清单到: {gl_depot_path / filename}")

            await self.migrate(st_use=True)
            
            lua_filename = f"{app_id}.lua"
            lua_filepath = stplug_path / lua_filename

            addappid_lines = [f'addappid({app_id})']
            for depot_id, info in all_depots.items():
                key = info.get("DecryptionKey", "None")
                if key.lower() == "none" or not key:
                    addappid_lines.append(f'addappid({depot_id})')
                else:
                    addappid_lines.append(f'addappid({depot_id}, 1, "{key}")')
            
            setmanifestid_lines = []
            for manifest_file_path in all_manifest_paths_in_tree:
                match = re.search(r'(\d+)_(\w+)\.manifest', Path(manifest_file_path).name)
                if match:
                    line = f'setManifestid({match.group(1)}, "{match.group(2)}")'
                    if is_auto_update_mode:
                        setmanifestid_lines.append('--' + line)
                    else:
                        setmanifestid_lines.append(line)

            async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                await lua_file.write('\n'.join(addappid_lines) + '\n')
                if setmanifestid_lines:
                    await lua_file.write('\n-- Manifests\n')
                    await lua_file.write('\n'.join(setmanifestid_lines) + '\n')

            self.log.info(f"已为SteamTools生成解锁文件: {lua_filename}")
            
            if add_all_dlc:
                await self._add_free_dlcs_to_lua(app_id, lua_filepath)

            # NEW: Apply depotkey patch if requested
            if patch_depot_key:
                self.log.info("开始修补创意工坊depotkey...")
                await self.patch_lua_with_depotkey(app_id, lua_filepath)

        else: # GreenLuma
            if not downloaded_manifest_paths:
                self.log.error("GreenLuma模式需要 .manifest 文件，但未能找到。")
                return False

            depot_cache_path = self.steam_path / 'depotcache'
            depot_cache_path.mkdir(exist_ok=True)
            for path in downloaded_manifest_paths:
                filename = Path(path).name
                (depot_cache_path / filename).write_bytes(downloaded_files[path])
                self.log.info(f"已为 GreenLuma 保存清单: {filename}")

            await self.migrate(st_use=False)
            if all_depots:
                await self.depotkey_merge(self.steam_path / 'config' / 'config.vdf', {'depots': all_depots})
                gl_ids = list(all_depots.keys())
                gl_ids.append(app_id)
                await self.greenluma_add(list(set(gl_ids)))
                self.log.info("已合并密钥并添加到GreenLuma。")

        self.log.info(f'清单最后更新时间: {r_json["commit"]["commit"]["author"]["date"]}')
        return True

    def extract_app_id(self, user_input: str) -> str | None:
        match = re.search(r"/app/(\d+)", user_input) or re.search(r"steamdb\.info/app/(\d+)", user_input)
        if match: return match.group(1)
        return user_input if user_input.isdigit() else None

    async def find_appid_by_name(self, game_name: str) -> List[Dict]:
        try:
            r = await self.client.get(f'https://steamui.com/api/loadGames.php?page=1&search={game_name}&sort=update')
            r.raise_for_status()
            return r.json().get('games', [])
        except Exception as e:
            self.log.error(f"搜索游戏 '{game_name}' 时出错: {self.stack_error(e)}")
            return []

    async def cleanup_temp_files(self):
        try:
            if self.temp_path.exists():
                shutil.rmtree(self.temp_path)
                self.log.info('临时文件已清理。')
        except Exception as e:
            self.log.error(f'清理临时文件失败: {self.stack_error(e)}')

    async def migrate(self, st_use: bool):
        directory = self.steam_path / "config" / "stplug-in"
        if st_use and directory.exists():
            self.log.info('检测到SteamTools, 正在检查是否有旧文件需要迁移...')
            for file in directory.glob("Cai_unlock_*.lua"):
                new_filename = directory / file.name.replace("Cai_unlock_", "")
                try:
                    file.rename(new_filename)
                    self.log.info(f'已重命名: {file.name} -> {new_filename.name}')
                except Exception as e:
                    self.log.error(f'重命名失败 {file.name}: {e}')