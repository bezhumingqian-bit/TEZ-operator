#!/usr/bin/env bash
# 停止 TEZ Operator 全部服务
set -euo pipefail

cd "$(dirname "$0")/.."

if docker compose version > /dev/null 2>&1; then
    COMPOSE="docker compose"
else
    COMPOSE="docker-compose"
fi

echo "🛑 停止 TEZ Operator..."
$COMPOSE --profile app down
echo "✅ 已停止（数据卷 ./data 保留）"
