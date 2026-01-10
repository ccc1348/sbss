#!/usr/bin/env python3
"""
BlueStacks 自動化工具
純 ADB 模式 - 跨平台支援
"""

import readline  # 改善中文輸入
import sys
import os
from multiprocessing import Process, Event

import cv2
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
    """主選單"""
    while True:
        clear_screen()
        print_header()
        print()

        profiles = core.get_profile_list()

        if profiles:
            print("Profiles:")
            for i, name in enumerate(profiles, 1):
                states = core.get_states(name)
                enabled = sum(1 for s in states.values() if s.get("enabled", True))
                print(f"  [{i}] {name} ({enabled}/{len(states)} 狀態)")
        else:
            print("(尚無任何 Profile)")

        print()
        print("  [+] 新增 Profile")
        print("  [r] 併行運行")
        print("  [s] 設定")
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
            show_settings()
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(profiles):
                    profile_menu(profiles[idx])
            except ValueError:
                pass


# ============ Profile 選單 ============

def profile_menu(profile_name):
    """Profile 選單"""
    while True:
        clear_screen()
        states = core.get_states(profile_name)
        state_list = list(states.keys())

        print("=" * 50)
        print(f"  {profile_name}")
        print("=" * 50)
        print()

        if states:
            print("狀態（執行順序）:")
            for i, name in enumerate(state_list, 1):
                config = states[name]
                enabled = config.get("enabled", True)
                status = "✓" if enabled else "✗"
                click = config.get("click", [])
                print(f"  [{i}] {status} {name} - {click}")
        else:
            print("(無狀態)")

        print()
        print("輸入數字選擇狀態，或:")
        print("  [a] 新增  [r] 運行  [e] 測試比對")
        print("  [x] 刪除 Profile  [b] 返回")
        print()

        choice = input("選擇: ").strip().lower()

        if choice == 'b':
            return
        elif choice == 'r':
            run_single_profile(profile_name)
        elif choice == 'a':
            add_state_menu(profile_name)
        elif choice == 'e':
            test_state_menu(profile_name)
        elif choice == 'x':
            if delete_profile_confirm(profile_name):
                return
        else:
            # 嘗試解析數字
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(state_list):
                    state_menu(profile_name, state_list[idx])
            except ValueError:
                pass


def state_menu(profile_name, state_name):
    """單一狀態選單"""
    while True:
        clear_screen()
        states = core.get_states(profile_name)

        if state_name not in states:
            return

        config = states[state_name]
        enabled = config.get("enabled", True)
        click = config.get("click", [])
        regions = get_regions_display(config)

        # 找出目前位置
        state_list = list(states.keys())
        idx = state_list.index(state_name)

        print("=" * 50)
        print(f"  {state_name}")
        print("=" * 50)
        print()
        print(f"  狀態: {'啟用' if enabled else '停用'}")
        print(f"  點擊: {click}")
        print(f"  區域: {regions}")
        print(f"  順序: {idx + 1} / {len(state_list)}")
        print()
        print("  [m] 編輯  [d] 刪除  [t] 切換啟用")
        print("  [u] 上移  [j] 下移")
        print("  [b] 返回")
        print()

        choice = input("選擇: ").strip().lower()

        if choice == 'b':
            return
        elif choice == 'm':
            record_state(profile_name, state_name)
        elif choice == 'd':
            if input(f"刪除「{state_name}」？(y/n): ").strip().lower() == 'y':
                core.remove_state(profile_name, state_name)
                print("已刪除")
                input("\n按 Enter 返回...")
                return
        elif choice == 't':
            core.toggle_state(profile_name, state_name, not enabled)
        elif choice == 'u':
            core.move_state(profile_name, state_name, -1)
        elif choice == 'j':
            core.move_state(profile_name, state_name, 1)


# ============ 運行 ============

