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

# 安全读取 .env 中单个 KEY=VALUE；只解析值，不执行文件内容。
get_env() {
    local key="$1"
    local line value

    line="$(grep -E "^${key}=" .env 2>/dev/null | tail -n 1 || true)"
    [[ -n "$line" ]] || return 0

    value="${line#*=}"
    if [[ ${#value} -ge 2 ]]; then
        if [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]] || \
            [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]]; then
            value="${value:1:${#value}-2}"
        fi
    fi
    printf '%s' "$value"
}

MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-$(get_env MYSQL_ROOT_PASSWORD)}"
MYSQL_DATABASE="${MYSQL_DATABASE:-$(get_env MYSQL_DATABASE)}"
MYSQL_DATABASE="${MYSQL_DATABASE:-tez_operator}"

if [[ -z "${MYSQL_ROOT_PASSWORD:-}" ]]; then
    echo "❌ 未读到 MYSQL_ROOT_PASSWORD，请先配置 .env"
    exit 1
fi

echo "⚠️  即将把 $BACKUP_FILE 恢复到库 ${MYSQL_DATABASE}"
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
        "${MYSQL_DATABASE}"

echo "✅ 恢复完成"
