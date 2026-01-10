# BlueStacks 自動化腳本

監控 BlueStacks 視窗，自動點擊指定按鈕。

## 安裝

```bash
python3 -m venv venv
./venv/bin/pip install pyautogui opencv-python numpy
```

macOS 需開啟權限：系統設定 → 隱私權與安全性 → Screen Recording / Accessibility

## 使用

### 執行主程式
```bash
./venv/bin/python main.py
```

### 添加新狀態
```bash
./venv/bin/python add_state.py
```

### 記錄滑鼠位置（輔助）
```bash
./venv/bin/python record_positions.py
```

### 截取狀態畫面（輔助）
```bash
./venv/bin/python capture_state.py <狀態名稱>
```

## 設定檔 config.json

```json
{
  "window": {
    "left": 540, "top": 391,
    "right": 924, "bottom": 1078
  },
  "scale": 2,
  "match_threshold": 0.8,
  "loop_interval": 1.0,
  "click_delay": [0.8, 1.5],
  "debug": true,
  "states": {
    "狀態名稱": {
      "click": [x, y],
      "enabled": true,
      "region": [left, top, right, bottom]
    }
  }
}
```

| 欄位 | 說明 |
|------|------|
| window | BlueStacks 視窗位置（邏輯座標）|
| scale | Retina 縮放比例（Mac 通常是 2）|
| match_threshold | 相似度閾值，0-1 |
| loop_interval | 掃描間隔（秒）|
| click_delay | 點擊後隨機等待範圍 |
| debug | 顯示所有狀態準確度 |
| states | 狀態定義 |

### 狀態欄位

| 欄位 | 必填 | 說明 |
|------|------|------|
| click | 是 | 點擊座標 [x, y] |
| enabled | 否 | 預設 true，設 false 停用 |
| region | 否 | 特徵區域 [left, top, right, bottom]，用於相似畫面 |

## 檔案結構

```
auto-bs/
├── main.py              # 主程式
├── add_state.py         # 添加新狀態
├── record_positions.py  # 記錄座標
├── capture_state.py     # 截取畫面
├── config.json          # 設定檔
└── templates/           # 狀態截圖
```
