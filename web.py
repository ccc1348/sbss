"""
Web 界面
"""

from flask import Flask, render_template, jsonify, request, Response
from pathlib import Path
import core
import threading
import time
import queue
import base64
import cv2
import os

BASE_DIR = Path(__file__).parent
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))

# ============ 自動關閉管理 ============

class ShutdownManager:
    """管理自動關閉 - 使用心跳檢測"""
    def __init__(self, timeout=5):
        self.timeout = timeout
        self.last_heartbeat = None
        self.lock = threading.Lock()
        self.checker_thread = None

    def heartbeat(self):
        with self.lock:
            first_beat = self.last_heartbeat is None
            self.last_heartbeat = time.time()

        # 第一次心跳時啟動檢查線程
        if first_beat:
            self.checker_thread = threading.Thread(target=self._checker, daemon=True)
            self.checker_thread.start()

    def _checker(self):
        """定期檢查心跳是否超時"""
        while True:
            time.sleep(1)
            with self.lock:
                if self.last_heartbeat is None:
                    continue
                elapsed = time.time() - self.last_heartbeat
                if elapsed > self.timeout:
                    print(f"\n心跳超時 ({elapsed:.1f}s)，自動關閉服務...")
                    os._exit(0)


shutdown_manager = ShutdownManager(timeout=15)

# ============ 運行管理 ============

