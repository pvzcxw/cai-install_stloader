# --- START OF FILE backend.py (UPDATED DLC RETRIEVAL FUNCTIONS) ---

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
import zipfile
import shutil
import struct
import zlib
import io  # Added for ZIP handling
from pathlib import Path
from typing import Tuple, Any, List, Dict, Literal

# --- LOGGING SETUP ---
LOG_FORMAT = '%(log_color)s%(message)s'
LOG_COLORS = {
    'INFO': 'cyan',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'purple',
}

# --- DEFAULT CONFIG ---
# --- MODIFIED: Added Force_Unlocker setting ---
DEFAULT_CONFIG = {
    "Github_Personal_Token": "",
    "Custom_Steam_Path": "",
    "Force_Unlocker": "",
    "QA1": "温馨提示: Github_Personal_Token(个人访问令牌)可在Github设置的最底下开发者选项中找到, 详情请看教程。",
    "QA2": "Force_Unlocker: 强制指定解锁工具, 填入 'steamtools' 或 'greenluma'。留空则自动检测。"
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

    # --- START OF WORKSHOP FUNCTIONALITY (FIXED) ---

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

    async def _download_and_place_workshop_manifest(self, depot_id: str, manifest_id: str) -> bool:
        """下载清单文件并放置到正确的文件夹 - 使用修复版本的逻辑"""
        output_filename = f"{depot_id}_{manifest_id}.manifest"
        self.log.info(f"准备下载清单: {output_filename}")

        # FIXED: 使用修复版本中确认有效的URL源，并优先使用（两个源貌似不可使用）
        urls = f"https://steamcontent.tnkjmec.com/depot/{depot_id}/manifest/{manifest_id}/5"   # 修复版本中确认的有效源

        
        manifest_content = None
        for url in urls:
            try:
                self.log.info(f"尝试从 {url.split('/')[2]} 下载...")
                response = await self.client.get(url, timeout=60)
                if response.status_code == 200:
                    # FIXED: 应用修复版本的ZIP处理逻辑
                    raw_content = response.content
                    
                    # 检查是否为ZIP文件
                    zip_in_memory = io.BytesIO(raw_content)
                    if zipfile.is_zipfile(zip_in_memory):
                        self.log.info("检测到ZIP文件，正在智能提取...")
                        try:
                            with zipfile.ZipFile(zip_in_memory, 'r') as zip_ref:
                                # 获取ZIP包内所有文件的列表
                                file_list = zip_ref.namelist()
                                
                                # 验证包内是否有且仅有一个文件
                                if len(file_list) != 1:
                                    self.log.error(f"ZIP包中的文件数量不是1 (实际为: {len(file_list)})，尝试下一个源...")
                                    self.log.warning(f"包内文件列表: {file_list}")
                                    continue

                                # 如果只有一个文件，就认为它是目标清单，无论它叫什么名字
                                filename_inside_zip = file_list[0]
                                self.log.info(f"成功锁定ZIP包内唯一文件: '{filename_inside_zip}'")
                                
                                # 读取这个文件的二进制内容作为清单内容
                                manifest_content = zip_ref.read(filename_inside_zip)
                    else:
                        # 如果不是ZIP文件，直接使用原始内容
                        manifest_content = raw_content
                    
                    if manifest_content:
                        self.log.info(f'下载成功: {output_filename} (来自 {url.split("/")[2]})')
                        break
                else:
                    self.log.warning(f'下载失败 (状态码: {response.status_code})')
            except httpx.RequestError as e:
                self.log.warning(f'下载失败 (错误: {e})')
            except Exception as e:
                self.log.warning(f'处理下载时出错: {e}')
        
        if not manifest_content:
            self.log.error(f"尝试所有下载方式后，仍无法下载清单 {output_filename}。")
            return False

        try:
            # 目标文件夹
            st_depot_path = self.steam_path / 'config' / 'depotcache'
            gl_depot_path = self.steam_path / 'depotcache'
            
            # 创建文件夹（如果不存在）
            st_depot_path.mkdir(parents=True, exist_ok=True)
            gl_depot_path.mkdir(parents=True, exist_ok=True)

            # 写入文件到两个位置
            (st_depot_path / output_filename).write_bytes(manifest_content)
            self.log.info(f"清单已保存到: {st_depot_path / output_filename}")
            
            (gl_depot_path / output_filename).write_bytes(manifest_content)
            self.log.info(f"清单已保存到: {gl_depot_path / output_filename}")
            
            self.log.info(f"成功处理创意工坊清单 {output_filename}。")
            return True
        except Exception as e:
            self.log.error(f"保存清单文件时出错: {self.stack_error(e)}")
            return False
        
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
            self.log.error(f'GreenLuma添加AppID失败: {e}')
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

    async def search_all_repos_for_appid(self, app_id: str, repos: List[str]) -> List[Dict]:
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

# --- END OF FILE backend.py (UPDATED DLC RETRIEVAL FUNCTIONS) ---
