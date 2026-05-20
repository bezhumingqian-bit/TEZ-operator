#!/usr/bin/env bash
# 健康检查（容器状态 + API ping）
# 退出码：0 全绿；1 任意一项异常
set -uo pipefail

cd "$(dirname "$0")/.."

echo "🩺 TEZ Operator 健康检查..."

# 检查哪些容器存在（W1 阶段只有 mysql + redis）
candidates=("tez-mysql" "tez-redis" "tez-backend" "tez-frontend")
all_ok=true
checked=0

for svc in "${candidates[@]}"; do
    status=$(docker inspect -f '{{.State.Status}}' "$svc" 2>/dev/null || echo "missing")
    case "$status" in
        running)
            echo "  ✅ $svc"
            checked=$((checked+1))
            ;;
        missing)
            echo "  ⏭  $svc 未部署（跳过）"
            ;;
        *)
            echo "  ❌ $svc: $status"
            all_ok=false
            ;;
    esac
done

if [[ "$checked" == "0" ]]; then
    echo "❌ 没有任何 TEZ 容器在运行，请先 ./scripts/start.sh"
    exit 1
fi

# MySQL ping
if docker ps --format '{{.Names}}' | grep -q '^tez-mysql$'; then
    if docker exec tez-mysql mysqladmin ping -h localhost --silent 2>/dev/null; then
        echo "  ✅ MySQL ping"
    else
        echo "  ❌ MySQL ping 失败"
        all_ok=false
    fi
fi

# Redis ping
if docker ps --format '{{.Names}}' | grep -q '^tez-redis$'; then
    if [[ "$(docker exec tez-redis redis-cli ping 2>/dev/null)" == "PONG" ]]; then
        echo "  ✅ Redis ping"
    else
        echo "  ❌ Redis ping 失败"
        all_ok=false
    fi
fi

# Backend API
if docker ps --format '{{.Names}}' | grep -q '^tez-backend$'; then
    if curl -fsS http://localhost:8000/health > /dev/null 2>&1; then
        echo "  ✅ Backend /health"
    else
        echo "  ❌ Backend /health 不通"
        all_ok=false
    fi
fi

if $all_ok; then
    echo "🎉 全部健康"
    exit 0
else
    echo "⚠️  存在异常，请检查日志：docker compose logs -f"
    exit 1
fi
