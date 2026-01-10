"""
BlueStacks 放置手遊自動化腳本
用途：自動完成結算與配對流程
設定：編輯 config.json
"""

import pyautogui
import cv2
import numpy as np
import time
import random
import json
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "config.json"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def load_config():
    """載入設定檔"""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_regions(state_config):
    """取得狀態的所有區域（兼容 region 和 regions）"""
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


def load_templates(states, window, scale):
    """載入所有狀態模板（只載入 enabled 的）"""
    templates = {}

    for state_name, state_config in states.items():
        if not state_config.get("enabled", True):
            print(f"  跳過: {state_name} (disabled)")
            continue

        path = TEMPLATES_DIR / f"{state_name}.png"
        if not path.exists():
            print(f"  缺少: {state_name}.png")
            continue

        img = cv2.imread(str(path))
        if img is None:
            print(f"  警告: 無法讀取 {path}")
            continue

        regions = get_regions(state_config)

        if regions:
            # 多區域模式：儲存每個區域的裁切
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
            print(f"  載入: {state_name} ({len(region_templates)} 個區域)")
        else:
            # 全畫面模式：儲存為單元素列表
            templates[state_name] = [img]
            print(f"  載入: {state_name} (全畫面, {img.shape[1]}x{img.shape[0]})")

    return templates


def capture_window(window, scale):
    """截取 BlueStacks 視窗區域"""
    screenshot = pyautogui.screenshot()
    screenshot_np = np.array(screenshot)

    left = window["left"] * scale
    top = window["top"] * scale
    right = window["right"] * scale
    bottom = window["bottom"] * scale

    cropped = screenshot_np[top:bottom, left:right]
    return cv2.cvtColor(cropped, cv2.COLOR_RGB2BGR)


def match_region(frame_region, template_region):
    """比對單一區域，返回相似度"""
    if frame_region.shape[:2] != template_region.shape[:2]:
        template_resized = cv2.resize(template_region, (frame_region.shape[1], frame_region.shape[0]))
    else:
        template_resized = template_region

    result = cv2.matchTemplate(frame_region, template_resized, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val


def match_state(current_frame, templates, states, window, scale, threshold):
    """
    比對當前畫面與所有模板
    多區域模式：所有區域都要達到閾值才算匹配，分數取最低
    返回: (state_name, confidence, all_scores)
    """
    best_match = None
    best_confidence = 0
    all_scores = {}

    for state_name, template_list in templates.items():
        state_config = states[state_name]

        if not state_config.get("enabled", True):
            continue

        regions = get_regions(state_config)

        # 計算每個區域的匹配分數
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
            # 全畫面模式
            score = match_region(current_frame, template_list[0])
            region_scores.append(score)

        # 取最低分作為該狀態的分數（所有區域都要匹配）
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


def main():
    print("=== BlueStacks 自動化腳本 ===\n")

    config = load_config()
    window = config["window"]
    scale = config["scale"]
    states = config["states"]
    threshold = config["match_threshold"]
    interval = config["loop_interval"]
    start_delay = config.get("start_delay", 5)
    click_delay = config["click_delay"]
    debug = config.get("debug", False)

    print("載入狀態模板...")
    templates = load_templates(states, window, scale)

    if not templates:
        print("\n錯誤: 沒有可用的模板")
        return

    print(f"\n已載入 {len(templates)} 個狀態")
    print(f"閾值: {threshold} | 間隔: {interval}s | Debug: {debug}")
    print(f"\n{start_delay} 秒後開始運行...")
    print("按 Ctrl+C 停止\n")
    time.sleep(start_delay)

    print("開始監控...\n")

    try:
        while True:
            current_frame = capture_window(window, scale)
            state, confidence, all_scores = match_state(
                current_frame, templates, states, window, scale, threshold
            )

            if debug:
                scores_str = " | ".join([f"{k}: {v:.2f}" for k, v in all_scores.items()])
                print(f"[DEBUG] {scores_str}")

            if state:
                x, y = states[state]["click"]
                print(f">>> [{state}] {confidence:.2f} → 點擊 ({x}, {y})")
                click_at(x, y, click_delay)

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n已停止運行")


if __name__ == "__main__":
    main()
