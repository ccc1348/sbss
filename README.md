# BlueStacks 自動化腳本

監控 BlueStacks 視窗，自動辨識遊戲狀態並點擊。支援多開（多 Profile）與自動視窗偏移計算。

## 安裝

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

macOS 需開啟權限：系統設定 → 隱私權與安全性 → Screen Recording / Accessibility

## 使用

```bash
./venv/bin/python run.py
```

### 主選單
- 選擇 Profile 進入操作
- `[+]` 新增 Profile（自動偵測 BlueStacks 視窗位置）
- `[r]` 併行運行多個 Profile
- `[s]` 查看共用設定

### Profile 選單
- `[r]` 運行自動化
- `[l]` 列出所有狀態
- `[a]` 新增狀態（可選 shared 或 local）
- `[d]` 刪除狀態
- `[t]` 切換狀態啟用/停用
- `[w]` 設定視窗位置

## 目錄結構

```
auto-bs/
├── run.py                  # 統一入口
├── core.py                 # 核心模組
├── shared/
│   ├── settings.json       # 共用設定
│   ├── states.json         # 共用狀態定義
│   └── templates/          # 共用模板截圖
└── profiles/
    └── <profile_name>/
        ├── config.json     # Profile 設定（視窗位置、override、local states）
        └── templates/      # 本地模板截圖
```

## 設定說明

### shared/settings.json

```json
{
  "scale": 2,
  "match_threshold": 0.8,
  "loop_interval": 1.0,
  "long_interval": 15,
  "miss_threshold": 5,
  "start_delay": 2,
  "click_delay": [0.8, 1.5],
  "debug": true
}
```

| 欄位 | 說明 |
|------|------|
| scale | Retina 縮放比例（Mac 通常是 2）|
| match_threshold | 相似度閾值，0-1 |
| loop_interval | 短間隔掃描（秒）|
| long_interval | 長間隔掃描（秒）|
| miss_threshold | 連續未命中幾次後切換到長間隔 |
| start_delay | 啟動延遲（秒）|
| click_delay | 點擊後隨機等待範圍 |
| debug | 顯示所有狀態準確度 |

### profiles/\<name\>/config.json

```json
{
  "window": { "left": 540, "top": 391, "right": 924, "bottom": 1078 },
  "reference_window": { "left": 537, "top": 356, "right": 958, "bottom": 1079 },
  "override_states": {},
  "local_states": {}
}
```

| 欄位 | 說明 |
|------|------|
| window | 截圖區域（遊戲畫面範圍）|
| reference_window | 參考視窗位置（錄製狀態時的位置，用於偏移計算）|
| override_states | 覆蓋 shared 狀態的設定（如停用）|
| local_states | 此 Profile 專屬的狀態 |

## 功能特點

### 自動視窗偵測
使用 macOS Quartz API 自動偵測 BlueStacks 視窗位置，無需手動設定座標。

### 自動偏移計算
記錄狀態時的視窗位置（reference_window），運行時自動計算偏移，視窗移動後無需重新錄製狀態。

### 兩段式間隔
連續未命中時自動切換到長間隔，減少資源消耗（適用於副本進行中的等待時間）。

### 共用與本地狀態
- **shared**: 所有 Profile 共用（如結算畫面）
- **local**: 單一 Profile 專屬（如特定副本入口）
- **override**: 可針對特定 Profile 停用或修改 shared 狀態
