"""
移除狀態工具
用途：刪除指定狀態及其模板圖片
"""

import readline  # 改善中文輸入
import json
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


def main():
    print("=== 移除狀態 ===\n")

    config = load_config()
    states = list(config["states"].keys())

    if not states:
        print("沒有任何狀態")
        return

    # 顯示列表
    print("現有狀態:")
    for i, name in enumerate(states, 1):
        state_config = config["states"][name]
        enabled = state_config.get("enabled", True)
        status = "" if enabled else " (disabled)"

        if "regions" in state_config:
            region_str = f" [{len(state_config['regions'])} 區域]"
        elif "region" in state_config:
            region_str = " [1 區域]"
        else:
            region_str = ""

        print(f"  {i}. {name}{status}{region_str}")

    print(f"\n輸入數字 1-{len(states)} 移除，或 q 取消")

    choice = input("\n選擇: ").strip()

    if choice.lower() == 'q':
        print("已取消")
        return

    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(states):
            print("無效選擇")
            return
    except ValueError:
        print("請輸入數字")
        return

    name = states[idx]

    # 確認
    confirm = input(f"\n確定要移除「{name}」？(y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        return

    # 刪除模板圖片
    template_path = TEMPLATES_DIR / f"{name}.png"
    if template_path.exists():
        os.remove(template_path)
        print(f"已刪除: {template_path}")

    # 更新設定
    del config["states"][name]
    save_config(config)
    print(f"已從 config.json 移除: {name}")

    print("\n完成！")


if __name__ == "__main__":
    main()
