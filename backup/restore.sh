#!/usr/bin/env bash
# TEZ Operator 数据恢复
# 用法：./backup/restore.sh <mysql_xxx.sql.gz>
#   会覆盖当前 MYSQL_DATABASE 库内容，谨慎使用！
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_FILE="${1:-}"
if [[ -z "$BACKUP_FILE" ]]; then
    echo "用法: $0 <mysql_xxx.sql.gz>"
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "❌ 文件不存在: $BACKUP_FILE"
    exit 1
fi

if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

if [[ -z "${MYSQL_ROOT_PASSWORD:-}" ]]; then
    echo "❌ 未读到 MYSQL_ROOT_PASSWORD，请先配置 .env"
    exit 1
fi

echo "⚠️  即将把 $BACKUP_FILE 恢复到库 ${MYSQL_DATABASE:-tez_operator}"
echo "    现有数据将被覆盖！"
read -r -p "继续？(yes/N) " confirm
if [[ "$confirm" != "yes" ]]; then
    echo "已取消"
    exit 0
fi

echo "🔄 恢复 MySQL..."
gunzip -c "$BACKUP_FILE" | \
    docker exec -i tez-mysql mysql \
        -uroot -p"${MYSQL_ROOT_PASSWORD}" \
        "${MYSQL_DATABASE:-tez_operator}"

echo "✅ 恢复完成"
