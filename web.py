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

BASE_DIR = Path(__file__).parent
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))

# ============ 運行管理 ============

class Runner:
    """管理自動化運行"""
    def __init__(self):
        self.thread = None
        self.status = "stopped"  # stopped, running, paused
        self.profile_name = None
        self.logs = []
        self.max_logs = 100
        self.lock = threading.Lock()

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

    def start(self, profile_name):
        if self.status == "running":
            return False, "已在運行中"

        self.profile_name = profile_name
        self.status = "running"
        self.clear_logs()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        return True, "已啟動"

    def pause(self):
        if self.status == "running":
            self.status = "paused"
            self.log("已暫停")
            return True
        return False

    def resume(self):
        if self.status == "paused":
            self.status = "running"
            self.log("已繼續")
            return True
        return False

    def stop(self):
        if self.status in ("running", "paused"):
            self.status = "stopped"
            self.log("已停止")
            return True
        return False

    def _run_loop(self):
        """自動化主循環"""
        self.log(f"開始運行: {self.profile_name}")

        if not core.adb_connect():
            self.log("無法連接 ADB")
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
            # 暫停時等待
            if self.status == "paused":
                time.sleep(0.5)
                continue

            # 截圖
            screenshot = core.adb_screenshot()
            if screenshot is None:
                self.log("截圖失敗")
                time.sleep(loop_interval)
                continue

            # 載入狀態
            states = core.get_states(self.profile_name)
            matched = False

            for state_name, config in states.items():
                if not config.get("enabled", True):
                    continue

                template_path = core.get_template_path(state_name, self.profile_name)
                if not template_path.exists():
                    continue

                template = cv2.imread(str(template_path))
                if template is None:
                    continue

                regions = core.get_regions(config)
                if not regions:
                    continue

                # 比對所有區域（全部通過才算匹配）
                all_matched = True
                min_score = 1.0
                for region in regions:
                    frame_region = core.crop_region(screenshot, region)
                    template_region = core.crop_region(template, region)
                    score = core.match_region(frame_region, template_region)
                    min_score = min(min_score, score)
                    if score < threshold:
                        all_matched = False
                        break

                if all_matched:
                    click = config.get("click", [])
                    if click:
                        self.log(f"匹配: {state_name} ({min_score:.2f}) → 點擊 {click}")
                        core.adb_tap(click[0], click[1])

                        # 點擊後等待
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
    return render_template("profile.html", name=name, states=states, runner=runner)


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
        cv2.imwrite(str(template_path), img)
    elif old_name and old_name != state_name:
        # 改名但沒新截圖，複製舊模板
        import shutil
        old_template = core.get_template_path(old_name, name)
        if old_template.exists():
            shutil.copy(old_template, template_path)

    # 如果是重命名，刪除舊狀態
    if old_name and old_name != state_name:
        core.remove_state(name, old_name)

    # 儲存設定
    core.add_state(name, state_name, click, regions)

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


# ============ 截圖 API ============

@app.route("/api/profile/<name>/state/<state_name>/screenshot")
def api_state_screenshot(name, state_name):
    """取得步驟的已存截圖"""
    template_path = core.get_template_path(state_name, name)
    if not template_path.exists():
        return jsonify({"error": "截圖不存在"}), 404

    img = cv2.imread(str(template_path))
    if img is None:
        return jsonify({"error": "讀取失敗"}), 500

    _, buffer = cv2.imencode(".png", img)
    b64 = base64.b64encode(buffer).decode("utf-8")

    return jsonify({"image": b64, "width": img.shape[1], "height": img.shape[0]})


@app.route("/api/screenshot")
def api_screenshot():
    """取得當前截圖"""
    if not core.adb_connect():
        return jsonify({"error": "無法連接 ADB"}), 500

    img = core.adb_screenshot()
    if img is None:
        return jsonify({"error": "截圖失敗"}), 500

    # 轉成 base64
    _, buffer = cv2.imencode(".png", img)
    b64 = base64.b64encode(buffer).decode("utf-8")

    return jsonify({"image": b64, "width": img.shape[1], "height": img.shape[0]})


# ============ 運行控制 API ============

@app.route("/api/runner/start/<profile_name>", methods=["POST"])
def api_runner_start(profile_name):
    """啟動運行"""
    success, msg = runner.start(profile_name)
    return jsonify({"success": success, "message": msg})


@app.route("/api/runner/pause", methods=["POST"])
def api_runner_pause():
    """暫停"""
    success = runner.pause()
    return jsonify({"success": success})


@app.route("/api/runner/resume", methods=["POST"])
def api_runner_resume():
    """繼續"""
    success = runner.resume()
    return jsonify({"success": success})


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
        "log_count": len(runner.logs)
    })


@app.route("/api/runner/stream")
def api_runner_stream():
    """SSE 串流運行狀態"""
    import json

    def generate():
        last_log_count = 0
        last_status = None

        while True:
            status = runner.status
            log_count = len(runner.logs)

            # 偵測 log 被清空（重新啟動時）
            if log_count < last_log_count:
                last_log_count = 0

            # 只在有變化時發送
            if status != last_status or log_count != last_log_count:
                data = {
                    "status": status,
                    "logs": runner.get_logs(last_log_count),
                    "log_count": log_count
                }
                yield f"data: {json.dumps(data)}\n\n"
                last_status = status
                last_log_count = log_count

            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")


# ============ 主程式 ============

if __name__ == "__main__":
    import webbrowser
    import os

    port = 8080

    print("啟動 Web 界面...")
    print(f"http://127.0.0.1:{port}")

    # 只在主進程開啟瀏覽器（避免 reloader 重複開啟）
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        webbrowser.open(f"http://127.0.0.1:{port}")

    app.run(host="127.0.0.1", port=port, debug=False)
