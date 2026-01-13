"""
核心模組：設定管理、狀態管理、自動化邏輯
純 ADB 模式 - 跨平台支援
"""

import cv2
import numpy as np
import time
import random
import json
import os
import sys
import shutil
import subprocess
from pathlib import Path


# ============ 跨平台支援 ============

def get_base_dir():
    """取得程式根目錄（支援 PyInstaller）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包後
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_data_dir():
    """取得資料目錄（跨平台，確保有寫入權限）"""
    if sys.platform == "win32":
        # Windows: %APPDATA%\sbss
        appdata = os.environ.get("APPDATA")
        if appdata:
            data_dir = Path(appdata) / "sbss"
        else:
            # 備選：使用程式目錄
            data_dir = get_base_dir()
    else:
        # Mac/Linux: 保持原樣（程式目錄）
        data_dir = get_base_dir()

    # 確保目錄存在
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_adb_path():
    """取得 ADB 執行檔路徑（跨平台）"""
    if sys.platform == "win32":
        base = get_base_dir()

        # Windows: 檢查多個可能的內嵌位置
        candidates = [
            # 開發環境: 專案根目錄下
            base / "platform-tools" / "adb.exe",
            # Electron 打包: resources/platform-tools (web.py 在 resources/app)
            base.parent / "platform-tools" / "adb.exe",
        ]

        for p in candidates:
            if p.exists():
                return str(p)

        # 其次檢查常見安裝位置
        common_paths = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe",
            Path("C:/Android/platform-tools/adb.exe"),
            Path("C:/Program Files/Android/android-sdk/platform-tools/adb.exe"),
        ]
        for p in common_paths:
            if p.exists():
                return str(p)

    # Mac/Linux 或 Windows 無內嵌時：用系統 PATH
    return "adb"


def imread_safe(path):
    """安全讀取圖片（支援中文路徑）"""
    path_str = str(path)

    if sys.platform == "win32":
        # Windows 中文路徑：用二進位讀取 + imdecode
        try:
            with open(path, 'rb') as f:
                img_bytes = f.read()
            img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
            return img
        except Exception:
            return None
    else:
        # Mac/Linux：直接使用 imread
        return cv2.imread(path_str)


def imwrite_safe(path, img):
    """安全寫入圖片（支援中文路徑）"""
    path_str = str(path)

    if sys.platform == "win32":
        # Windows 中文路徑：用 imencode + 二進位寫入
        try:
            success, buffer = cv2.imencode('.png', img)
            if success:
                with open(path, 'wb') as f:
                    f.write(buffer.tobytes())
                return True
            return False
        except Exception:
            return False
    else:
        # Mac/Linux：直接使用 imwrite
        return cv2.imwrite(path_str, img)


BASE_DIR = get_base_dir()
DATA_DIR = get_data_dir()
SHARED_DIR = DATA_DIR / "shared"
PROFILES_DIR = DATA_DIR / "profiles"
ADB_PATH = get_adb_path()
# ADB 日誌放在資料目錄（確保有寫入權限）
ADB_LOG_PATH = DATA_DIR / "adb.log"

# 確保必要目錄存在
SHARED_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR.mkdir(parents=True, exist_ok=True)

def adb_log(msg):
    """寫入 ADB 除錯日誌"""
    import time as _time
    timestamp = _time.strftime("%H:%M:%S")
    with open(ADB_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {msg}\n")


# ============ 設定載入 ============

def load_json(path, default=None):
    """載入 JSON 檔案，檔案不存在時返回預設值"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else {}


