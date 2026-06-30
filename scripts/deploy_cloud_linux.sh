#!/bin/bash
# TEZ Operator 云桌面一键部署脚本 (Linux/macOS)
# 用法：bash deploy_cloud_linux.sh

set -e

PROJECT_DIR="$HOME/TEZ-operator"
PYTHON="python3"

echo "========================================"
echo "  TEZ Operator 云桌面部署 (Linux)"
echo "========================================"
echo ""

# ── Step 1: 检查 Python ──
echo "[1/6] 检查 Python..."
if ! command -v $PYTHON &> /dev/null; then
    echo "  Python3 未安装，请先安装: sudo apt install python3 python3-pip"
    exit 1
fi
$PYTHON --version
echo "  OK"

# ── Step 2: 复制项目 ──
echo "[2/6] 项目目录..."
if [ ! -d "$PROJECT_DIR" ]; then
    echo "  请先将 TEZ-operator 复制到 $PROJECT_DIR"
    echo "  scp -r TEZ-operator user@cloud-desktop:~/"
    exit 0
fi
cd "$PROJECT_DIR"

# ── Step 3: 安装依赖 ──
echo "[3/6] 安装 Python 依赖..."
pip install -r requirements.txt -q
echo "  OK"

# ── Step 4: 安装 Playwright ──
echo "[4/6] 安装 Playwright Chromium..."
$PYTHON -m playwright install chromium
echo "  OK"

# ── Step 5: 配置 ──
echo "[5/6] 配置环境..."
if [ ! -f .env ]; then
    if [ -f scripts/env_template.txt ]; then
        cp scripts/env_template.txt .env
        echo "  已从模板创建 .env（请填入真实 API Key 等敏感配置）"
    else
        echo "  未找到 .env 模板"
        exit 1
    fi
fi
sed -i 's/TEZ_BROWSER_HEADLESS=true/TEZ_BROWSER_HEADLESS=false/' .env
sed -i 's/TEZ_APP_DEBUG=true/TEZ_APP_DEBUG=false/' .env
echo "  已将 headless=false, debug=false"
echo "  OK"

# ── Step 6: 开机自启 (systemd) ──
echo "[6/6] 设置开机自启..."
SERVICE_FILE="/etc/systemd/system/tez-operator.service"
if [ ! -f "$SERVICE_FILE" ]; then
    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=TEZ Operator
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port 80 --log-level warning
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable tez-operator
    echo "  systemd 服务已创建"
else
    echo "  服务已存在，跳过"
fi
echo "  OK"

echo ""
echo "========================================"
echo "  部署完成！"
echo "========================================"
echo ""
echo "  启动服务:  sudo systemctl start tez-operator"
echo "  查看状态:  sudo systemctl status tez-operator"
echo "  查看日志:  journalctl -u tez-operator -f"
echo "  访问地址:  http://$(hostname -I | awk '{print $1}'):80"
echo ""
echo "  首次运行会弹出浏览器 → 扫码登录 iOA（只需一次）"