class Runner:
    """管理自動化運行"""
    def __init__(self):
        self.thread = None
        self.status = "stopped"  # stopped, running
        self.profile_name = None
        self.device = None
        self.logs = []
        self.max_logs = 100
        self.lock = threading.Lock()
        # 順序模式狀態
        self.sequential_mode = False
        self.current_step_index = -1  # -1 表示尚未開始
        self.current_step_name = None
        self.step_names = []  # 啟用的步驟名稱列表

    def log(self, msg):
        with self.lock:
            timestamp = time.strftime("%H:%M:%S")
            self.logs.append({"time": timestamp, "msg": msg})
            if len(self.logs) > self.max_logs:
                self.logs.pop(0)

    def get_logs(self, since=0):
        with self.lock:
            return self.logs[since:]

    def clear_logs(self):
        with self.lock:
            self.logs = []

    def start(self, profile_name, device=None):
        if self.status == "running":
            return False, "已在運行中"

        self.profile_name = profile_name
        self.device = device or "localhost:5555"
        self.status = "running"
        self.clear_logs()

        # 重置順序模式狀態
        config = core.get_profile_config(profile_name)
        self.sequential_mode = config.get("sequential_mode", False)
        self.current_step_index = -1
        self.current_step_name = None
        self.step_names = []

        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        return True, "已啟動"

    def stop(self):
        if self.status == "running":
            self.status = "stopped"
            self.log("已停止")
            return True
        return False

    def _run_loop(self):
        """自動化主循環"""
        mode_text = "順序模式" if self.sequential_mode else "全部比對"
        self.log(f"開始運行: {self.profile_name} ({self.device}) [{mode_text}]")

        # 嘗試連接（如果是 localhost:port 格式）
        if self.device.startswith("localhost:"):
            port = int(self.device.split(":")[1])
            if not core.adb_connect(port=port):
                self.log(f"無法連接 ADB: {self.device}")
                self.status = "stopped"
                return

        settings = core.get_shared_settings()
        threshold = settings["match_threshold"]
        loop_interval = settings["loop_interval"]
        long_interval = settings["long_interval"]
        miss_threshold = settings["miss_threshold"]
        click_delay = settings["click_delay"]

        miss_count = 0

        while self.status != "stopped":
            # 截圖
            screenshot = core.adb_screenshot(device=self.device)
            if screenshot is None:
                self.log("截圖失敗")
                time.sleep(loop_interval)
                continue

            # 載入狀態
            states = core.get_states(self.profile_name)
            all_state_names = list(states.keys())
            total_steps = len(all_state_names)

            # 建立啟用的步驟列表，保留原始索引
            # (原始索引, 名稱, 設定)
            enabled_states = [(i, name, cfg) for i, (name, cfg) in enumerate(states.items())
                              if cfg.get("enabled", True)]
            self.step_names = [name for _, name, _ in enabled_states]

            if not enabled_states:
                time.sleep(loop_interval)
                continue

            matched = False
            matched_name = None
            matched_index = -1

            if self.sequential_mode:
                # 順序模式
                # 啟動時（index=-1）先全部比對，找到當前位置
                if self.current_step_index == -1:
                    candidates = list(enabled_states)  # 全部比對
                else:
                    candidates = self._get_sequential_candidates(enabled_states)

                for enabled_idx, (orig_idx, state_name, config) in enumerate(candidates):
                    match_result = self._try_match(screenshot, state_name, config, threshold)
                    if match_result:
                        min_score, click = match_result
                        if click:
                            if self.current_step_index == -1:
                                self.log(f"初始定位: 從步驟 {orig_idx + 1} 開始")
                            else:
                                # 計算跳過的啟用步驟數
                                skipped = enabled_idx
                                if skipped > 0:
                                    self.log(f"跳過 {skipped} 步")
                            self.log(f"[{orig_idx + 1}/{total_steps}] 匹配: {state_name} ({min_score:.2f}) → 點擊 {click}")
                            core.adb_tap(click[0], click[1], device=self.device)
                            delay = click_delay[0] + (click_delay[1] - click_delay[0]) * (time.time() % 1)
                            time.sleep(delay)

                        matched = True
                        matched_name = state_name
                        matched_index = orig_idx

                        # 更新當前步驟（使用在 enabled_states 中的位置）
                        current_enabled_idx = next(i for i, (oi, n, c) in enumerate(enabled_states) if n == state_name)
                        self.current_step_index = current_enabled_idx
                        self.current_step_name = state_name

                        # 如果是最後一個啟用的步驟，重新開始
                        if current_enabled_idx >= len(enabled_states) - 1:
                            self.log("完成一輪，重新開始")
                            self.current_step_index = -1
                            self.current_step_name = None

                        miss_count = 0
                        break

                # 防呆：如果 candidates 都不匹配，且已經到達尾端（最後都是可略過的），重新開始
                if not matched and candidates:
                    last_candidate_enabled_idx = next(
                        (i for i, (oi, n, c) in enumerate(enabled_states) if n == candidates[-1][1]),
                        -1
                    )
                    if last_candidate_enabled_idx >= len(enabled_states) - 1:
                        self.log("尾端步驟皆未匹配，重新開始")
                        self.current_step_index = -1
                        self.current_step_name = None
            else:
                # 全部比對模式：遍歷所有步驟
                for orig_idx, state_name, config in enabled_states:
                    match_result = self._try_match(screenshot, state_name, config, threshold)
                    if match_result:
                        min_score, click = match_result
                        if click:
                            self.log(f"匹配: {state_name} ({min_score:.2f}) → 點擊 {click}")
                            core.adb_tap(click[0], click[1], device=self.device)
                            delay = click_delay[0] + (click_delay[1] - click_delay[0]) * (time.time() % 1)
                            time.sleep(delay)

                        matched = True
                        miss_count = 0
                        break

            if not matched:
                miss_count += 1
                if miss_count >= miss_threshold:
                    time.sleep(long_interval)
                else:
                    time.sleep(loop_interval)
            else:
                time.sleep(loop_interval)

        self.log("運行結束")

    def _get_sequential_candidates(self, enabled_states):
        """取得順序模式下要比對的步驟範圍
        - 如果當前步驟是可重複的，從當前步驟開始
        - 否則從 current_step_index + 1 開始
        - 到下一個不可略過的步驟為止
        enabled_states 格式: [(原始索引, 名稱, 設定), ...]
        """
        start_idx = self.current_step_index + 1
        current_is_repeatable = False

        # 如果當前步驟是可重複的，從當前步驟開始比對
        if self.current_step_index >= 0 and self.current_step_index < len(enabled_states):
            _, _, current_config = enabled_states[self.current_step_index]
            if current_config.get("repeatable", False):
                start_idx = self.current_step_index
                current_is_repeatable = True

        candidates = []

        for idx in range(start_idx, len(enabled_states)):
            orig_idx, state_name, config = enabled_states[idx]
            candidates.append((orig_idx, state_name, config))

            # 遇到不可略過的步驟就停止
            # 但當前的 repeatable 步驟不算停止點（需要繼續往後找）
            if not config.get("skippable", False):
                if current_is_repeatable and idx == self.current_step_index:
                    continue  # 跳過當前 repeatable 步驟
                break

        return candidates

    def _try_match(self, screenshot, state_name, config, threshold):
        """嘗試匹配單一步驟，返回 (min_score, click) 或 None"""
        template_path = core.get_template_path(state_name, self.profile_name)
        if not template_path.exists():
            return None

        template = core.imread_safe(template_path)
        if template is None:
            return None

        regions = core.get_regions(config)
        if not regions:
            return None

        # 比對所有區域（全部通過才算匹配）
        min_score = 1.0
        for region in regions:
            frame_region = core.crop_region(screenshot, region)
            template_region = core.crop_region(template, region)
            score = core.match_region(frame_region, template_region)
            min_score = min(min_score, score)
            if score < threshold:
                return None

        click = config.get("click", [])
        return (min_score, click)


