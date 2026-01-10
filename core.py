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
from pathlib import Path
from PIL import Image

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

def create_profile(profile_name, window=None):
    """建立新 Profile"""
    profile_dir = get_profile_dir(profile_name)
    if profile_dir.exists():
        return False, "Profile 已存在"

    profile_dir.mkdir(parents=True)
    (profile_dir / "templates").mkdir()

    config = {
        "window": window or {"left": 0, "top": 0, "right": 400, "bottom": 800},
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
    """截取視窗區域"""
    screenshot = pyautogui.screenshot()
    screenshot_np = np.array(screenshot)

    left = window["left"] * scale
    top = window["top"] * scale
    right = window["right"] * scale
    bottom = window["bottom"] * scale

    cropped = screenshot_np[top:bottom, left:right]
    return cv2.cvtColor(cropped, cv2.COLOR_RGB2BGR)


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


def match_state(current_frame, templates, states, window, scale, threshold):
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
                frame_region = crop_region(current_frame, region, window, scale)
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


def click_at(x, y, delay_range):
    """點擊指定座標"""
    pyautogui.click(x, y)
    delay = random.uniform(delay_range[0], delay_range[1])
    time.sleep(delay)


def run_automation(profile_name, stop_event=None):
    """執行自動化（可在獨立進程中運行）"""
    settings = get_shared_settings()
    profile_config = get_profile_config(profile_name)
    states = get_merged_states(profile_name)

    window = profile_config["window"]
    scale = settings["scale"]
    threshold = settings["match_threshold"]
    interval = settings["loop_interval"]
    start_delay = settings.get("start_delay", 5)
    click_delay = settings["click_delay"]
    debug = settings.get("debug", False)

    print(f"\n=== Profile: {profile_name} ===")
    print("載入狀態模板...")
    templates = load_templates(profile_name, states, window, scale)

    if not templates:
        print("錯誤: 沒有可用的模板")
        return

    print(f"\n已載入 {len(templates)} 個狀態")
    print(f"閾值: {threshold} | 間隔: {interval}s | Debug: {debug}")
    print(f"\n{start_delay} 秒後開始運行...")
    print("按 Ctrl+C 停止\n")
    time.sleep(start_delay)

    print("開始監控...\n")

    try:
        while True:
            if stop_event and stop_event.is_set():
                break

            current_frame = capture_window(window, scale)
            state, confidence, all_scores = match_state(
                current_frame, templates, states, window, scale, threshold
            )

            if debug:
                scores_str = " | ".join([f"{k}: {v:.2f}" for k, v in all_scores.items()])
                print(f"[DEBUG] {scores_str}")

            if state:
                x, y = states[state]["click"]
                print(f">>> [{state}] {confidence:.2f} -> 點擊 ({x}, {y})")
                click_at(x, y, click_delay)

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n已停止運行")
