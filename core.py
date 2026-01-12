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
        # Windows: 優先用內嵌的 platform-tools
        bundled = get_base_dir() / "platform-tools" / "adb.exe"
        if bundled.exists():
            return str(bundled)

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

# 確保必要目錄存在
SHARED_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR.mkdir(parents=True, exist_ok=True)


# ============ 設定載入 ============

def load_json(path):
    """載入 JSON 檔案"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    """儲存 JSON 檔案"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_shared_settings():
    """載入共用設定"""
    return load_json(SHARED_DIR / "settings.json")


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
    try:
        result = subprocess.run(
            [ADB_PATH, "devices"],
            capture_output=True, text=True
        )
    except FileNotFoundError:
        return []  # ADB 不存在

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
    except FileNotFoundError:
        return False  # ADB 不存在


def adb_get_resolution(device="localhost:5555"):
    """取得 Android 解析度"""
    try:
        result = subprocess.run(
            [ADB_PATH, "-s", device, "shell", "wm", "size"],
            capture_output=True, text=True
        )
    except FileNotFoundError:
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
    except FileNotFoundError:
        return False


def adb_screenshot(device="localhost:5555"):
    """使用 ADB 截取 Android 畫面"""
    try:
        result = subprocess.run(
            [ADB_PATH, "-s", device, "exec-out", "screencap", "-p"],
            capture_output=True
        )
    except FileNotFoundError:
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