# 全局 runner 實例
runner = Runner()


# ============ 頁面路由 ============

@app.route("/")
def index():
    """首頁 - Profile 列表"""
    profiles = core.get_profile_list()
    return render_template("index.html", profiles=profiles)


@app.route("/profile/<name>")
def profile_page(name):
    """Profile 詳情頁"""
    config = core.get_profile_config(name)
    if config is None:
        return "Profile 不存在", 404
    states = core.get_states(name)
    sequential_mode = config.get("sequential_mode", False)
    return render_template("profile.html", name=name, states=states, runner=runner,
                          sequential_mode=sequential_mode)


@app.route("/settings")
def settings_page():
    """設定頁面"""
    settings = core.get_shared_settings()
    return render_template("settings.html", settings=settings)


@app.route("/profile/<name>/add")
def add_state_page(name):
    """新增狀態頁"""
    return render_template("state_editor.html", profile=name, state_name=None, is_new=True)


@app.route("/profile/<name>/edit/<state_name>")
def edit_state_page(name, state_name):
    """編輯狀態頁"""
    states = core.get_states(name)
    if state_name not in states:
        return "狀態不存在", 404
    return render_template("state_editor.html", profile=name, state_name=state_name,
                          config=states[state_name], is_new=False)


# ============ API 路由 ============

@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    """取得設定"""
    return jsonify(core.get_shared_settings())


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    """儲存設定"""
    data = request.json
    core.save_json(core.SHARED_DIR / "settings.json", data)
    return jsonify({"success": True})


@app.route("/api/profiles", methods=["GET"])
def api_get_profiles():
    """取得 Profile 列表"""
    return jsonify(core.get_profile_list())


@app.route("/api/profile", methods=["POST"])
def api_create_profile():
    """建立 Profile"""
    data = request.json
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "名稱不能為空"}), 400

    success, msg = core.create_profile(name)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": msg}), 400


@app.route("/api/profile/<name>", methods=["DELETE"])
def api_delete_profile(name):
    """刪除 Profile"""
    success, msg = core.delete_profile(name)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": msg}), 400


@app.route("/api/profile/<name>/clone", methods=["POST"])
def api_clone_profile(name):
    """複製 Profile"""
    data = request.json
    new_name = data.get("name", "").strip()
    if not new_name:
        return jsonify({"error": "名稱不能為空"}), 400

    success, msg = core.clone_profile(name, new_name)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": msg}), 400


