"""
核心模組：設定管理、狀態合併、自動化邏輯
"""

import pyautogui
import cv2
import numpy as np
import time
import random
import json
import os
import shutil
import ctypes
import subprocess
from pathlib import Path
from PIL import Image
import Quartz

BASE_DIR = Path(__file__).parent
SHARED_DIR = BASE_DIR / "shared"
PROFILES_DIR = BASE_DIR / "profiles"


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


def get_shared_states():
    """載入共用狀態"""
    return load_json(SHARED_DIR / "states.json")


def get_profile_list():
    """取得所有 Profile 名稱"""
    profiles = []
    if PROFILES_DIR.exists():
        for p in PROFILES_DIR.iterdir():
            if p.is_dir() and (p / "config.json").exists():
                profiles.append(p.name)
    return sorted(profiles)


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


def get_merged_states(profile_name):
    """
    合併狀態：shared + override + local
    返回: dict of states
    """
    shared_states = get_shared_states()
    profile_config = get_profile_config(profile_name)

    override_states = profile_config.get("override_states", {})
    local_states = profile_config.get("local_states", {})

    # 從 shared 開始
    merged = {}
    for name, config in shared_states.items():
        merged[name] = {**config, "_source": "shared"}

    # 套用 override
    for name, override in override_states.items():
        if name in merged:
            merged[name] = {**merged[name], **override, "_source": "shared"}

    # 加入 local
    for name, config in local_states.items():
        merged[name] = {**config, "_source": "local"}

    return merged


def get_template_path(state_name, profile_name):
    """
    取得模板路徑（先找 local，再找 shared）
    """
    local_path = get_profile_dir(profile_name) / "templates" / f"{state_name}.png"
    if local_path.exists():
        return local_path

    shared_path = SHARED_DIR / "templates" / f"{state_name}.png"
    if shared_path.exists():
        return shared_path

    return None


# ============ Profile 管理 ============

def create_profile(profile_name, window=None, reference_window=None):
    """建立新 Profile"""
    profile_dir = get_profile_dir(profile_name)
    if profile_dir.exists():
        return False, "Profile 已存在"

    profile_dir.mkdir(parents=True)
    (profile_dir / "templates").mkdir()

    default_window = {"left": 0, "top": 0, "right": 400, "bottom": 800}
    config = {
        "window": window or default_window,
        "reference_window": reference_window or window or default_window,
        "override_states": {},
        "local_states": {}
    }
    save_profile_config(profile_name, config)
    return True, "建立成功"


def delete_profile(profile_name):
    """刪除 Profile"""
    profile_dir = get_profile_dir(profile_name)
    if not profile_dir.exists():
        return False, "Profile 不存在"

    shutil.rmtree(profile_dir)
    return True, "刪除成功"


# ============ 視窗偵測 ============

def get_bluestacks_windows():
    """取得所有 BlueStacks 視窗位置（包含 window ID）"""
    windows = []
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID
    )

    for win in window_list:
        owner = win.get(Quartz.kCGWindowOwnerName, "")
        if owner == "BlueStacks":
            bounds = win.get("kCGWindowBounds", {})
            if bounds:
                windows.append({
                    "window_id": win.get(Quartz.kCGWindowNumber),
                    "title": win.get(Quartz.kCGWindowName, "BlueStacks"),
                    "left": int(bounds["X"]),
                    "top": int(bounds["Y"]),
                    "right": int(bounds["X"] + bounds["Width"]),
                    "bottom": int(bounds["Y"] + bounds["Height"])
                })

    return windows


def get_single_bluestacks_window():
    """取得單一 BlueStacks 視窗（如果只有一個，包含 window_id）"""
    windows = get_bluestacks_windows()
    if len(windows) == 1:
        w = windows[0]
        return {
            "window_id": w["window_id"],
            "left": w["left"],
            "top": w["top"],
            "right": w["right"],
            "bottom": w["bottom"]
        }
    return None


# ============ 狀態管理 ============

def add_state_to_shared(name, click, regions=None):
    """新增狀態到 shared"""
    states = get_shared_states()

    state_config = {"click": click}
    if regions:
        if len(regions) == 1:
            state_config["region"] = regions[0]
        else:
            state_config["regions"] = regions

    states[name] = state_config
    save_json(SHARED_DIR / "states.json", states)


def add_state_to_profile(profile_name, name, click, regions=None):
    """新增狀態到 Profile（local）"""
    config = get_profile_config(profile_name)

    state_config = {"click": click}
    if regions:
        if len(regions) == 1:
            state_config["region"] = regions[0]
        else:
            state_config["regions"] = regions

    config["local_states"][name] = state_config
    save_profile_config(profile_name, config)


