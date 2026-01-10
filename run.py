#!/usr/bin/env python3
"""
BlueStacks 自動化工具 - 統一入口
支援多 Profile 管理與併行運行
"""

import readline  # 改善中文輸入
import sys
import os
import pyautogui
from multiprocessing import Process, Event

import core


def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_header():
    print("=" * 50)
    print("  BlueStacks 自動化工具")
    print("=" * 50)


def get_regions_display(state_config):
    """取得區域顯示文字"""
    if "regions" in state_config:
        return f"{len(state_config['regions'])} 個區域"
    elif "region" in state_config:
        return "1 個區域"
    return "全畫面"


# ============ 主選單 ============

def main_menu():
    """主選單：選擇 Profile"""
    while True:
        clear_screen()
        print_header()
        print()

        profiles = core.get_profile_list()

        if profiles:
            print("現有 Profiles:")
            for i, name in enumerate(profiles, 1):
                config = core.get_profile_config(name)
                window = config.get("window", {})
                pos = f"({window.get('left', '?')}, {window.get('top', '?')})"
                states = core.get_merged_states(name)
                enabled_count = sum(1 for s in states.values() if s.get("enabled", True))
                print(f"  [{i}] {name} - 視窗: {pos} | 狀態: {enabled_count}/{len(states)}")
        else:
            print("(尚無任何 Profile)")

        print()
        print("  [+] 新增 Profile")
        print("  [r] 併行運行多個 Profile")
        print("  [s] 編輯共用設定")
        print("  [q] 離開")
        print()

        choice = input("選擇: ").strip().lower()

        if choice == 'q':
            print("再見！")
            sys.exit(0)
        elif choice == '+':
            create_profile_menu()
        elif choice == 'r':
            run_multiple_profiles(profiles)
        elif choice == 's':
            edit_shared_settings()
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(profiles):
                    profile_menu(profiles[idx])
            except ValueError:
                pass


# ============ Profile 選單 ============

def profile_menu(profile_name):
    """Profile 內部選單"""
    while True:
        clear_screen()
        config = core.get_profile_config(profile_name)
        states = core.get_merged_states(profile_name)
        settings = core.get_shared_settings()

        window = config.get("window", {})
        shared_count = sum(1 for s in states.values() if s.get("_source") == "shared")
        local_count = sum(1 for s in states.values() if s.get("_source") == "local")

        print("=" * 50)
        print(f"  Profile: {profile_name}")
        print("=" * 50)
        print()
        print(f"  視窗位置: ({window.get('left')}, {window.get('top')}) - ({window.get('right')}, {window.get('bottom')})")
        print(f"  共用狀態: {shared_count} | 本地狀態: {local_count}")
        print()
        print("  [r] 運行自動化")
        print("  [l] 列出所有狀態")
        print("  [a] 新增狀態")
        print("  [d] 刪除狀態")
        print("  [t] 切換狀態啟用")
        print("  [w] 設定視窗位置")
        print("  [x] 刪除此 Profile")
        print("  [b] 返回")
        print()

        choice = input("選擇: ").strip().lower()

        if choice == 'b':
            return
        elif choice == 'r':
            run_single_profile(profile_name)
        elif choice == 'l':
            list_states(profile_name)
        elif choice == 'a':
            add_state_menu(profile_name)
        elif choice == 'd':
            remove_state_menu(profile_name)
        elif choice == 't':
            toggle_state_menu(profile_name)
        elif choice == 'w':
            set_window_position(profile_name)
        elif choice == 'x':
            if delete_profile_confirm(profile_name):
                return


# ============ 運行功能 ============

def run_single_profile(profile_name):
    """運行單一 Profile"""
    clear_screen()
    print(f"準備運行 Profile: {profile_name}")
    print("按 Ctrl+C 停止")
    print()

    try:
        core.run_automation(profile_name)
    except KeyboardInterrupt:
        print("\n已停止")

    input("\n按 Enter 返回...")