def adb_capture_touch(device="localhost:5555", timeout=30):
    """
    捕獲 ADB 觸摸位置（跨平台）
    返回 (x, y) Android 座標，或 None（如超時）
    """
    import re
    import threading
    import queue

    # 取得解析度
    width, height = adb_get_resolution(device)
    if not width or not height:
        return None

    # 確保是直向
    if height < width:
        width, height = height, width

    # BlueStacks Virtual Touch 最大值
    TOUCH_MAX = 32767

    # 啟動 getevent
    try:
        proc = subprocess.Popen(
            [ADB_PATH, "-s", device, "shell", "getevent", "-l", "/dev/input/event2"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except FileNotFoundError:
        return None

    result_queue = queue.Queue()

    def reader():
        touch_x = None
        touch_y = None
        try:
            for line in proc.stdout:
                if "ABS_MT_POSITION_X" in line:
                    match = re.search(r"ABS_MT_POSITION_X\s+([0-9a-fA-F]+)", line)
                    if match:
                        raw_x = int(match.group(1), 16)
                        touch_x = int(raw_x / TOUCH_MAX * width)

                elif "ABS_MT_POSITION_Y" in line:
                    match = re.search(r"ABS_MT_POSITION_Y\s+([0-9a-fA-F]+)", line)
                    if match:
                        raw_y = int(match.group(1), 16)
                        touch_y = int(raw_y / TOUCH_MAX * height)

                if touch_x is not None and touch_y is not None:
                    result_queue.put((touch_x, touch_y))
                    return
        except:
            pass

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    proc.terminate()
    proc.wait()

    try:
        return result_queue.get_nowait()
    except queue.Empty:
        return None


# ============ 圖片選擇 ============

def adb_select_point(img, title="選擇點擊位置"):
    """
    在圖片上選擇一個點
    img: 已截取的圖片
    返回 (x, y) 或 None
    """
    if img is None:
        return None

    h, w = img.shape[:2]
    # 縮放以適合螢幕 (最大 800 寬)
    scale = min(800 / w, 1.0)
    if scale < 1.0:
        display_img = cv2.resize(img, (int(w * scale), int(h * scale)))
    else:
        display_img = img.copy()

    selected = [None]

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            selected[0] = (x, y)

    window = f"{title} (點擊選擇, Enter 確認, ESC 取消)"
    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_mouse)

    while True:
        show = display_img.copy()
        if selected[0]:
            # 畫十字標記
            x, y = selected[0]
            cv2.line(show, (x - 15, y), (x + 15, y), (0, 255, 0), 2)
            cv2.line(show, (x, y - 15), (x, y + 15), (0, 255, 0), 2)
            cv2.circle(show, (x, y), 5, (0, 255, 0), -1)
            # 顯示座標
            orig_x, orig_y = int(x / scale), int(y / scale)
            cv2.putText(show, f"({orig_x}, {orig_y})", (x + 10, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        cv2.imshow(window, show)
        key = cv2.waitKey(30) & 0xFF

        if key == 27:  # ESC
            cv2.destroyAllWindows()
            cv2.waitKey(1)
            return None
        elif key == 13 and selected[0]:  # Enter
            cv2.destroyAllWindows()
            cv2.waitKey(1)
            x, y = selected[0]
            return (int(x / scale), int(y / scale))


def adb_select_region(img, title="選擇區域"):
    """
    在圖片上拖曳選擇區域
    img: 已截取的圖片
    返回 (left, top, right, bottom) 或 None
    """
    if img is None:
        return None

    h, w = img.shape[:2]
    scale = min(800 / w, 1.0)
    if scale < 1.0:
        display_img = cv2.resize(img, (int(w * scale), int(h * scale)))
    else:
        display_img = img.copy()

    state = {"start": None, "end": None, "dragging": False}

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state["start"] = (x, y)
            state["end"] = (x, y)
            state["dragging"] = True
        elif event == cv2.EVENT_MOUSEMOVE and state["dragging"]:
            state["end"] = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            state["end"] = (x, y)
            state["dragging"] = False

    window = f"{title} (拖曳選擇, Enter 確認, ESC 取消)"
    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_mouse)

    while True:
        show = display_img.copy()
        if state["start"] and state["end"]:
            x1, y1 = state["start"]
            x2, y2 = state["end"]
            cv2.rectangle(show, (x1, y1), (x2, y2), (0, 255, 0), 2)
            # 顯示區域尺寸
            orig_region = [
                int(min(x1, x2) / scale), int(min(y1, y2) / scale),
                int(max(x1, x2) / scale), int(max(y1, y2) / scale)
            ]
            info = f"{orig_region[2]-orig_region[0]}x{orig_region[3]-orig_region[1]}"
            cv2.putText(show, info, (min(x1, x2), min(y1, y2) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        cv2.imshow(window, show)
        key = cv2.waitKey(30) & 0xFF

        if key == 27:  # ESC
            cv2.destroyAllWindows()
            cv2.waitKey(1)
            return None
        elif key == 13 and state["start"] and state["end"]:  # Enter
            cv2.destroyAllWindows()
            cv2.waitKey(1)
            x1, y1 = state["start"]
            x2, y2 = state["end"]
            return (
                int(min(x1, x2) / scale), int(min(y1, y2) / scale),
                int(max(x1, x2) / scale), int(max(y1, y2) / scale)
            )


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
    if frame_region.shape[:2] != template_region.shape[:2]:
        template_resized = cv2.resize(template_region, (frame_region.shape[1], frame_region.shape[0]))
    else:
        template_resized = template_region

    result = cv2.matchTemplate(frame_region, template_resized, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val


def load_templates(profile_name, states):
    """載入所有狀態模板"""
    templates = {}

    for state_name, state_config in states.items():
        if not state_config.get("enabled", True):
            print(f"  跳過: {state_name} (disabled)")
            continue

        path = get_template_path(state_name, profile_name)
        if not path.exists():
            print(f"  缺少: {state_name}.png")
            continue

        img = imread_safe(path)
        if img is None:
            print(f"  警告: 無法讀取 {path}")
            continue

        regions = get_regions(state_config)

        if regions:
            region_templates = []
            for i, region in enumerate(regions):
                cropped = crop_region(img, region)
                if cropped is None:
                    print(f"  警告: {state_name} region[{i}] 無效")
                    continue
                region_templates.append(cropped)

            if not region_templates:
                print(f"  警告: {state_name} 沒有有效區域，跳過")
                continue

            templates[state_name] = region_templates
            print(f"  載入: {state_name} ({len(region_templates)} 個區域)")
        else:
            templates[state_name] = [img]
            print(f"  載入: {state_name} (全畫面)")

    return templates


def match_state(current_frame, templates, states, threshold):
    """比對當前畫面與所有模板"""
    best_match = None
    best_confidence = 0
    all_scores = {}

    for state_name, template_list in templates.items():
        state_config = states[state_name]

        if not state_config.get("enabled", True):
            continue

        regions = get_regions(state_config)
        region_scores = []

        if regions:
            for i, (region, template) in enumerate(zip(regions, template_list)):
                frame_region = crop_region(current_frame, region)
                if frame_region is None:
                    region_scores.append(0)
                    continue
                score = match_region(frame_region, template)
                region_scores.append(score)
        else:
            score = match_region(current_frame, template_list[0])
            region_scores.append(score)

        min_score = min(region_scores) if region_scores else 0
        all_scores[state_name] = min_score

        if min_score >= threshold and min_score > best_confidence:
            best_confidence = min_score
            best_match = state_name

    return best_match, best_confidence, all_scores


# ============ 自動化核心 ============

def run_automation(profile_name, stop_event=None):
    """執行自動化"""
    settings = get_shared_settings()
    states = get_states(profile_name)

    if not states:
        print("錯誤: 此 Profile 沒有任何狀態")
        return

    # 連接 ADB
    if not adb_connect():
        print("錯誤: 無法連接 ADB")
        print("請確認 BlueStacks 已開啟且 ADB 已啟用")
        return

    android_w, android_h = adb_get_resolution()
    if not android_w or not android_h:
        print("錯誤: 無法取得 Android 解析度")
        return

    # 確保是直向
    if android_h < android_w:
        android_w, android_h = android_h, android_w

    # 驗證解析度
    expected_res = settings.get("resolution", [1080, 1920])
    if [android_w, android_h] != expected_res:
        print(f"警告: 解析度不符！")
        print(f"  設定: {expected_res[0]}x{expected_res[1]}")
        print(f"  實際: {android_w}x{android_h}")
        print("模板和座標可能不正確，請調整 BlueStacks 解析度或重新錄製")
        return

    print(f"ADB 已連接 (解析度: {android_w}x{android_h})")

    threshold = settings["match_threshold"]
    short_interval = settings["loop_interval"]
    long_interval = settings.get("long_interval", 10.0)
    miss_threshold = settings.get("miss_threshold", 5)
    start_delay = settings.get("start_delay", 5)
    click_delay = settings["click_delay"]
    debug = settings.get("debug", False)

    print(f"\n=== Profile: {profile_name} ===")
    print("載入狀態模板...")

    templates = load_templates(profile_name, states)

    if not templates:
        print("錯誤: 沒有可用的模板")
        return

    print(f"\n已載入 {len(templates)} 個狀態")
    print(f"閾值: {threshold} | 短間隔: {short_interval}s | 長間隔: {long_interval}s | Debug: {debug}")
    print(f"\n{start_delay} 秒後開始運行...")
    print("按 Ctrl+C 停止\n")
    time.sleep(start_delay)

    print("開始監控...\n")

    consecutive_misses = 0
    using_long_interval = False

    try:
        while True:
            if stop_event and stop_event.is_set():
                break

            current_frame = adb_screenshot()
            if current_frame is None:
                print("警告: ADB 截圖失敗")
                time.sleep(short_interval)
                continue

            state, confidence, all_scores = match_state(
                current_frame, templates, states, threshold
            )

            if debug:
                scores_str = " | ".join([f"{k}: {v:.2f}" for k, v in all_scores.items()])
                interval_mode = "長" if using_long_interval else "短"
                print(f"[DEBUG] [{interval_mode}] {scores_str}")

            if state:
                click_x, click_y = states[state]["click"]
                adb_tap(click_x, click_y)
                delay = random.uniform(click_delay[0], click_delay[1])
                time.sleep(delay)
                print(f">>> [{state}] {confidence:.2f} -> 點擊 ({click_x}, {click_y})")

                consecutive_misses = 0
                if using_long_interval:
                    using_long_interval = False
                    print("切換到短間隔模式")
            else:
                consecutive_misses += 1
                if not using_long_interval and consecutive_misses >= miss_threshold:
                    using_long_interval = True
                    print(f"連續 {miss_threshold} 次未命中，切換到長間隔模式")

            current_interval = long_interval if using_long_interval else short_interval
            time.sleep(current_interval)

    except KeyboardInterrupt:
        print("\n\n已停止運行")