def remove_state_from_shared(name):
    """從 shared 移除狀態"""
    states = get_shared_states()
    if name not in states:
        return False, "狀態不存在"

    del states[name]
    save_json(SHARED_DIR / "states.json", states)

    # 刪除模板
    template_path = SHARED_DIR / "templates" / f"{name}.png"
    if template_path.exists():
        os.remove(template_path)

    return True, "刪除成功"


def remove_state_from_profile(profile_name, name):
    """從 Profile 移除狀態（local 或 override）"""
    config = get_profile_config(profile_name)
    removed = False

    if name in config.get("local_states", {}):
        del config["local_states"][name]
        removed = True

        # 刪除本地模板
        template_path = get_profile_dir(profile_name) / "templates" / f"{name}.png"
        if template_path.exists():
            os.remove(template_path)

    if name in config.get("override_states", {}):
        del config["override_states"][name]
        removed = True

    if removed:
        save_profile_config(profile_name, config)
        return True, "刪除成功"

    return False, "狀態不存在於此 Profile"


def toggle_state_in_profile(profile_name, state_name, enabled):
    """在 Profile 中啟用/停用 shared 狀態"""
    config = get_profile_config(profile_name)

    if "override_states" not in config:
        config["override_states"] = {}

    if state_name not in config["override_states"]:
        config["override_states"][state_name] = {}

    config["override_states"][state_name]["enabled"] = enabled
    save_profile_config(profile_name, config)


# ============ 截圖與模板 ============

def capture_window(window, scale):
    """截取視窗區域（舊方法，截整個螢幕再裁切）"""
    screenshot = pyautogui.screenshot()
    screenshot_np = np.array(screenshot)

    left = window["left"] * scale
    top = window["top"] * scale
    right = window["right"] * scale
    bottom = window["bottom"] * scale

    cropped = screenshot_np[top:bottom, left:right]
    return cv2.cvtColor(cropped, cv2.COLOR_RGB2BGR)


def capture_window_by_id(window_id, window, scale):
    """
    使用 Quartz 直接截取特定視窗（即使被遮蓋也能截圖）

    Args:
        window_id: Quartz window ID
        window: 視窗邊界 dict (left, top, right, bottom)
        scale: Retina 縮放比例

    Returns:
        numpy array (BGR format for OpenCV)
    """
    # 計算截圖區域（相對於螢幕）
    region = Quartz.CGRectMake(
        window["left"],
        window["top"],
        window["right"] - window["left"],
        window["bottom"] - window["top"]
    )

    # 截取特定視窗的圖像
    # kCGWindowListOptionIncludingWindow: 只截取指定視窗
    # kCGWindowImageBoundsIgnoreFraming: 忽略視窗邊框，只截取內容
    image = Quartz.CGWindowListCreateImage(
        region,
        Quartz.kCGWindowListOptionIncludingWindow,
        window_id,
        Quartz.kCGWindowImageBoundsIgnoreFraming
    )

    if image is None:
        return None

    # 取得圖像尺寸
    width = Quartz.CGImageGetWidth(image)
    height = Quartz.CGImageGetHeight(image)

    if width == 0 or height == 0:
        return None

    # 建立 bitmap context 來取得像素資料
    bytes_per_row = width * 4
    color_space = Quartz.CGColorSpaceCreateDeviceRGB()

    # 分配記憶體
    buffer = ctypes.create_string_buffer(height * bytes_per_row)

    context = Quartz.CGBitmapContextCreate(
        buffer,
        width,
        height,
        8,  # bits per component
        bytes_per_row,
        color_space,
        Quartz.kCGImageAlphaPremultipliedFirst | Quartz.kCGBitmapByteOrder32Little
    )

    # 繪製圖像到 context
    Quartz.CGContextDrawImage(context, Quartz.CGRectMake(0, 0, width, height), image)

    # 轉換為 numpy array
    img_data = np.frombuffer(buffer, dtype=np.uint8)
    img_data = img_data.reshape((height, width, 4))

    # BGRA -> BGR (移除 alpha channel)
    bgr = img_data[:, :, :3]

    return bgr


def capture_and_save_template(name, window, scale, save_to_shared=True, profile_name=None):
    """截取並儲存模板"""
    screenshot = pyautogui.screenshot()
    screenshot_np = np.array(screenshot)

    left = window["left"] * scale
    top = window["top"] * scale
    right = window["right"] * scale
    bottom = window["bottom"] * scale

    cropped = screenshot_np[top:bottom, left:right]

    if save_to_shared:
        output_path = SHARED_DIR / "templates" / f"{name}.png"
    else:
        output_path = get_profile_dir(profile_name) / "templates" / f"{name}.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(cropped).save(output_path)
    return output_path


# ============ 自動化核心 ============