def run_single_profile(profile_name):
    """運行單一 Profile"""
    clear_screen()
    print(f"運行: {profile_name}")
    print("按 Ctrl+C 停止\n")

    try:
        core.run_automation(profile_name)
    except KeyboardInterrupt:
        print("\n已停止")

    input("\n按 Enter 返回...")


def run_multiple_profiles(profiles):
    """併行運行"""
    if not profiles:
        print("沒有可用的 Profile")
        input("\n按 Enter 返回...")
        return

    clear_screen()
    print("=== 併行運行 ===\n")

    for i, name in enumerate(profiles, 1):
        print(f"  [{i}] {name}")

    print()
    print("輸入編號（空格分隔）或 'all'")
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
        return

    print(f"\n運行: {', '.join(selected)}")
    print("按 Ctrl+C 停止\n")

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

        for p in processes:
            p.join()

    except KeyboardInterrupt:
        print("\n停止中...")
        for event in stop_events:
            event.set()
        for p in processes:
            p.terminate()
            p.join(timeout=2)

    input("\n按 Enter 返回...")


# ============ 狀態管理 ============

def add_state_menu(profile_name):
    """新增狀態"""
    clear_screen()
    print("=== 新增狀態 ===\n")

    name = input("狀態名稱 (q 取消): ").strip()
    if not name or name.lower() == 'q':
        return

    # 檢查是否已存在
    states = core.get_states(profile_name)
    if name in states:
        print(f"狀態「{name}」已存在")
        input("\n按 Enter 返回...")
        return

    record_state(profile_name, name)


def record_state(profile_name, state_name):
    """錄製狀態（新增/編輯共用）- 純 ADB 模式"""
    clear_screen()
    print(f"=== 錄製: {state_name} ===\n")

    # 連接 ADB
    if not core.adb_connect():
        print("錯誤: 無法連接 ADB")
        input("\n按 Enter 返回...")
        return

    android_w, android_h = core.adb_get_resolution()
    if not android_w or not android_h:
        print("錯誤: 無法取得解析度")
        input("\n按 Enter 返回...")
        return

    if android_h < android_w:
        android_w, android_h = android_h, android_w

    # 驗證解析度
    settings = core.get_shared_settings()
    expected = settings.get("resolution", [1080, 1920])
    if [android_w, android_h] != expected:
        print(f"警告: 解析度不符 (設定: {expected[0]}x{expected[1]}, 實際: {android_w}x{android_h})")
        if input("繼續？(y/n): ").strip().lower() != 'y':
            return

    print(f"Android 解析度: {android_w}x{android_h}\n")

    # 先截圖一次，後續都用這張圖
    print("截圖中...")
    screenshot = core.adb_screenshot()
    if screenshot is None:
        print("截圖失敗!")
        input("\n按 Enter 返回...")
        return
    print("截圖完成\n")

    # 步驟 1: 選擇點擊位置 (在截圖上選)
    print("【步驟 1】選擇點擊位置")
    print("在截圖視窗上點擊選擇位置，按 Enter 確認\n")

    click_pos = core.adb_select_point(screenshot, title=f"{state_name} - 點擊位置")
    if not click_pos:
        print("已取消")
        cv2.destroyAllWindows()
        for _ in range(5):
            cv2.waitKey(1)
        input("\n按 Enter 返回...")
        return

    click_x, click_y = click_pos
    print(f"點擊座標: ({click_x}, {click_y})\n")

    # 步驟 2: 選擇特徵區域 (用同一張截圖)
    regions = []
    print("【步驟 2】特徵區域（可選）")
    if input("指定特徵區域？(y/n，預設 n): ").strip().lower() == 'y':
        print("拖曳框選區域，按 Enter 確認，ESC 結束\n")
        while True:
            region = core.adb_select_region(screenshot, title=f"{state_name} - 區域 {len(regions)+1}")
            if not region:
                break
            regions.append(list(region))
            print(f"  已加入區域 {len(regions)}: {region}")
            if input("繼續加入？(y/n): ").strip().lower() != 'y':
                break

    # 步驟 3: 儲存截圖
    print("\n【步驟 3】儲存模板")
    template_path = core.get_template_path(state_name, profile_name)
    template_path.parent.mkdir(parents=True, exist_ok=True)
    core.imwrite_safe(template_path, screenshot)
    print(f"已儲存: {template_path}")

    # 儲存
    core.add_state(profile_name, state_name, [click_x, click_y], regions or None)
    print(f"\n已儲存: {state_name}")
    print(f"  點擊: ({click_x}, {click_y})")
    if regions:
        print(f"  區域: {regions}")

    # 確保關閉所有 OpenCV 視窗
    cv2.destroyAllWindows()
    for _ in range(5):
        cv2.waitKey(1)

    input("\n按 Enter 返回...")


