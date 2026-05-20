#!/usr/bin/env bash
# 重启 TEZ Operator
# 用法：./scripts/restart.sh [--with-app]
set -euo pipefail

cd "$(dirname "$0")/.."

echo "🔄 重启 TEZ Operator..."
./scripts/stop.sh
sleep 2
./scripts/start.sh "$@"