@app.route("/api/profile/<name>/rename", methods=["POST"])
def api_rename_profile(name):
    """重新命名 Profile"""
    data = request.json
    new_name = data.get("name", "").strip()
    if not new_name:
        return jsonify({"error": "名稱不能為空"}), 400

    success, msg = core.rename_profile(name, new_name)
    if success:
        return jsonify({"success": True, "new_name": new_name})
    return jsonify({"error": msg}), 400


@app.route("/api/profile/<name>/states", methods=["GET"])
def api_get_states(name):
    """取得狀態列表"""
    states = core.get_states(name)
    return jsonify(states)


@app.route("/api/profile/<name>/state", methods=["POST"])
def api_save_state(name):
    """儲存狀態（新增或更新）"""
    data = request.json
    state_name = data.get("name", "").strip()
    old_name = data.get("old_name", "").strip()
    click = data.get("click")
    regions = data.get("regions", [])

    if not state_name:
        return jsonify({"error": "名稱不能為空"}), 400
    if not click or len(click) != 2:
        return jsonify({"error": "請選擇點擊位置"}), 400
    if not regions:
        return jsonify({"error": "請選擇至少一個區域"}), 400

    # 處理模板
    screenshot_b64 = data.get("screenshot")
    template_path = core.get_template_path(state_name, name)
    template_path.parent.mkdir(parents=True, exist_ok=True)

    if screenshot_b64:
        # 有新截圖，儲存
        import numpy as np
        img_data = base64.b64decode(screenshot_b64)
        img_array = np.frombuffer(img_data, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        core.imwrite_safe(template_path, img)
    elif old_name and old_name != state_name:
        # 改名但沒新截圖，複製舊模板
        import shutil
        old_template = core.get_template_path(old_name, name)
        if old_template.exists():
            shutil.copy(old_template, template_path)

    # 儲存設定
    config = core.get_profile_config(name)
    if "states" not in config:
        config["states"] = {}

    is_new = not old_name
    is_rename = old_name and old_name != state_name

    # 建立新的 state 設定
    new_state_config = {"click": click}
    if len(regions) == 1:
        new_state_config["region"] = regions[0]
    else:
        new_state_config["regions"] = regions

    if is_new:
        # 新增：放在最上方，預設 disabled
        new_state_config["enabled"] = False
        new_states = {state_name: new_state_config}
        new_states.update(config["states"])
        config["states"] = new_states
    elif is_rename:
        # 重命名：保持原位置，保留其他屬性
        old_config = config["states"].get(old_name, {})
        new_state_config["enabled"] = old_config.get("enabled", True)
        new_state_config["skippable"] = old_config.get("skippable", False)
        new_state_config["repeatable"] = old_config.get("repeatable", False)

        # 重建 states 保持順序
        new_states = {}
        for k, v in config["states"].items():
            if k == old_name:
                new_states[state_name] = new_state_config
            else:
                new_states[k] = v
        config["states"] = new_states

        # 刪除舊模板
        old_template = core.get_template_path(old_name, name)
        if old_template.exists() and old_name != state_name:
            old_template.unlink()
    else:
        # 編輯（同名）：保留既有屬性，只更新 click 和 regions
        old_config = config["states"].get(state_name, {})
        new_state_config["enabled"] = old_config.get("enabled", True)
        new_state_config["skippable"] = old_config.get("skippable", False)
        new_state_config["repeatable"] = old_config.get("repeatable", False)
        config["states"][state_name] = new_state_config

    core.save_profile_config(name, config)

    return jsonify({"success": True})


@app.route("/api/profile/<name>/state/<state_name>", methods=["DELETE"])
def api_delete_state(name, state_name):
    """刪除狀態"""
    success, msg = core.remove_state(name, state_name)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": msg}), 400


@app.route("/api/profile/<name>/state/<state_name>/toggle", methods=["POST"])
def api_toggle_state(name, state_name):
    """切換啟用"""
    states = core.get_states(name)
    if state_name not in states:
        return jsonify({"error": "狀態不存在"}), 404

    current = states[state_name].get("enabled", True)
    core.toggle_state(name, state_name, not current)
    return jsonify({"enabled": not current})


@app.route("/api/profile/<name>/state/<state_name>/move", methods=["POST"])
def api_move_state(name, state_name):
    """移動狀態順序"""
    data = request.json
    direction = data.get("direction", 0)

    if direction not in (-1, 1):
        return jsonify({"error": "無效方向"}), 400

    success = core.move_state(name, state_name, direction)
    return jsonify({"success": success})


@app.route("/api/profile/<name>/reorder", methods=["POST"])
def api_reorder_states(name):
    """重新排序狀態（拖拽後）"""
    data = request.json
    new_order = data.get("order", [])

    config = core.get_profile_config(name)
    old_states = config.get("states", {})

    # 重建 states dict
    new_states = {}
    for state_name in new_order:
        if state_name in old_states:
            new_states[state_name] = old_states[state_name]

    # 保留未在 new_order 中的狀態（以防萬一）
    for state_name in old_states:
        if state_name not in new_states:
            new_states[state_name] = old_states[state_name]

    config["states"] = new_states
    core.save_profile_config(name, config)

    return jsonify({"success": True})


@app.route("/api/profile/<name>/sequential", methods=["POST"])
def api_toggle_sequential(name):
    """切換順序模式"""
    data = request.json
    enabled = data.get("enabled", False)

    config = core.get_profile_config(name)
    if config is None:
        return jsonify({"error": "Profile 不存在"}), 404

    config["sequential_mode"] = enabled
    core.save_profile_config(name, config)

    return jsonify({"success": True, "sequential_mode": enabled})


@app.route("/api/profile/<name>/state/<state_name>/skippable", methods=["POST"])
def api_toggle_skippable(name, state_name):
    """切換步驟可略過"""
    data = request.json
    skippable = data.get("skippable", False)

    config = core.get_profile_config(name)
    if config is None:
        return jsonify({"error": "Profile 不存在"}), 404

    states = config.get("states", {})
    if state_name not in states:
        return jsonify({"error": "狀態不存在"}), 404

    states[state_name]["skippable"] = skippable
    core.save_profile_config(name, config)

    return jsonify({"success": True, "skippable": skippable})


@app.route("/api/profile/<name>/state/<state_name>/repeatable", methods=["POST"])
def api_toggle_repeatable(name, state_name):
    """切換步驟可重複"""
    data = request.json
    repeatable = data.get("repeatable", False)

    config = core.get_profile_config(name)
    if config is None:
        return jsonify({"error": "Profile 不存在"}), 404

    states = config.get("states", {})
    if state_name not in states:
        return jsonify({"error": "狀態不存在"}), 404

    states[state_name]["repeatable"] = repeatable
    core.save_profile_config(name, config)

    return jsonify({"success": True, "repeatable": repeatable})


# ============ 截圖 API ============

@app.route("/api/profile/<name>/state/<state_name>/screenshot")
def api_state_screenshot(name, state_name):
    """取得步驟的已存截圖"""
    template_path = core.get_template_path(state_name, name)
    if not template_path.exists():
        return jsonify({"error": "截圖不存在"}), 404

    img = core.imread_safe(template_path)
    if img is None:
        return jsonify({"error": "讀取失敗"}), 500

    _, buffer = cv2.imencode(".png", img)
    b64 = base64.b64encode(buffer).decode("utf-8")

    return jsonify({"image": b64, "width": img.shape[1], "height": img.shape[0]})


@app.route("/api/screenshot")
def api_screenshot():
    """取得當前截圖"""
    device = request.args.get("device", "localhost:5555")

    # 嘗試連接（如果是 localhost:port 格式）
    if device.startswith("localhost:"):
        port = int(device.split(":")[1])
        if not core.adb_connect(port=port):
            return jsonify({"error": f"無法連接 ADB: {device}"}), 500

    img = core.adb_screenshot(device=device)
    if img is None:
        return jsonify({"error": "截圖失敗"}), 500

    # 轉成 base64
    _, buffer = cv2.imencode(".png", img)
    b64 = base64.b64encode(buffer).decode("utf-8")

    return jsonify({"image": b64, "width": img.shape[1], "height": img.shape[0]})


# ============ 設備 API ============

def scan_adb_ports():
    """掃描常見 ADB 端口，找出正在監聽的"""
    import socket
    listening = []
    # BlueStacks: 5555, 5565, 5575...  LDPlayer: 5555, 5556...  夜神: 62001...
    for port in list(range(5555, 5600)) + [62001, 62025]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result == 0:
            listening.append(port)
    return listening


@app.route("/api/devices")
def api_list_devices():
    """列出所有已連接的 ADB 設備"""
    # 掃描並連接監聽中的 ADB 端口
    for port in scan_adb_ports():
        core.adb_connect(port=port)

    devices = core.adb_list_devices()
    return jsonify({"devices": devices})


# ============ 運行控制 API ============

@app.route("/api/runner/start/<profile_name>", methods=["POST"])
def api_runner_start(profile_name):
    """啟動運行"""
    data = request.json or {}
    device = data.get("device")
    success, msg = runner.start(profile_name, device=device)
    return jsonify({"success": success, "message": msg})


@app.route("/api/runner/stop", methods=["POST"])
def api_runner_stop():
    """停止"""
    success = runner.stop()
    return jsonify({"success": success})


@app.route("/api/runner/status")
def api_runner_status():
    """取得運行狀態"""
    since = request.args.get("since", 0, type=int)
    return jsonify({
        "status": runner.status,
        "profile": runner.profile_name,
        "logs": runner.get_logs(since),
        "log_count": len(runner.logs),
        "sequential_mode": runner.sequential_mode,
        "current_step_index": runner.current_step_index,
        "current_step_name": runner.current_step_name,
        "step_names": runner.step_names
    })


@app.route("/api/heartbeat", methods=["POST"])
def api_heartbeat():
    """心跳 - 用於追蹤頁面連線狀態"""
    shutdown_manager.heartbeat()
    return "", 204


@app.route("/api/runner/stream")
def api_runner_stream():
    """SSE 串流運行狀態"""
    import json

    def generate():
        last_log_count = 0
        last_status = None
        last_step_index = None

        while True:
            status = runner.status
            log_count = len(runner.logs)
            step_index = runner.current_step_index

            # 偵測 log 被清空（重新啟動時）
            if log_count < last_log_count:
                last_log_count = 0

            # 只在有變化時發送
            if status != last_status or log_count != last_log_count or step_index != last_step_index:
                data = {
                    "status": status,
                    "logs": runner.get_logs(last_log_count),
                    "log_count": log_count,
                    "sequential_mode": runner.sequential_mode,
                    "current_step_index": runner.current_step_index,
                    "current_step_name": runner.current_step_name,
                    "step_names": runner.step_names
                }
                yield f"data: {json.dumps(data)}\n\n"
                last_status = status
                last_log_count = log_count
                last_step_index = step_index

            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")


# ============ 主程式 ============

def find_free_port(start_port=8080, max_attempts=10):
    """尋找可用端口"""
    import socket
    for port in range(start_port, start_port + max_attempts):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", port))
            sock.close()
            return port
        except OSError:
            continue
    raise RuntimeError(f"找不到可用端口 ({start_port}-{start_port + max_attempts - 1})")


if __name__ == "__main__":
    import webbrowser
    import os

    port = find_free_port(8080)

    print("啟動 Web 界面...")
    print(f"http://127.0.0.1:{port}")

    # 只在主進程開啟瀏覽器（避免 reloader 重複開啟）
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        webbrowser.open(f"http://127.0.0.1:{port}")

    app.run(host="127.0.0.1", port=port, debug=False)