def test_state_menu(profile_name):
    """測試比對"""
    states = core.get_states(profile_name)
    if not states:
        print("無狀態")
        input("\n按 Enter 返回...")
        return

    clear_screen()
    print("=== 測試比對 ===\n")

    if not core.adb_connect():
        print("無法連接 ADB")
        input("\n按 Enter 返回...")
        return

    settings = core.get_shared_settings()
    threshold = settings["match_threshold"]

    print("截圖中...")
    frame = core.adb_screenshot()
    if frame is None:
        print("截圖失敗")
        input("\n按 Enter 返回...")
        return

    print(f"尺寸: {frame.shape[1]}x{frame.shape[0]}\n")

    for state_name, config in states.items():
        path = core.get_template_path(state_name, profile_name)
        if not path.exists():
            print(f"  {state_name}: 缺少模板")
            continue

        template = core.imread_safe(path)
        if template is None:
            print(f"  {state_name}: 無法讀取")
            continue

        regions = core.get_regions(config)

        if regions:
            scores = []
            for region in regions:
                fr = core.crop_region(frame, region)
                tr = core.crop_region(template, region)
                if fr is not None and tr is not None:
                    scores.append(core.match_region(fr, tr))
                else:
                    scores.append(0)
            score = min(scores) if scores else 0
            detail = ", ".join([f"{s:.2f}" for s in scores])
            mark = "V" if score >= threshold else " "
            print(f"  {mark} {state_name}: {score:.4f} ({detail})")
        else:
            score = core.match_region(frame, template)
            mark = "V" if score >= threshold else " "
            print(f"  {mark} {state_name}: {score:.4f}")

    print(f"\n閾值: {threshold}")
    input("\n按 Enter 返回...")


# ============ Profile 管理 ============

def create_profile_menu():
    """建立 Profile"""
    clear_screen()
    print("=== 新增 Profile ===\n")

    name = input("名稱 (q 取消): ").strip()
    if not name or name.lower() == 'q':
        return

    success, msg = core.create_profile(name)
    print(msg)
    input("\n按 Enter 返回...")


def delete_profile_confirm(profile_name):
    """刪除 Profile"""
    if input(f"刪除 Profile「{profile_name}」？輸入 yes: ").strip().lower() == 'yes':
        success, msg = core.delete_profile(profile_name)
        print(msg)
        input("\n按 Enter 返回...")
        return True
    return False


def show_settings():
    """顯示設定"""
    clear_screen()
    print("=== 設定 ===\n")

    settings = core.get_shared_settings()
    res = settings.get('resolution', [1080, 1920])

    print(f"  resolution: {res[0]}x{res[1]}")
    print(f"  match_threshold: {settings.get('match_threshold')}")
    print(f"  loop_interval: {settings.get('loop_interval')}")
    print(f"  long_interval: {settings.get('long_interval')}")
    print(f"  click_delay: {settings.get('click_delay')}")
    print(f"  debug: {settings.get('debug')}")
    print()
    print("編輯: shared/settings.json")

    input("\n按 Enter 返回...")


# ============ 主程式 ============

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\n再見！")
        sys.exit(0)
