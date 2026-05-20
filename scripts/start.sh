#!/usr/bin/env bash
# 一键启动 TEZ Operator
# 用法：./scripts/start.sh [--with-app]
#   默认仅启动 mysql + redis 基础设施
#   --with-app 同时启动 backend + frontend（需镜像就绪）
set -euo pipefail

cd "$(dirname "$0")/.."

WITH_APP=0
for arg in "$@"; do
    case "$arg" in
        --with-app) WITH_APP=1 ;;
        *) echo "未知参数: $arg"; exit 1 ;;
    esac
done

echo "🚀 启动 TEZ Operator..."

# 1) 检查 Docker 在跑
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker 未启动，请先打开 Docker Desktop / 启动 docker 守护进程"
    exit 1
fi

# 2) 检查 .env
if [[ ! -f .env ]]; then
    echo "❌ 未找到 .env，请先执行：cp .env.example .env 并填充配置"
    exit 1
fi

# 3) 选择 compose 命令
if docker compose version > /dev/null 2>&1; then
    COMPOSE="docker compose"
else
    COMPOSE="docker-compose"
fi

# 4) 启动服务
if [[ "$WITH_APP" == "1" ]]; then
    echo "📦 启动 mysql + redis + backend + frontend..."
    $COMPOSE --profile app up -d
else
    echo "📦 启动 mysql + redis（W1 默认模式，不带 app）..."
    $COMPOSE up -d mysql redis
fi

# 5) 等待 MySQL 就绪
echo "⏳ 等待 MySQL 就绪..."
for i in {1..30}; do
    if docker exec tez-mysql mysqladmin ping -h localhost --silent 2>/dev/null; then
        echo "✅ MySQL ready"
        break
    fi
    sleep 2
done

# 6) 应用层迁移（仅 with-app 时）
if [[ "$WITH_APP" == "1" ]]; then
    echo "📦 执行数据库迁移..."
    docker exec tez-backend uv run alembic upgrade head || \
        echo "⚠️  alembic 未配置或失败，请检查 backend"
fi

# 7) 健康检查
sleep 2
./scripts/healthcheck.sh || true

LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
echo "✅ 启动完成"
echo "   后端 API: http://${LOCAL_IP}:8000/docs"
echo "   前端 UI : http://${LOCAL_IP}:8080"
