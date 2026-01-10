"""
位置記錄工具
用途：記錄滑鼠位置，方便截取按鈕
使用方式：執行後，把滑鼠移到目標位置，按 Enter 記錄
"""

import readline  # 改善中文輸入
import pyautogui

def main():
    print("=== 位置記錄工具 ===")
    print("操作方式：")
    print("  1. 把滑鼠移到按鈕位置")
    print("  2. 回到 Terminal 按 Enter 記錄")
    print("  3. 輸入 q 結束\n")

    positions = []
    count = 1

    while True:
        name = input(f"[{count}] 輸入按鈕名稱 (或 q 結束): ").strip()

        if name.lower() == 'q':
            break

        if not name:
            print("  名稱不能為空，請重新輸入")
            continue

        print(f"  請把滑鼠移到「{name}」按鈕上，然後按 Enter...")
        input()

        x, y = pyautogui.position()
        positions.append((name, x, y))
        print(f"  已記錄: {name} -> ({x}, {y})\n")
        count += 1

    print("\n=== 記錄結果 ===")
    for name, x, y in positions:
        print(f"{name}: ({x}, {y})")

if __name__ == "__main__":
    main()