def run_multiple_profiles(profiles):
    """併行運行多個 Profile"""
    if not profiles:
        print("沒有可用的 Profile")
        input("\n按 Enter 返回...")
        return

    clear_screen()
    print("=== 併行運行 ===\n")

    print("可用 Profiles:")
    for i, name in enumerate(profiles, 1):
        print(f"  [{i}] {name}")

    print()
    print("輸入要運行的編號（用空格分隔，如 '1 2 3'）")
    print("或輸入 'all' 運行全部")
    print()

    choice = input("選擇: ").strip().lower()

    if choice == 'all':
        selected = profiles
    else:
        try:
            indices = [int(x) - 1 for x in choice.split()]
            selected = [profiles[i] for i in indices if 0 <= i < len(profiles)]
        except (ValueError, IndexError):
            print("無效輸入")
            input("\n按 Enter 返回...")
            return

    if not selected:
        print("未選擇任何 Profile")
        input("\n按 Enter 返回...")
        return

    print(f"\n將運行: {', '.join(selected)}")
    print("按 Ctrl+C 停止所有\n")

    processes = []
    stop_events = []

    try:
        for name in selected:
            stop_event = Event()
            stop_events.append(stop_event)
            p = Process(target=core.run_automation, args=(name, stop_event))
            p.start()
            processes.append(p)
            print(f"啟動: {name} (PID: {p.pid})")

        print("\n所有 Profile 已啟動，等待中...")

        for p in processes:
            p.join()

    except KeyboardInterrupt:
        print("\n\n正在停止所有 Profile...")
        for event in stop_events:
            event.set()
        for p in processes:
            p.terminate()
            p.join(timeout=2)
        print("已停止所有 Profile")

    input("\n按 Enter 返回...")


# ============ 狀態管理 ============

def list_states(profile_name):
    """列出所有狀態"""
    clear_screen()
    states = core.get_merged_states(profile_name)

    print(f"=== {profile_name} 的狀態 ===\n")

    if not states:
        print("(無任何狀態)")
    else:
        for name, config in states.items():
            source = config.get("_source", "unknown")
            enabled = config.get("enabled", True)
            status = "" if enabled else " [停用]"
            regions = get_regions_display(config)
            click = config.get("click", [])

            print(f"  {name}{status}")
            print(f"    來源: {source} | 點擊: {click} | {regions}")

    input("\n按 Enter 返回...")


def add_state_menu(profile_name):
    """新增狀態"""
    clear_screen()
    print("=== 新增狀態 ===\n")

    # 選擇目標
    print("新增到哪裡？")
    print("  [s] shared（所有 Profile 共用）")
    print("  [l] 本地（只有此 Profile）")
    print("  [b] 取消")
    print()

    target = input("選擇: ").strip().lower()
    if target not in ['s', 'l']:
        return

    save_to_shared = (target == 's')

    # 取得設定
    settings = core.get_shared_settings()
    scale = settings["scale"]

    config = core.get_profile_config(profile_name)
    window = config["window"]

    # 輸入名稱
    print()
    name = input("狀態名稱 (或 q 取消): ").strip()
    if not name or name.lower() == 'q':
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

    # 截圖
    print("\n截圖中...")
    output_path = core.capture_and_save_template(
        name, window, scale,
        save_to_shared=save_to_shared,
        profile_name=profile_name
    )
    print(f"畫面已儲存: {output_path}")

    # 儲存設定
    if save_to_shared:
        core.add_state_to_shared(name, [click_x, click_y], regions or None)
        print(f"\n已新增到 shared: {name}")
    else:
        core.add_state_to_profile(profile_name, name, [click_x, click_y], regions or None)
        print(f"\n已新增到 {profile_name}: {name}")

    input("\n按 Enter 返回...")


