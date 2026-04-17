#!/bin/bash
# ComicForge 啟動腳本
# 使用方法: ./start.sh [port]

set -e

PORT=${1:-5003}
VENV_DIR="venv"
LOG_FILE="comicforge.log"

echo "🎨 啟動 ComicForge 漫鍛引擎..."
echo "================================"

# 檢查 Python 版本
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "🐍 Python 版本: $PYTHON_VERSION"

# 檢查虛擬環境
if [ ! -d "$VENV_DIR" ]; then
    echo "⚠️  虛擬環境不存在，正在創建..."
    python3 -m venv $VENV_DIR
    echo "✅ 虛擬環境創建完成"
fi

# 啟動虛擬環境
echo "🔄 啟動虛擬環境..."
source $VENV_DIR/bin/activate

# 檢查依賴
echo "📦 檢查依賴套件..."
if [ -f "requirements.txt" ]; then
    pip install -q -r requirements.txt
    echo "✅ 依賴套件安裝完成"
else
    echo "⚠️  未找到 requirements.txt，安裝基本依賴..."
    pip install -q flask flask-cors flask-sqlalchemy torch diffusers transformers pillow
fi

# 創建必要目錄
mkdir -p output characters static templates instance

# 檢查數據庫
if [ ! -f "instance/comicforge.db" ]; then
    echo "🗄️  初始化數據庫..."
    python3 -c "from app import db; db.create_all()"
    echo "✅ 故據庫初始化完成"
fi

# 啟動服務
echo ""
echo "🚀 啟動 ComicForge 服務..."
echo "📍 地址: http://localhost:$PORT"
echo "📝 日誌: $LOG_FILE"
echo "⏹️  停止服務: Ctrl+C"
echo ""

# 使用 gunicorn 或直接啟動
if command -v gunicorn &> /dev/null; then
    echo "使用 gunicorn 啟動..."
    gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile - --error-logfile - | tee $LOG_FILE
else
    echo "使用 Flask 開發伺服器啟動..."
    python3 app.py 2>&1 | tee $LOG_FILE
fi