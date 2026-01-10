"""
模板截圖輔助工具
用途：截取按鈕圖片作為模板
使用方式：python capture_template.py <模板名稱>
範例：python capture_template.py 開始配對
"""

import pyautogui
import sys
import time
import os

def get_scale_factor():
    """計算 Retina 縮放比例"""
    screen_width, _ = pyautogui.size()
    screenshot = pyautogui.screenshot()
    return screenshot.size[0] / screen_width

def main():
    if len(sys.argv) < 2:
        print("使用方式: python capture_template.py <模板名稱>")
        print("範例: python capture_template.py 開始配對")
        return

    template_name = sys.argv[1]
    output_path = f"templates/{template_name}.png"

    # 確保 templates 目錄存在
    os.makedirs("templates", exist_ok=True)

    scale = get_scale_factor()
    print(f"偵測到縮放比例: {scale}x")
    print("")
    print("=== 模板截圖工具 ===")
    print("")
    print("操作步驟：")
    print("1. 把滑鼠移到按鈕的「左上角」，等待 3 秒")
    print("2. 再把滑鼠移到按鈕的「右下角」，等待 3 秒")
    print("")
    input("準備好後按 Enter 開始...")

    # 第一個點：左上角
    print("\n請將滑鼠移到按鈕【左上角】...")
    time.sleep(3)
    x1, y1 = pyautogui.position()
    print(f"左上角: ({x1}, {y1})")

    # 第二個點：右下角
    print("\n請將滑鼠移到按鈕【右下角】...")
    time.sleep(3)
    x2, y2 = pyautogui.position()
    print(f"右下角: ({x2}, {y2})")

    # 計算區域
    left = min(x1, x2)
    top = min(y1, y2)
    width = abs(x2 - x1)
    height = abs(y2 - y1)

    if width < 5 or height < 5:
        print("錯誤：區域太小，請重新操作")
        return

    # 截圖
    print(f"\n截取區域: 左上({left}, {top}), 寬高({width}, {height})")

    # PyAutoGUI 的 region 使用邏輯座標
    screenshot = pyautogui.screenshot(region=(left, top, width, height))
    screenshot.save(output_path)

    print(f"\n模板已儲存: {output_path}")
    print(f"圖片尺寸: {screenshot.size[0]} x {screenshot.size[1]} 像素")

if __name__ == "__main__":
    main()
