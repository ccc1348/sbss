"""
環境測試腳本
用途：確認截圖功能正常、檢查 Retina 縮放比例
"""

import pyautogui
import time

def main():
    print("=== 環境測試 ===\n")

    # 1. 取得螢幕尺寸（PyAutoGUI 認知的邏輯尺寸）
    screen_width, screen_height = pyautogui.size()
    print(f"螢幕邏輯尺寸: {screen_width} x {screen_height}")

    # 2. 截圖並檢查實際像素
    print("\n3 秒後截圖，請確保 BlueStacks 視窗可見...")
    time.sleep(3)

    screenshot = pyautogui.screenshot()
    actual_width, actual_height = screenshot.size
    print(f"截圖實際尺寸: {actual_width} x {actual_height}")

    # 3. 計算縮放比例
    scale = actual_width / screen_width
    print(f"縮放比例: {scale}x (Retina 通常是 2x)")

    # 4. 儲存截圖
    output_path = "test_screenshot.png"
    screenshot.save(output_path)
    print(f"\n截圖已儲存: {output_path}")

    # 5. 測試滑鼠位置
    print("\n接下來測試滑鼠位置讀取，5 秒內移動滑鼠到 BlueStacks 視窗...")
    for i in range(5):
        time.sleep(1)
        x, y = pyautogui.position()
        print(f"  滑鼠位置: ({x}, {y})")

    print("\n=== 測試完成 ===")
    print("請檢查 test_screenshot.png 確認截圖正常")
    print(f"記住縮放比例: {scale}x，後續開發需要用到")

if __name__ == "__main__":
    main()