def get_regions(state_config):
    """取得狀態的所有區域"""
    if "regions" in state_config:
        return state_config["regions"]
    elif "region" in state_config:
        return [state_config["region"]]
    return []


def crop_region(img, region, window, scale):
    """從圖片裁切指定區域"""
    left = int((region[0] - window["left"]) * scale)
    top = int((region[1] - window["top"]) * scale)
    right = int((region[2] - window["left"]) * scale)
    bottom = int((region[3] - window["top"]) * scale)

    left = max(0, left)
    top = max(0, top)
    right = min(img.shape[1], right)
    bottom = min(img.shape[0], bottom)

    if right <= left or bottom <= top:
        return None

    return img[top:bottom, left:right]


def load_templates(profile_name, states, window, scale):
    """載入所有狀態模板"""
    templates = {}

    for state_name, state_config in states.items():
        if not state_config.get("enabled", True):
            print(f"  跳過: {state_name} (disabled)")
            continue

        path = get_template_path(state_name, profile_name)
        if not path:
            print(f"  缺少: {state_name}.png")
            continue

        img = cv2.imread(str(path))
        if img is None:
            print(f"  警告: 無法讀取 {path}")
            continue

        regions = get_regions(state_config)

        if regions:
            region_templates = []
            for i, region in enumerate(regions):
                cropped = crop_region(img, region, window, scale)
                if cropped is None:
                    print(f"  警告: {state_name} region[{i}] 無效")
                    continue
                region_templates.append(cropped)

            if not region_templates:
                print(f"  警告: {state_name} 沒有有效區域，跳過")
                continue

            templates[state_name] = region_templates
            source = state_config.get("_source", "unknown")
            print(f"  載入: {state_name} ({len(region_templates)} 個區域) [{source}]")
        else:
            templates[state_name] = [img]
            source = state_config.get("_source", "unknown")
            print(f"  載入: {state_name} (全畫面) [{source}]")

    return templates


