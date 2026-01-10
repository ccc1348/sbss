# Android 自動工具

透過 ADB 自動辨識畫面並點擊，適用於 BlueStacks 等模擬器。支援多開、跨平台（macOS/Windows）。

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

### Web 界面（推薦）

```bash
./venv/bin/python web.py
```

自動開啟瀏覽器，在網頁上操作：
- 管理 腳本 和步驟
- 截圖選擇點擊位置和區域
- 拖拽排序步驟
- 啟動/暫停/停止運行
- 即時日誌顯示

### 命令行界面

```bash
./venv/bin/python run.py
```

### 主選單
- 選擇 腳本 進入操作
- `[+]` 新增 腳本
- `[r]` 併行運行
- `[s]` 設定

### 腳本 選單
- 輸入數字選擇步驟
- `[a]` 新增步驟
- `[r]` 運行
- `[e]` 測試比對

### 步驟選單
- `[m]` 編輯（重新錄製）
- `[d]` 刪除
- `[t]` 切換啟用
- `[u]` 上移 / `[j]` 下移

## 目錄結構

```
sbss/
├── run.py                  # 入口
├── core.py                 # 核心
├── shared/
│   └── settings.json       # 共用設定
└── profiles/
    └── <profile_name>/
        ├── config.json     # 步驟設定
        └── templates/      # 步驟截圖
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
    "步驟名稱": {
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
- 可複製整個 腳本 到其他機器

## 多開

BlueStacks 多開時，每個實例有不同 ADB 端口：
- 實例 1: `localhost:5555`
- 實例 2: `localhost:5565`
- ...

目前預設連接 `localhost:5555`。