def save_json(path, data):
    """儲存 JSON 檔案"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


DEFAULT_SETTINGS = {
    "match_threshold": 0.8,
    "loop_interval": 0.5,
    "long_interval": 5,
    "miss_threshold": 5,
    "start_delay": 2,
    "click_delay": [0.2, 1.2],
    "debug": False
}

def get_shared_settings():
    """載入共用設定，不存在時返回預設值"""
    settings = load_json(SHARED_DIR / "settings.json", DEFAULT_SETTINGS.copy())
    # 確保所有欄位都存在
    for key, value in DEFAULT_SETTINGS.items():
        if key not in settings:
            settings[key] = value
    return settings


def get_profile_list():
    """取得所有 Profile 名稱（按建立時間排序，舊的在前）"""
    profiles = []
    if PROFILES_DIR.exists():
        for p in PROFILES_DIR.iterdir():
            if p.is_dir() and (p / "config.json").exists():
                config = load_json(p / "config.json")
                created_at = config.get("created_at", 0)
                profiles.append((created_at, p.name))
    profiles.sort(key=lambda x: x[0])  # 按時間排序
    return [name for _, name in profiles]


def get_profile_dir(profile_name):
    """取得 Profile 目錄"""
    return PROFILES_DIR / profile_name


def get_profile_config(profile_name):
    """載入 Profile 設定"""
    config_path = get_profile_dir(profile_name) / "config.json"
    return load_json(config_path)


def save_profile_config(profile_name, config):
    """儲存 Profile 設定"""
    config_path = get_profile_dir(profile_name) / "config.json"
    save_json(config_path, config)


def get_states(profile_name):
    """取得 Profile 的所有狀態"""
    config = get_profile_config(profile_name)
    return config.get("states", {})


def get_template_path(state_name, profile_name):
    """取得模板路徑"""
    return get_profile_dir(profile_name) / "templates" / f"{state_name}.png"


# ============ Profile 管理 ============

def create_profile(profile_name):
    """建立新 Profile"""
    profile_dir = get_profile_dir(profile_name)
    if profile_dir.exists():
        return False, "Profile 已存在"

    profile_dir.mkdir(parents=True)
    (profile_dir / "templates").mkdir()

    config = {"states": {}, "created_at": time.time()}
    save_profile_config(profile_name, config)
    return True, "建立成功"


def delete_profile(profile_name):
    """刪除 Profile"""
    profile_dir = get_profile_dir(profile_name)
    if not profile_dir.exists():
        return False, "Profile 不存在"

    shutil.rmtree(profile_dir)
    return True, "刪除成功"


def clone_profile(source_name, target_name):
    """複製 Profile（包含所有 templates）"""
    source_dir = get_profile_dir(source_name)
    target_dir = get_profile_dir(target_name)

    if not source_dir.exists():
        return False, "來源 Profile 不存在"
    if target_dir.exists():
        return False, "目標 Profile 已存在"

    shutil.copytree(source_dir, target_dir)

    # 更新 created_at 讓新腳本排在最後
    config = get_profile_config(target_name)
    config["created_at"] = time.time()
    save_profile_config(target_name, config)

    return True, "複製成功"


def rename_profile(old_name, new_name):
    """重新命名 Profile"""
    if old_name == new_name:
        return True, "名稱相同"

    old_dir = get_profile_dir(old_name)
    new_dir = get_profile_dir(new_name)

    if not old_dir.exists():
        return False, "Profile 不存在"
    if new_dir.exists():
        return False, "新名稱已存在"

    old_dir.rename(new_dir)
    return True, "改名成功"


# ============ 狀態管理 ============

def add_state(profile_name, name, click, regions=None):
    """新增狀態"""
    config = get_profile_config(profile_name)
    if "states" not in config:
        config["states"] = {}

    state_config = {"click": click, "enabled": True}
    if regions:
        if len(regions) == 1:
            state_config["region"] = regions[0]
        else:
            state_config["regions"] = regions

    config["states"][name] = state_config
    save_profile_config(profile_name, config)


def remove_state(profile_name, name):
    """刪除狀態"""
    config = get_profile_config(profile_name)
    if name not in config.get("states", {}):
        return False, "狀態不存在"

    del config["states"][name]
    save_profile_config(profile_name, config)

    # 刪除模板
    template_path = get_template_path(name, profile_name)
    if template_path.exists():
        os.remove(template_path)

    return True, "刪除成功"


def toggle_state(profile_name, state_name, enabled):
    """啟用/停用狀態"""
    config = get_profile_config(profile_name)
    if state_name in config.get("states", {}):
        config["states"][state_name]["enabled"] = enabled
        save_profile_config(profile_name, config)


def move_state(profile_name, state_name, direction):
    """
    移動狀態順序
    direction: -1 上移, 1 下移
    """
    config = get_profile_config(profile_name)
    states = config.get("states", {})
    keys = list(states.keys())

    if state_name not in keys:
        return False

    idx = keys.index(state_name)
    new_idx = idx + direction

    if new_idx < 0 or new_idx >= len(keys):
        return False

    # 交換位置
    keys[idx], keys[new_idx] = keys[new_idx], keys[idx]

    # 重建 dict
    config["states"] = {k: states[k] for k in keys}
    save_profile_config(profile_name, config)
    return True


# ============ ADB 功能 ============

def adb_list_devices():
    """
    列出所有已連接的 ADB 設備
    返回 [{"id": "localhost:5555", "name": "emulator-5554 (localhost:5555)"}, ...]
    """
    adb_log(f"adb_list_devices: ADB_PATH={ADB_PATH}")
    try:
        result = subprocess.run(
            [ADB_PATH, "devices"],
            capture_output=True, text=True
        )
        adb_log(f"adb_list_devices: returncode={result.returncode}, stdout={result.stdout[:200] if result.stdout else 'None'}")
    except FileNotFoundError as e:
        adb_log(f"adb_list_devices: FileNotFoundError - {e}")
        return []  # ADB 不存在
    except Exception as e:
        adb_log(f"adb_list_devices: Exception - {e}")
        return []

    raw_devices = []
    for line in result.stdout.strip().split("\n")[1:]:  # 跳過標題行
        if "\t" in line:
            device_id, status = line.split("\t")
            if status == "device":
                raw_devices.append(device_id)

    # 整理設備列表
    devices = []
    seen_ports = set()

    # 先處理 emulator-xxxx 格式
    for dev in raw_devices:
        if dev.startswith("emulator-"):
            try:
                emu_port = int(dev.split("-")[1])
                adb_port = emu_port + 1  # emulator-5554 → localhost:5555
                device_id = f"localhost:{adb_port}"
                devices.append({
                    "id": device_id,
                    "name": f"{dev} (localhost:{adb_port})"
                })
                seen_ports.add(adb_port)
            except (ValueError, IndexError):
                pass

    # 再處理 localhost:xxxx 格式（避免重複）
    for dev in raw_devices:
        if ":" in dev:
            try:
                port = int(dev.split(":")[1])
                if port not in seen_ports:
                    devices.append({
                        "id": dev,
                        "name": dev
                    })
            except (ValueError, IndexError):
                devices.append({"id": dev, "name": dev})

    return devices


def adb_connect(host="localhost", port=5555):
    """連接 ADB"""
    addr = f"{host}:{port}"
    try:
        result = subprocess.run(
            [ADB_PATH, "connect", addr],
            capture_output=True, text=True
        )
        return "connected" in result.stdout.lower()
    except FileNotFoundError as e:
        adb_log(f"adb_connect({addr}): FileNotFoundError - {e}")
        return False
    except Exception as e:
        adb_log(f"adb_connect({addr}): Exception - {e}")
        return False


def adb_get_resolution(device="localhost:5555"):
    """取得 Android 解析度"""
    try:
        result = subprocess.run(
            [ADB_PATH, "-s", device, "shell", "wm", "size"],
            capture_output=True, text=True
        )
    except FileNotFoundError as e:
        adb_log(f"adb_get_resolution({device}): FileNotFoundError - {e}")
        return None, None
    except Exception as e:
        adb_log(f"adb_get_resolution({device}): Exception - {e}")
        return None, None
    if result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            if "Physical size" in line:
                size_str = line.split(":")[-1].strip()
                w, h = map(int, size_str.split("x"))
                return w, h
    return None, None


def adb_tap(x, y, device="localhost:5555"):
    """ADB 點擊指定座標"""
    try:
        result = subprocess.run(
            [ADB_PATH, "-s", device, "shell", "input", "tap", str(x), str(y)],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except FileNotFoundError as e:
        adb_log(f"adb_tap({x},{y},{device}): FileNotFoundError - {e}")
        return False
    except Exception as e:
        adb_log(f"adb_tap({x},{y},{device}): Exception - {e}")
        return False


def adb_screenshot(device="localhost:5555"):
    """使用 ADB 截取 Android 畫面"""
    try:
        result = subprocess.run(
            [ADB_PATH, "-s", device, "exec-out", "screencap", "-p"],
            capture_output=True
        )
    except FileNotFoundError as e:
        adb_log(f"adb_screenshot({device}): FileNotFoundError - {e}")
        return None
    except Exception as e:
        adb_log(f"adb_screenshot({device}): Exception - {e}")
        return None
    if result.returncode != 0 or not result.stdout:
        return None

    img_array = np.frombuffer(result.stdout, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    return img


def adb_save_template(name, profile_name, device="localhost:5555"):
    """使用 ADB 截圖並儲存模板"""
    img = adb_screenshot(device)
    if img is None:
        return None

    output_path = get_template_path(name, profile_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    imwrite_safe(output_path, img)
    return output_path




# ============ 模板比對 ============

def get_regions(state_config):
    """取得狀態的所有區域"""
    if "regions" in state_config:
        return state_config["regions"]
    elif "region" in state_config:
        return [state_config["region"]]
    return []


def crop_region(img, region):
    """從圖片裁切指定區域"""
    left, top, right, bottom = region
    left = max(0, left)
    top = max(0, top)
    right = min(img.shape[1], right)
    bottom = min(img.shape[0], bottom)

    if right <= left or bottom <= top:
        return None

    return img[top:bottom, left:right]


def match_region(frame_region, template_region):
    """比對單一區域"""
    if frame_region is None or template_region is None:
        return 0
    if frame_region.shape[:2] != template_region.shape[:2]:
        template_resized = cv2.resize(template_region, (frame_region.shape[1], frame_region.shape[0]))
    else:
        template_resized = template_region

    result = cv2.matchTemplate(frame_region, template_resized, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val
