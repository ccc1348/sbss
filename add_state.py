"""
添加新狀態工具
用途：記錄座標 + 截取畫面 + 可選多個特徵區域 + 更新設定檔
"""

import readline  # 改善中文輸入
import pyautogui
import json
import time
import os
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "config.json"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_regions_display(state_config):
    """取得區域顯示文字"""
    if "regions" in state_config:
        return f"{len(state_config['regions'])} 個區域"
    elif "region" in state_config:
        return "1 個區域"
    return "全畫面"


def main():
    print("=== 添加新狀態 ===\n")

    config = load_config()
    scale = config["scale"]
    window = config["window"]

    # 顯示現有狀態
    print("現有狀態:")
    for name, state_config in config["states"].items():
        click = state_config.get("click")
        regions_str = get_regions_display(state_config)
        print(f"  {name}: click={click}, {regions_str}")
    print()

    # 輸入名稱
    name = input("新狀態名稱 (或 q 取消): ").strip()
    if not name or name.lower() == 'q':
        print("已取消")
        return

    if name in config["states"]:
        overwrite = input(f"'{name}' 已存在，要覆蓋嗎？(y/n): ").strip().lower()
        if overwrite != 'y':
            print("已取消")
            return

    # 記錄點擊座標
    print(f"\n請把滑鼠移到「{name}」要點擊的位置，然後按 Enter...")
    input()
    click_x, click_y = pyautogui.position()
    print(f"點擊座標: ({click_x}, {click_y})")

    # 詢問是否使用特徵區域
    use_region = input("\n是否指定特徵區域？(y/n，預設 n): ").strip().lower() == 'y'

    regions = []
    if use_region:
        print("\n可以指定多個區域，輸入 d 完成")
        region_count = 1

        while True:
            print(f"\n--- 區域 {region_count} ---")
            print("請把滑鼠移到區域的【左上角】，然後按 Enter (或輸入 d 完成)...")
            cmd = input().strip().lower()
            if cmd == 'd':
                break

            r_x1, r_y1 = pyautogui.position()
            print(f"左上角: ({r_x1}, {r_y1})")

            print("請把滑鼠移到區域的【右下角】，然後按 Enter...")
            input()
            r_x2, r_y2 = pyautogui.position()
            print(f"右下角: ({r_x2}, {r_y2})")

            region = [min(r_x1, r_x2), min(r_y1, r_y2), max(r_x1, r_x2), max(r_y1, r_y2)]
            regions.append(region)
            print(f"已記錄區域 {region_count}: {region}")
            region_count += 1

        if regions:
            print(f"\n共記錄 {len(regions)} 個區域")

    # 截取畫面
    print("\n截圖中...")
    screenshot = pyautogui.screenshot()
    screenshot_np = __import__('numpy').array(screenshot)

    left = window["left"] * scale
    top = window["top"] * scale
    right = window["right"] * scale
    bottom = window["bottom"] * scale

    cropped = screenshot_np[top:bottom, left:right]

    # 儲存
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    output_path = TEMPLATES_DIR / f"{name}.png"

    from PIL import Image
    Image.fromarray(cropped).save(output_path)
    print(f"畫面已儲存: {output_path}")

    # 更新設定
    state_config = {"click": [click_x, click_y]}
    if len(regions) == 1:
        state_config["region"] = regions[0]
    elif len(regions) > 1:
        state_config["regions"] = regions

    config["states"][name] = state_config
    save_config(config)

    if regions:
        print(f"設定已更新: {name} → click=({click_x}, {click_y}), {len(regions)} 個區域")
    else:
        print(f"設定已更新: {name} → click=({click_x}, {click_y}), 全畫面")

    print("\n完成！")


if __name__ == "__main__":
    main()
