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
DEFAULT_CONFIG = {
    "Github_Personal_Token": "",
    "Custom_Steam_Path": "",
    "QA1": "温馨提示: Github_Personal_Token(个人访问令牌)可在Github设置的最底下开发者选项中找到, 详情请看教程。"
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
        self.client = httpx.AsyncClient(verify=False, trust_env=True)
        self.config = {}
        self.steam_path = None
        self.unlocker_type = None 
        self.use_st_auto_update = False
        self.st_lock_manifest_version = False
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

    async def initialize(self) -> Literal["steamtools", "greenluma", "conflict", "none", None]:
        self.config = await self.load_config()
        if self.config is None:
            return None

        self.steam_path = self.get_steam_path()
        if not self.steam_path or not self.steam_path.exists():
            self.log.error('无法确定有效的Steam路径。正在退出。')
            return None
        
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
                return json.loads(await f.read())
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

    async def _process_zip_manifest_generic(self, app_id: str, download_url: str, source_name: str) -> bool:
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
            is_floating_version_mode = is_auto_update_mode and not self.st_lock_manifest_version

            if self.is_steamtools():
                stplug_path = self.steam_path / 'config' / 'stplug-in'
                stplug_path.mkdir(parents=True, exist_ok=True)

                if not is_auto_update_mode: # 传统模式: 复制清单
                    steam_depot_path = self.steam_path / 'config' / 'depotcache'
                    steam_depot_path.mkdir(parents=True, exist_ok=True)
                    if not manifest_files: self.log.warning(f"在来自 {source_name} 的压缩包中未找到 .manifest 文件。")
                    for f in manifest_files: 
                        shutil.copy2(f, steam_depot_path / f.name)
                        self.log.info(f'已复制清单: {f.name}')
                else: # 自动更新模式 (固定/浮动): 不复制清单
                    self.log.info('已启用SteamTools自动更新，跳过复制 .manifest 文件。')
                
                # --- REFACTORED LOGIC START ---
                # 1. 聚合所有depot key
                all_depots = {}
                for lua_f in lua_files:
                    depots = self.parse_lua_file_for_depots(str(lua_f))
                    all_depots.update(depots)

                # 2. 从零生成新的lua文件
                lua_filename = f"{app_id}.lua"
                lua_filepath = stplug_path / lua_filename
                async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                    await lua_file.write(f'addappid({app_id}, 1, "None")\n')
                    for depot_id, info in all_depots.items():
                        await lua_file.write(f'addappid({depot_id}, 1, "{info["DecryptionKey"]}")\n')

                    # 3. 写入版本信息 (setManifestid)
                    for manifest_f in manifest_files:
                        match = re.search(r'(\d+)_(\w+)\.manifest', manifest_f.name)
                        if match:
                            line = f'setManifestid({match.group(1)}, "{match.group(2)}")\n'
                            if is_floating_version_mode:
                                await lua_file.write('--' + line)
                            else: # 传统模式和固定版本模式
                                await lua_file.write(line)
                self.log.info(f"已为SteamTools生成解锁文件: {lua_filename}")
                # --- REFACTORED LOGIC END ---

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

    async def process_printedwaste_manifest(self, app_id: str) -> bool:
        return await self._process_zip_manifest_generic(app_id, f'https://api.printedwaste.com/gfk/download/{app_id}', "SWA V2 (printedwaste)")

    async def process_cysaw_manifest(self, app_id: str) -> bool:
        return await self._process_zip_manifest_generic(app_id, f'https://cysaw.top/uploads/{app_id}.zip', "Cysaw")
        
    async def process_furcate_manifest(self, app_id: str) -> bool:
        return await self._process_zip_manifest_generic(app_id, f'https://furcate.eu/files/{app_id}.zip', "Furcate")

    async def process_assiw_manifest(self, app_id: str) -> bool:
        return await self._process_zip_manifest_generic(app_id, f'https://assiw.cngames.site/qindan/{app_id}.zip', "CNGS (assiw)")
        
    async def process_steamdatabase_manifest(self, app_id: str) -> bool:
        return await self._process_zip_manifest_generic(app_id, f'https://steamdatabase.s3.eu-north-1.amazonaws.com/{app_id}.zip', "SteamDatabase")

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

    async def process_github_manifest(self, app_id: str, repo: str) -> bool:
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
        is_floating_version_mode = is_auto_update_mode and not self.st_lock_manifest_version

        if is_auto_update_mode:
            # 在任何自动更新模式下，都不下载 .manifest 文件
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
        downloaded_manifest_paths = [p for p in downloaded_files if p.endswith('.manifest')] # 只有在传统模式下才有内容
        key_vdf_path = next((p for p in downloaded_files if "key.vdf" in p.lower()), None)
        all_depots = {}
        if key_vdf_path:
            depots_config = vdf.loads(downloaded_files[key_vdf_path].decode('utf-8'))
            all_depots = depots_config.get('depots', {})

        if self.is_steamtools():
            stplug_path = self.steam_path / 'config' / 'stplug-in'
            stplug_path.mkdir(parents=True, exist_ok=True)

            if not is_auto_update_mode: # 传统模式: 复制清单文件
                if downloaded_manifest_paths:
                    config_depot_cache_path = self.steam_path / 'config' / 'depotcache'
                    config_depot_cache_path.mkdir(parents=True, exist_ok=True)
                    for path in downloaded_manifest_paths:
                        filename = Path(path).name
                        (config_depot_cache_path / filename).write_bytes(downloaded_files[path])
                        self.log.info(f"已为 SteamTools 保存清单: {filename}")

            await self.migrate(st_use=True)
            lua_filename = f"{app_id}.lua"
            lua_filepath = stplug_path / lua_filename
            async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                await lua_file.write(f'addappid({app_id}, 1, "None")\n')
                for depot_id, info in all_depots.items():
                    await lua_file.write(f'addappid({depot_id}, 1, "{info["DecryptionKey"]}")\n')
                
                for manifest_file_path in all_manifest_paths_in_tree:
                    match = re.search(r'(\d+)_(\w+)\.manifest', Path(manifest_file_path).name)
                    if match:
                        line = f'setManifestid({match.group(1)}, "{match.group(2)}")\n'
                        if is_floating_version_mode:
                            await lua_file.write('--' + line)
                        else: # 传统模式和固定版本模式
                            await lua_file.write(line)

            self.log.info(f"已为SteamTools生成解锁文件: {app_id}")
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