def match_region(frame_region, template_region):
    """比對單一區域"""
    if frame_region.shape[:2] != template_region.shape[:2]:
        template_resized = cv2.resize(template_region, (frame_region.shape[1], frame_region.shape[0]))
    else:
        template_resized = template_region

    result = cv2.matchTemplate(frame_region, template_resized, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val


def match_state(current_frame, templates, states, window, scale, threshold, offset=(0, 0)):
    """比對當前畫面與所有模板"""
    best_match = None
    best_confidence = 0
    all_scores = {}
    offset_x, offset_y = offset

    for state_name, template_list in templates.items():
        state_config = states[state_name]

        if not state_config.get("enabled", True):
            continue

        regions = get_regions(state_config)
        region_scores = []

        if regions:
            for i, (region, template) in enumerate(zip(regions, template_list)):
                # 套用偏移到 region
                adjusted_region = [
                    region[0] + offset_x,
                    region[1] + offset_y,
                    region[2] + offset_x,
                    region[3] + offset_y
                ]
                frame_region = crop_region(current_frame, adjusted_region, window, scale)
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


# ============ ADB 點擊 ============

def adb_connect(host="localhost", port=5555):
    """連接 ADB"""
    addr = f"{host}:{port}"
    result = subprocess.run(
        ["adb", "connect", addr],
        capture_output=True, text=True
    )
    return "connected" in result.stdout.lower()


def adb_get_resolution(device="localhost:5555"):
    """取得 Android 解析度"""
    result = subprocess.run(
        ["adb", "-s", device, "shell", "wm", "size"],
        capture_output=True, text=True
    )
    # 輸出格式: "Physical size: 1920x1080" 或 "Physical size: 1080x1920"
    if result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            if "Physical size" in line:
                size_str = line.split(":")[-1].strip()
                w, h = map(int, size_str.split("x"))
                return w, h
    return None, None


def adb_tap(android_x, android_y, device="localhost:5555"):
    """ADB 點擊指定 Android 座標"""
    result = subprocess.run(
        ["adb", "-s", device, "shell", "input", "tap", str(android_x), str(android_y)],
        capture_output=True, text=True
    )
    return result.returncode == 0


def convert_to_android_coords(click_x, click_y, config_window, android_resolution):
    """
    將 macOS 螢幕座標轉換為 Android 座標

    Args:
        click_x, click_y: macOS 螢幕座標（原始錄製的點擊位置）
        config_window: 遊戲視窗區域 dict (left, top, right, bottom)
        android_resolution: (android_width, android_height)

    Returns:
        (android_x, android_y)
    """
    android_w, android_h = android_resolution

    # 計算相對於 config_window 的位置
    rel_x = click_x - config_window["left"]
    rel_y = click_y - config_window["top"]

    # config_window 尺寸
    win_w = config_window["right"] - config_window["left"]
    win_h = config_window["bottom"] - config_window["top"]

    # 轉換到 Android 座標
    android_x = int(rel_x * android_w / win_w)
    android_y = int(rel_y * android_h / win_h)

    return android_x, android_y


def click_at(x, y, delay_range):
    """點擊指定座標（使用 pyautogui）"""
    pyautogui.click(x, y)
    delay = random.uniform(delay_range[0], delay_range[1])
    time.sleep(delay)


def click_at_adb(click_x, click_y, config_window, android_resolution, delay_range, device="localhost:5555"):
    """點擊指定座標（使用 ADB）"""
    android_x, android_y = convert_to_android_coords(click_x, click_y, config_window, android_resolution)
    adb_tap(android_x, android_y, device)
    delay = random.uniform(delay_range[0], delay_range[1])
    time.sleep(delay)
    return android_x, android_y


def run_automation(profile_name, stop_event=None):
    """執行自動化（可在獨立進程中運行）"""
    settings = get_shared_settings()
    profile_config = get_profile_config(profile_name)
    states = get_merged_states(profile_name)

    # 載入視窗設定
    config_window = profile_config["window"]
    reference_window = profile_config.get("reference_window", config_window)

    # 嘗試自動偵測當前視窗位置
    detected = get_single_bluestacks_window()
    window_id = None
    if detected:
        current_window = detected
        window_id = detected.get("window_id")
        offset_x = current_window["left"] - reference_window["left"]
        offset_y = current_window["top"] - reference_window["top"]
        print(f"偵測到視窗位置: ({current_window['left']}, {current_window['top']})")
        if window_id:
            print(f"視窗 ID: {window_id} (支援背景截圖)")
        if offset_x != 0 or offset_y != 0:
            print(f"相對參考位置偏移: ({offset_x:+d}, {offset_y:+d})")
    else:
        current_window = config_window
        offset_x = 0
        offset_y = 0
        print("未偵測到視窗，使用設定值（不支援背景截圖）")

    # 嘗試連接 ADB
    use_adb = False
    android_resolution = None
    if adb_connect():
        android_w, android_h = adb_get_resolution()
        if android_w and android_h:
            # 確保是直向（高度 > 寬度）
            if android_h < android_w:
                android_w, android_h = android_h, android_w
            android_resolution = (android_w, android_h)
            use_adb = True
            print(f"ADB 已連接 (解析度: {android_w}x{android_h})，滑鼠不會被佔用")
        else:
            print("ADB 連接成功但無法取得解析度，使用 pyautogui")
    else:
        print("ADB 未連接，使用 pyautogui 點擊（滑鼠會被佔用）")

    # 計算截圖用的視窗區域（套用偏移到原本的 config_window）
    window = {
        "left": config_window["left"] + offset_x,
        "top": config_window["top"] + offset_y,
        "right": config_window["right"] + offset_x,
        "bottom": config_window["bottom"] + offset_y
    }

    scale = settings["scale"]
    threshold = settings["match_threshold"]
    short_interval = settings["loop_interval"]
    long_interval = settings.get("long_interval", 10.0)
    miss_threshold = settings.get("miss_threshold", 5)
    start_delay = settings.get("start_delay", 5)
    click_delay = settings["click_delay"]
    debug = settings.get("debug", False)

    print(f"\n=== Profile: {profile_name} ===")
    print("載入狀態模板...")
    # 模板是用原始 config_window 截的，所以用 config_window 載入
    templates = load_templates(profile_name, states, config_window, scale)

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

            # 優先使用視窗截圖（支援背景），否則用螢幕截圖
            if window_id:
                current_frame = capture_window_by_id(window_id, window, scale)
                if current_frame is None:
                    print("警告: 視窗截圖失敗，嘗試螢幕截圖")
                    current_frame = capture_window(window, scale)
            else:
                current_frame = capture_window(window, scale)

            state, confidence, all_scores = match_state(
                current_frame, templates, states, window, scale, threshold,
                offset=(offset_x, offset_y)
            )

            if debug:
                scores_str = " | ".join([f"{k}: {v:.2f}" for k, v in all_scores.items()])
                interval_mode = "長" if using_long_interval else "短"
                print(f"[DEBUG] [{interval_mode}] {scores_str}")

            if state:
                orig_x, orig_y = states[state]["click"]
                if use_adb:
                    android_x, android_y = click_at_adb(orig_x, orig_y, config_window, android_resolution, click_delay)
                    print(f">>> [{state}] {confidence:.2f} -> ADB 點擊 ({android_x}, {android_y})")
                else:
                    x, y = orig_x + offset_x, orig_y + offset_y
                    print(f">>> [{state}] {confidence:.2f} -> 點擊 ({x}, {y})")
                    click_at(x, y, click_delay)
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
