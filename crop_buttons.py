"""
根據記錄的位置截取按鈕圖片
"""

import pyautogui
from PIL import Image
import os

# 記錄的位置（邏輯座標）
POSITIONS = {
    "退出結算1": (581, 1045),
    "退出結算2": (807, 786),
    "接受配對": (821, 981),
    "準備": (729, 900),
}

# 按鈕大小（邏輯尺寸）
BUTTON_WIDTH = 120
BUTTON_HEIGHT = 50

# Retina 縮放比例
SCALE = 2

def main():
    print("請確保 BlueStacks 顯示相關畫面...")
    print("3 秒後截圖...\n")

    import time
    time.sleep(3)

    # 截取全螢幕
    screenshot = pyautogui.screenshot()
    print(f"截圖尺寸: {screenshot.size}")

    os.makedirs("templates", exist_ok=True)

    for name, (x, y) in POSITIONS.items():
        # 轉換為截圖像素座標
        px = x * SCALE
        py = y * SCALE
        pw = BUTTON_WIDTH * SCALE
        ph = BUTTON_HEIGHT * SCALE

        # 計算裁切區域（以座標為中心）
        left = px - pw // 2
        top = py - ph // 2
        right = px + pw // 2
        bottom = py + ph // 2

        # 裁切
        cropped = screenshot.crop((left, top, right, bottom))

        # 儲存
        output_path = f"templates/{name}.png"
        cropped.save(output_path)
        print(f"已儲存: {output_path} ({cropped.size[0]}x{cropped.size[1]})")

    print("\n完成！請檢查 templates/ 資料夾中的圖片")

if __name__ == "__main__":
    main()
