# ComicForge 漫鍛 - AI 漫畫生成引擎

## 🚀 快速啟動

### 方法 1: 使用啟動腳本（推薦）
```bash
# 默認端口 5003
./start.sh

# 指定端口
./start.sh 8080
```

### 方法 2: 手動啟動
```bash
# 創建虛擬環境
python3 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt

# 啟動服務
python3 app.py
```

## 📋 功能特色

- **IP-Adapter 角色一致性** - 使用 AI 保持角色外觀一致
- **多種漫畫風格** - 日系黑白、彩色、Webtoon、美式漫畫等
- **對話氣泡** - 自動添加專業對話氣泡
- **進度追蹤** - 即時查看生成進度
- **免費方案** - 免費用戶每月 20 格漫畫

## 🔧 環境要求

- Python 3.10+
- Apple Silicon Mac (M1/M2/M3/M4) 或支持 MPS 的 GPU
- 16GB+ RAM 推薦

## 📁 項目結構

```
comicforge/
├── app.py              # Flask 主應用
├── start.sh            # 啟動腳本
├── requirements.txt    # Python 依賴
├── templates/          # HTML 模板
├── output/             # 生成的漫畫
├── characters/         # 角色參考圖
└── venv/               # Python 虛擬環境
```

## 🌐 API 端點

### 健康檢查
```
GET /health
```

### 用戶認證
```
POST /api/register      # 註冊
POST /api/login         # 登入
GET  /api/logout        # 登出
```

### 角色管理
```
POST /api/character/upload    # 上傳角色參考圖
GET  /api/characters          # 獲取角色列表
```

### 漫畫生成
```
POST /api/comic/create        # 創建漫畫項目
GET  /api/comic/<proj_id>     # 獲取漫畫詳情
GET  /api/projects            # 獲取項目列表
```

## 🎨 漫畫風格

1. **日系黑白漫畫** - 經典黑白漫畫風格
2. **日系彩色漫畫** - 動漫彩色風格
3. **Webtoon 風格** - 韓國條漫風格
4. **美式漫畫** - 超級英雄風格
5. **水彩繪本** - 兒童繪本風格
6. **Q版可愛** - 可愛 Q 版風格

## 📊 進度追蹤

生成漫畫時，可以通過 API 獲取即時進度：
```json
{
  "id": 1,
  "status": "generating",
  "progress": 75,
  "total_panels": 4,
  "completed_panels": 3
}
```

## 🛠️ 故障排除

### 1. 端口被占用
```bash
# 查找占用端口的進程
lsof -i :5003

# 強制終止進程
kill -9 <PID>
```

### 2. 模型下載慢
設置 Hugging Face 鏡像：
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### 3. 內存不足
- 關閉其他應用程序
- 使用較小的圖片尺寸（512x512）
- 減少同時生成的面板數量

## 📞 聯繫方式

- **負責人**: 鄭凱壬 (Kent)
- **Email**: skybomb7777@gmail.com
- **GitHub**: https://github.com/skybomb77/comicforge

## 📄 授權

© 2026 Kent & KClaw Studio. All rights reserved.