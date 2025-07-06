# --- START OF FILE backend.py ---

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
import ujson as json
import vdf
import zipfile
import shutil
import struct
import zlib
from pathlib import Path
from typing import Tuple, Any, Dict, List

# A silent, library-level logger for debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('CaiCoreBackend')

class STConverter:
    """Handles conversion of .st files to .lua files"""
    def convert_file(self, st_path: str) -> str:
        try:
            with open(st_path, 'rb') as stfile:
                content = stfile.read()

            header = content[:12]
            if len(header) < 12:
                raise ValueError("ST file header is too short.")

            xorkey, size, _ = struct.unpack('III', header)
            xorkey = (xorkey ^ 0xFFFEA4C8) & 0xFF

            encrypted_data = content[12:12+size]
            if len(encrypted_data) < size:
                raise ValueError("ST file data is incomplete.")

            data = bytearray(encrypted_data)
            for i in range(len(data)):
                data[i] ^= xorkey

            decompressed_data = zlib.decompress(data)
            return decompressed_data[512:].decode('utf-8')
        except Exception as e:
            log.error(f"Failed to convert ST file {st_path}: {e}")
            raise

class CaiCore:
    """
    The core backend logic for Cai Install.
    Handles all operations without direct user interaction.
    """
    DEFAULT_CONFIG = {
        "Github_Personal_Token": "",
        "Custom_Steam_Path": "",
        "QA1": "温馨提示: Github_Personal_Token-cixcode可在Github设置的最底下开发者选项找到, 详情看教程"
    }
    
    GITHUB_REPOS = [
        'Auiowu/ManifestAutoUpdate',
        'SteamAutoCracks/ManifestHub',
    ]

    def __init__(self):
        self.config = {}
        self.steam_path: Path = None
        self.isGreenLuma = False
        self.isSteamTools = False
        self.client = httpx.AsyncClient(verify=False, trust_env=True)
        self.st_converter = STConverter()
        self.temp_path = Path('./temp')

    async def initialize(self) -> Tuple[bool, str]:
        """Loads config and determines Steam environment. Returns (success, message)."""
        try:
            # Load Config
            if not os.path.exists('./config.json'):
                await self._gen_config_file()
                return False, "Configuration file created. Please fill it out and restart."
            
            async with aiofiles.open("./config.json", mode="r", encoding="utf-8") as f:
                self.config = json.loads(await f.read())

            # Get Steam Path
            custom_path = self.config.get("Custom_Steam_Path", "").strip()
            if custom_path:
                self.steam_path = Path(custom_path)
            else:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
                self.steam_path = Path(winreg.QueryValueEx(key, 'SteamPath')[0])

            if not self.steam_path or not self.steam_path.exists():
                 return False, "Could not find Steam path. Please set it in config.json."

            # Check for Unlockers
            self.isGreenLuma = any((self.steam_path / dll).exists() for dll in ['GreenLuma_2024_x86.dll', 'GreenLuma_2024_x64.dll', 'User32.dll'])
            self.isSteamTools = (self.steam_path / 'config' / 'stUI').is_dir()

            return True, f"Initialization successful. Steam found at: {self.steam_path}"

        except Exception as e:
            return False, f"Initialization failed: {self._stack_error(e)}"

    async def close(self):
        """Closes async resources like the HTTP client."""
        await self.client.aclose()
        await self._cleanup_temp_files()

    def _stack_error(self, exception: Exception) -> str:
        """ Formats an exception traceback into a string. """
        return ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))

    async def _gen_config_file(self):
        """Generates the default configuration file."""
        async with aiofiles.open("./config.json", mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(self.DEFAULT_CONFIG, indent=2, ensure_ascii=False))

    async def search_games_by_name(self, name: str) -> List[Dict]:
        """Searches for games on steamui.com and returns a list of results."""
        url = f'https://steamui.com/loadGames.php?search={name}'
        try:
            r = await self.client.get(url)
            r.raise_for_status()
            data = r.json()
            return data.get('games', [])
        except Exception as e:
            log.error(f"Error searching for game '{name}': {e}")
            return []

    async def check_github_api_rate_limit(self) -> Dict:
        """Checks and returns the GitHub API rate limit status."""
        token = self.config.get("Github_Personal_Token", "")
        headers = {'Authorization': f'Bearer {token}'} if token else None
        url = 'https://api.github.com/rate_limit'
        try:
            r = await self.client.get(url, headers=headers)
            r.raise_for_status()
            return r.json().get('rate', {})
        except Exception as e:
            log.error(f"Failed to check GitHub API rate limit: {e}")
            return {}

    # --- Installation Methods ---

    async def install_from_source(self, app_id: str, source: str) -> Tuple[bool, str]:
        """
        Master installer for non-GitHub sources.
        Returns (success, message).
        """
        source_map = {
            "SWA": self._process_printedwaste_manifest,
            "Cysaw": self._process_cysaw_manifest,
            "Furcate": self._process_furcate_manifest,
            "CNGS": self._process_assiw_manifest,
            "SteamDB": self._process_steamdatabase_manifest
        }
        if source in source_map:
            return await source_map[source](app_id)
        return False, f"Unknown source: {source}"
    
    async def install_from_github_repo(self, app_id: str, repo: str) -> Tuple[bool, str]:
        """Installs manifests for a given app_id from a specific GitHub repo."""
        token = self.config.get("Github_Personal_Token", "")
        headers = {'Authorization': f'Bearer {token}'} if token else None
        
        url = f'https://api.github.com/repos/{repo}/branches/{app_id}'
        try:
            branch_info = await self._fetch_json(url, headers)
            if not (branch_info and 'commit' in branch_info):
                return False, f"Could not find branch for app '{app_id}' in repo '{repo}'."

            sha = branch_info['commit']['sha']
            tree_url = branch_info['commit']['commit']['tree']['url']
            tree_info = await self._fetch_json(tree_url, headers)
            
            if not (tree_info and 'tree' in tree_info):
                return False, f"Could not fetch file tree for app '{app_id}'."

            # This is a key part: process all files for the app
            for item in tree_info['tree']:
                await self._get_and_place_manifest_file(sha, item['path'], repo, app_id)

            update_date = branch_info["commit"]["commit"]["author"]["date"]
            return True, f"Successfully installed from {repo}. Last update: {update_date}"

        except Exception as e:
            return False, f"Error during GitHub installation: {self._stack_error(e)}"


    # --- Internal Helper Methods for Installation ---

    async def _fetch_json(self, url: str, headers: Dict = None) -> Any:
        try:
            r = await self.client.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            log.error(f"HTTP Error fetching {url}: {e.response.status_code}")
        except Exception as e:
            log.error(f"Failed to fetch {url}: {e}")
        return None

    async def _download_zip_and_extract(self, url: str, app_id: str) -> Tuple[bool, Path]:
        """Downloads a zip file, extracts it, and returns the path to the extracted files."""
        zip_path = self.temp_path / f'{app_id}.zip'
        extract_path = self.temp_path / app_id
        
        try:
            self.temp_path.mkdir(exist_ok=True, parents=True)
            
            r = await self.client.get(url, timeout=120)
            if r.status_code != 200:
                log.error(f"Failed to download from {url}. Status: {r.status_code}")
                return False, None

            async with aiofiles.open(zip_path, 'wb') as f:
                await f.write(r.content)
            
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_path)
            
            return True, extract_path
        except Exception as e:
            log.error(f"Error in _download_zip_and_extract for {url}: {self._stack_error(e)}")
            return False, None

    async def _process_extracted_files(self, extract_path: Path) -> Tuple[bool, str]:
        """Generic handler for extracted manifest/lua files."""
        manifests = list(extract_path.glob('*.manifest'))
        luas = list(extract_path.glob('*.lua'))
        sts = list(extract_path.glob('*.st'))

        # Convert .st to .lua first
        for st_file in sts:
            try:
                lua_content = self.st_converter.convert_file(str(st_file))
                lua_path = st_file.with_suffix('.lua')
                async with aiofiles.open(lua_path, 'w', encoding='utf-8') as f:
                    await f.write(lua_content)
                luas.append(lua_path)
            except Exception as e:
                return False, f"Failed to convert {st_file.name}: {e}"

        if self.isSteamTools:
            dest_depot = self.steam_path / 'config' / 'depotcache'
            dest_lua = self.steam_path / 'config' / 'stplug-in'
        else: # Assumes GreenLuma or other
            dest_depot = self.steam_path / 'depotcache'
            dest_lua = None # GL uses vdf merge

        dest_depot.mkdir(parents=True, exist_ok=True)
        if dest_lua: dest_lua.mkdir(parents=True, exist_ok=True)

        for m_file in manifests:
            shutil.copy2(m_file, dest_depot / m_file.name)
        
        for l_file in luas:
            if self.isSteamTools:
                shutil.copy2(l_file, dest_lua / l_file.name)
            else:
                # GreenLuma: Merge keys into config.vdf
                depots, _ = self._parse_lua_file(str(l_file))
                if depots:
                    config_vdf_path = self.steam_path / 'config' / 'config.vdf'
                    await self._depotkey_merge(config_vdf_path, {'depots': depots})
        
        return True, "Files processed successfully."

    # --- Specific Source Processors ---

    async def _process_printedwaste_manifest(self, app_id: str) -> Tuple[bool, str]:
        url = f'https://api.printedwaste.com/gfk/download/{app_id}'
        success, extract_path = await self._download_zip_and_extract(url, app_id)
        if not success:
            return False, f"Failed to download/extract from PrintedWaste for {app_id}."
        return await self._process_extracted_files(extract_path)

    async def _process_cysaw_manifest(self, app_id: str) -> Tuple[bool, str]:
        url = f'https://cysaw.top/uploads/{app_id}.zip'
        success, extract_path = await self._download_zip_and_extract(url, app_id)
        if not success:
            return False, f"Failed to download/extract from Cysaw for {app_id}."
        return await self._process_extracted_files(extract_path)

    async def _process_furcate_manifest(self, app_id: str) -> Tuple[bool, str]:
        url = f'https://furcate.eu/files/{app_id}.zip'
        success, extract_path = await self._download_zip_and_extract(url, app_id)
        if not success:
            return False, f"Failed to download/extract from Furcate for {app_id}."
        return await self._process_extracted_files(extract_path)

    async def _process_assiw_manifest(self, app_id: str) -> Tuple[bool, str]:
        url = f'https://assiw.cngames.site/qindan/{app_id}.zip'
        success, extract_path = await self._download_zip_and_extract(url, app_id)
        if not success:
            return False, f"Failed to download/extract from CNGS for {app_id}."
        return await self._process_extracted_files(extract_path)

    async def _process_steamdatabase_manifest(self, app_id: str) -> Tuple[bool, str]:
        url = f'https://steamdatabase.s3.eu-north-1.amazonaws.com/{app_id}.zip'
        success, extract_path = await self._download_zip_and_extract(url, app_id)
        if not success:
            return False, f"Failed to download/extract from SteamDatabase for {app_id}."
        return await self._process_extracted_files(extract_path)

    # --- Low-level File Handlers ---

    async def _get_and_place_manifest_file(self, sha: str, path: str, repo: str, current_app_id: str):
        """Downloads a single file from GitHub and places it correctly."""
        content = await self._get_github_file_content(sha, path, repo)
        if not content:
            raise Exception(f"Failed to download {path} from {repo}")

        if path.endswith('.manifest'):
            paths = [
                self.steam_path / 'depotcache' / path,
                self.steam_path / 'config' / 'depotcache' / path
            ]
            for p in paths:
                p.parent.mkdir(exist_ok=True, parents=True)
                async with aiofiles.open(p, 'wb') as f: await f.write(content)
        
        elif path.endswith('.lua'):
            # Always place lua files in stplug-in for ST, GL will ignore them
            p = self.steam_path / 'config' / 'stplug-in' / path
            p.parent.mkdir(exist_ok=True, parents=True)
            async with aiofiles.open(p, 'wb') as f: await f.write(content)
            
        elif "key.vdf" in path.lower():
            depots_config = vdf.loads(content.decode('utf-8'))
            if self.isSteamTools:
                # Convert VDF to LUA for SteamTools
                lua_path = self.steam_path / 'config' / 'stplug-in' / f"{current_app_id}.lua"
                async with aiofiles.open(lua_path, 'w', encoding='utf-8') as f:
                    await f.write(f'addappid({current_app_id}, 1, "None")\n')
                    for depot_id, depot_info in depots_config.get('depots', {}).items():
                        await f.write(f'addappid({depot_id}, 1, "{depot_info["DecryptionKey"]}")\n')
            else:
                # Merge VDF for GreenLuma
                config_vdf_path = self.steam_path / 'config' / 'config.vdf'
                await self._depotkey_merge(config_vdf_path, depots_config)
    
    async def _get_github_file_content(self, sha: str, path: str, repo: str) -> bytes:
        """Gets raw file content from GitHub, trying multiple CDNs."""
        base_urls = [
            f'https://cdn.jsdmirror.com/gh/{repo}@{sha}',
            f'https://raw.gitmirror.com/{repo}/{sha}',
            f'https://raw.githubusercontent.com/{repo}/{sha}'
        ]
        for base in base_urls:
            try:
                r = await self.client.get(f"{base}/{path}", timeout=30)
                if r.status_code == 200:
                    return r.content
            except Exception:
                continue # Try next URL
        return None

    def _parse_lua_file(self, lua_path: str) -> Tuple[Dict, Dict]:
        """Parses a Lua file to extract depot keys and manifest IDs."""
        add_pattern = re.compile(r'addappid\((\d+),\s*1,\s*"([^"]+)"\)')
        set_pattern = re.compile(r'setManifestid\((\d+),\s*"([^"]+)"(?:,\s*\d+)?\)')
        depots, manifests = {}, {}
        with open(lua_path, 'r', encoding='utf-8') as f:
            content = f.read()
            for match in add_pattern.finditer(content):
                depots[match.group(1)] = {"DecryptionKey": match.group(2)}
            for match in set_pattern.finditer(content):
                manifests[match.group(1)] = match.group(2)
        return depots, manifests
    
    async def _depotkey_merge(self, config_path: Path, depots_to_add: dict):
        """Merges new depot keys into Steam's config.vdf."""
        if not config_path.exists(): return
        
        async with aiofiles.open(config_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        config_data = vdf.loads(content)
        
        # Navigate to the 'depots' section, creating it if necessary
        store = config_data.get('InstallConfigStore', {}).get('Software', {}).get('Valve') or \
                config_data.get('InstallConfigStore', {}).get('Software', {}).get('valve', {})
        
        depots_section = store.setdefault('depots', {})
        depots_section.update(depots_to_add.get('depots', {}))
        
        async with aiofiles.open(config_path, 'w', encoding='utf-8') as f:
            await f.write(vdf.dumps(config_data, pretty=True))

    async def _cleanup_temp_files(self):
        """Clean up temporary files and folders."""
        if self.temp_path.exists():
            shutil.rmtree(self.temp_path, ignore_errors=True)
