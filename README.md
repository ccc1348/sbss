# BlueStacks 自動化腳本

透過 ADB 監控 BlueStacks 畫面，自動辨識遊戲狀態並點擊。支援多開、跨平台（macOS/Windows）。

## 需求

- Python 3.8+
- ADB（Android Debug Bridge）
- BlueStacks 已啟用 ADB（設定 → 進階 → Android Debug Bridge）

## 安裝

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## 使用

```bash
./venv/bin/python run.py
```

### 主選單
- 選擇 Profile 進入操作
- `[+]` 新增 Profile
- `[r]` 併行運行
- `[s]` 設定

### Profile 選單
- `[r]` 運行
- `[a]` 新增狀態
- `[c]` 從其他 Profile 複製
- `[m]` 編輯狀態
- `[d]` 刪除狀態
- `[t]` 切換啟用
- `[e]` 測試比對

## 目錄結構

```
auto-bs/
├── run.py                  # 入口
├── core.py                 # 核心
├── shared/
│   └── settings.json       # 共用設定
└── profiles/
    └── <profile_name>/
        ├── config.json     # 狀態設定
        └── templates/      # 模板截圖
```

## 設定說明

### shared/settings.json

```json
{
  "resolution": [1080, 1920],
  "match_threshold": 0.8,
  "loop_interval": 0.8,
  "long_interval": 10,
  "miss_threshold": 5,
  "start_delay": 2,
  "click_delay": [0.8, 1.5],
  "debug": true
}
```

| 欄位 | 說明 |
|------|------|
| resolution | BlueStacks 解析度 [寬, 高] |
| match_threshold | 相似度閾值 0-1 |
| loop_interval | 短間隔（秒）|
| long_interval | 長間隔（秒）|
| miss_threshold | 連續未命中幾次後切換長間隔 |
| click_delay | 點擊後等待範圍 |
| debug | 顯示比對分數 |

### profiles/\<name\>/config.json

```json
{
  "states": {
    "狀態名稱": {
      "click": [540, 960],
      "region": [100, 200, 300, 400],
      "enabled": true
    }
  }
}
```

## 功能

### 純 ADB 模式
- 使用 ADB 截圖和點擊，視窗可被遮擋
- 跨平台（macOS/Windows 使用同一套設定）
- 座標都是 Android 座標

### 解析度共用
- BlueStacks 解析度相同，設定完全共用
- 可複製整個 Profile 到其他機器

### 複製狀態
- 從其他 Profile 複製狀態（設定 + 模板）
- 支援單個或全部複製

## 多開

BlueStacks 多開時，每個實例有不同 ADB 端口：
- 實例 1: `localhost:5555`
- 實例 2: `localhost:5565`
- ...

目前預設連接 `localhost:5555`。
