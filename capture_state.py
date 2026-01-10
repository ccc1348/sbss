"""
狀態畫面截取工具
用途：截取 BlueStacks 視窗作為狀態判斷依據
"""

import pyautogui
import sys
import time
import os

# BlueStacks 視窗位置（邏輯座標）
WINDOW_LEFT = 540
WINDOW_TOP = 391
WINDOW_RIGHT = 924
WINDOW_BOTTOM = 1078

# 已記錄的狀態和點擊座標（邏輯座標）
STATES = {
    "退出結算1": (581, 1045),
    "退出結算2": (807, 786),
    "接受配對": (821, 981),
    "準備": (729, 900),
}

# Retina 縮放
SCALE = 2

def main():
    if len(sys.argv) < 2:
        print("使用方式: python capture_state.py <狀態名稱>")
        print("\n可用的狀態名稱:")
        for name, pos in STATES.items():
            print(f"  {name} -> 點擊座標 {pos}")
        print("\n範例: python capture_state.py 準備")
        return

    state_name = sys.argv[1]

    if state_name not in STATES:
        print(f"錯誤: 未知的狀態名稱 '{state_name}'")
        print("可用的狀態:", list(STATES.keys()))
        return

    os.makedirs("templates", exist_ok=True)

    print(f"準備截取狀態: {state_name}")
    print(f"視窗範圍: ({WINDOW_LEFT}, {WINDOW_TOP}) - ({WINDOW_RIGHT}, {WINDOW_BOTTOM})")
    print("\n截圖中...")
    screenshot = pyautogui.screenshot()

    # 計算裁切區域（像素座標，乘以 SCALE）
    left = WINDOW_LEFT * SCALE
    top = WINDOW_TOP * SCALE
    right = WINDOW_RIGHT * SCALE
    bottom = WINDOW_BOTTOM * SCALE

    # 裁切 BlueStacks 視窗
    cropped = screenshot.crop((left, top, right, bottom))

    output_path = f"templates/{state_name}.png"
    cropped.save(output_path)

    print(f"\n已儲存: {output_path}")
    print(f"圖片尺寸: {cropped.size[0]} x {cropped.size[1]}")

if __name__ == "__main__":
    main()
