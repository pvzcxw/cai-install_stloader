import subprocess
import os
import zipfile
import requests
import winreg
import psutil
import shutil
import logging
from pathlib import Path
from tqdm import tqdm

# 配置文件路径
config_file = "config.txt"
steam_config_path = 'steam_config.vdf'
luapacka_url = ""#添加你的luapacka下载链接（其实无所谓）

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger("Cai Install")

def get_steamtools_path():
    """获取 SteamTools 的路径"""
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'].lower() == 'steamtools.exe':
                log.warning("检测到 steamtools 进程正在运行。")
                return proc.exe()
    except psutil.AccessDenied as e:
        log.error(f"无法访问进程信息: {e}")
    except Exception as e:
        log.error(f"检测 SteamTools 时出错: {e}")

def get_steam_path():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
        steam_path = Path(winreg.QueryValueEx(key, 'SteamPath')[0])
        return steam_path
    except Exception as e:
        log.error(f'Steam路径获取失败, {e}')
        return None

def detect_steamtools():
    steam_path = get_steam_path()
    if steam_path:
        isSteamTools = (Path(steam_path) / 'config' / 'stUI').is_dir()
        return isSteamTools, steam_path
    return False, None

def download_file(url, filename):
    """下载文件到指定路径并显示进度条"""
    try:
        response = requests.get(url, stream=True)
        if response.status_code != 200:
            log.error(f"下载失败，状态码: {response.status_code}")
            return False
        
        total_size = int(response.headers.get('content-length', 0))  # 获取文件总大小
        block_size = 1024  # 每次读取1KB

        with open(filename, 'wb') as file, tqdm(
                desc=filename,
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
        ) as bar:
            for data in response.iter_content(block_size):
                file.write(data)
                bar.update(len(data))
        log.info(f"文件 {filename} 已下载完成")
        return True
    except Exception as e:
        log.error(f"下载文件时出错: {e}")
        return False

def fetch_and_download(appid):
    """请求文件并下载"""
    try:
        verify_url = f''#添加清单库验证
        verify_response = requests.get(verify_url)
        if verify_response.status_code != 200:
            log.error(f"验证appid失败: {appid}")
            return False

        download_url = f''#添加清单库下载
        download_response = requests.get(download_url)
        if download_response.status_code != 200:
            log.error(f"获取下载链接失败: {appid}")
            return False

        json_data = download_response.json()
        file_url = json_data.get('url').strip()  # 清理多余空格
        if not file_url:
            log.error("响应中未找到下载URL。")
            return False

        filename = file_url.split('/')[-1]  # 提取文件名
        if not download_file(file_url, filename):
            return False

        log.info(f"准备解压文件: {filename}")
        if not extract_zip(filename, Path('extracted')):
            return False

        log.info("解压完成，继续处理文件")
        return True

    except Exception as e:
        log.error(f"处理下载或解压时发生错误: {e}")
        return False

def extract_zip(zip_path, extract_to):
    """解压缩 ZIP 文件到指定目录"""
    try:
        zip_path = Path(zip_path)
        extract_to = Path(extract_to)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        log.info(f"文件解压成功: {extract_to}")
        return True
    except zipfile.BadZipFile:
        log.error(f"解压文件时出错: {zip_path} 不是有效的 ZIP 文件")
    except Exception as e:
        log.error(f"解压文件时出错: {e}")
    return False

def ensure_luapacka(steam_path):
    """确保 luapacka.exe 存在，如果不存在则下载"""
    try:
        luapacka_path = Path(steam_path) / "config" / "stplug-in" / "luapacka.exe"
        
        if not luapacka_path.exists():
            log.warning(f'警告: {luapacka_path} 不存在!')
            luapacka_path.parent.mkdir(parents=True, exist_ok=True)
            if not download_file(luapacka_url, luapacka_path):
                return None
        return luapacka_path
    except Exception as e:
        log.error(f"处理 luapacka 时出错: {e}")
        return None

def copy_files_to_unlock(steam_path):
    extracted_path = './extracted'
    stplugin_path = Path(steam_path / 'config' / 'stplug-in')
    depotcache_path = Path(steam_path / 'depotcache')

    depotcache_path.mkdir(parents=True, exist_ok=True)

    for root, _, fnames in os.walk(extracted_path):
        for fname in sorted(fnames):
            fpath = os.path.join(root, fname)

            if fname.endswith('.lua') and stplugin_path.exists():
                shutil.copy(fpath, stplugin_path)
                log.info(f"{fname} 复制到 {stplugin_path} 完成")
            elif fname.endswith('.manifest'):
                shutil.copy(fpath, depotcache_path)
                log.info(f"{fname} 复制到 {depotcache_path} 完成")

    if stplugin_path.exists():
        luapacka_path = ensure_luapacka(steam_path)
        if not luapacka_path:
            return False
        for root, _, fnames in os.walk(stplugin_path):
            for fname in fnames:
                if fname.endswith('.lua'):
                    lua_file_path = os.path.join(root, fname)
                    subprocess.run([str(luapacka_path), lua_file_path])
                    os.remove(lua_file_path)
                    log.info(f"{lua_file_path} 已处理并删除")
    return True

def cleanup(app_id):
    """清理缓存"""
    if os.path.exists(f'./{app_id}.zip'):
        os.remove(f'./{app_id}.zip')
        log.info(f"已删除文件: {app_id}.zip")
    if os.path.exists('./extracted'):
        shutil.rmtree('./extracted')
        log.info(f"已删除文件夹: extracted")

def main():
    try:
        app_id = input("请输入APPID: ")

        isSteamTools, steam_path = detect_steamtools()
        
        if not steam_path:
            log.error("未找到 Steam 目录，请确保 Steam 已安装。")
            return

        if fetch_and_download(app_id):
            if isSteamTools:
                if copy_files_to_unlock(steam_path):
                    log.info("入库成功！")
                else:
                    log.error("文件处理失败")
            else:
                log.error("未检测到 SteamTools")
        cleanup(app_id)

    except Exception as e:
        log.error(f"程序执行中发生错误: {e}")
        cleanup(app_id)

    # 等待用户按任意键退出
    input("按任意键退出...")
if __name__ == "__main__":
    main()