def remove_state_menu(profile_name):
    """刪除狀態"""
    clear_screen()
    states = core.get_merged_states(profile_name)

    print("=== 刪除狀態 ===\n")

    if not states:
        print("(無任何狀態)")
        input("\n按 Enter 返回...")
        return

    state_list = list(states.keys())
    for i, name in enumerate(state_list, 1):
        source = states[name].get("_source", "unknown")
        print(f"  [{i}] {name} ({source})")

    print()
    print("  [b] 取消")
    print()

    choice = input("選擇要刪除的狀態: ").strip().lower()
    if choice == 'b':
        return

    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(state_list):
            print("無效選擇")
            input("\n按 Enter 返回...")
            return
    except ValueError:
        return

    name = state_list[idx]
    source = states[name].get("_source", "unknown")

    confirm = input(f"\n確定要刪除「{name}」({source})？(y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        input("\n按 Enter 返回...")
        return

    if source == "shared":
        success, msg = core.remove_state_from_shared(name)
    else:
        success, msg = core.remove_state_from_profile(profile_name, name)

    print(f"\n{msg}")
    input("\n按 Enter 返回...")


def toggle_state_menu(profile_name):
    """切換狀態啟用"""
    clear_screen()
    states = core.get_merged_states(profile_name)

    print("=== 切換狀態啟用 ===\n")

    if not states:
        print("(無任何狀態)")
        input("\n按 Enter 返回...")
        return

    state_list = list(states.keys())
    for i, name in enumerate(state_list, 1):
        enabled = states[name].get("enabled", True)
        status = "啟用" if enabled else "停用"
        source = states[name].get("_source", "unknown")
        print(f"  [{i}] {name} - {status} ({source})")

    print()
    print("  [b] 返回")
    print()

    choice = input("選擇要切換的狀態: ").strip().lower()
    if choice == 'b':
        return

    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(state_list):
            print("無效選擇")
            input("\n按 Enter 返回...")
            return
    except ValueError:
        return

    name = state_list[idx]
    current_enabled = states[name].get("enabled", True)
    new_enabled = not current_enabled

    core.toggle_state_in_profile(profile_name, name, new_enabled)

    status = "啟用" if new_enabled else "停用"
    print(f"\n已將「{name}」設為 {status}")
    input("\n按 Enter 返回...")


# ============ Profile 管理 ============

def create_profile_menu():
    """建立新 Profile"""
    clear_screen()
    print("=== 新增 Profile ===\n")

    name = input("Profile 名稱 (或 q 取消): ").strip()
    if not name or name.lower() == 'q':
        return

    # 設定視窗位置
    print("\n設定視窗位置：")
    print("請把滑鼠移到視窗【左上角】，然後按 Enter...")
    input()
    left, top = pyautogui.position()
    print(f"左上角: ({left}, {top})")

    print("請把滑鼠移到視窗【右下角】，然後按 Enter...")
    input()
    right, bottom = pyautogui.position()
    print(f"右下角: ({right}, {bottom})")

    window = {
        "left": min(left, right),
        "top": min(top, bottom),
        "right": max(left, right),
        "bottom": max(top, bottom)
    }

    success, msg = core.create_profile(name, window)
    print(f"\n{msg}")

    input("\n按 Enter 返回...")


def delete_profile_confirm(profile_name):
    """確認刪除 Profile"""
    print(f"\n確定要刪除 Profile「{profile_name}」？")
    print("這將刪除所有本地狀態和模板")
    confirm = input("輸入 'yes' 確認: ").strip().lower()

    if confirm == 'yes':
        success, msg = core.delete_profile(profile_name)
        print(f"\n{msg}")
        input("\n按 Enter 返回...")
        return True
    else:
        print("已取消")
        return False


def set_window_position(profile_name):
    """設定視窗位置"""
    clear_screen()
    print(f"=== 設定視窗位置: {profile_name} ===\n")

    config = core.get_profile_config(profile_name)
    current = config.get("window", {})
    print(f"目前: ({current.get('left')}, {current.get('top')}) - ({current.get('right')}, {current.get('bottom')})")
    print()

    print("請把滑鼠移到視窗【左上角】，然後按 Enter...")
    input()
    left, top = pyautogui.position()
    print(f"左上角: ({left}, {top})")

    print("請把滑鼠移到視窗【右下角】，然後按 Enter...")
    input()
    right, bottom = pyautogui.position()
    print(f"右下角: ({right}, {bottom})")

    config["window"] = {
        "left": min(left, right),
        "top": min(top, bottom),
        "right": max(left, right),
        "bottom": max(top, bottom)
    }

    core.save_profile_config(profile_name, config)
    print("\n視窗位置已更新")

    input("\n按 Enter 返回...")


def edit_shared_settings():
    """編輯共用設定"""
    clear_screen()
    print("=== 共用設定 ===\n")

    settings = core.get_shared_settings()

    print(f"  scale: {settings.get('scale')}")
    print(f"  match_threshold: {settings.get('match_threshold')}")
    print(f"  loop_interval: {settings.get('loop_interval')}")
    print(f"  start_delay: {settings.get('start_delay')}")
    print(f"  click_delay: {settings.get('click_delay')}")
    print(f"  debug: {settings.get('debug')}")
    print()
    print("(編輯 shared/settings.json 來修改設定)")

    input("\n按 Enter 返回...")


# ============ 主程式 ============

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\n再見！")
        sys.exit(0)
