#!/usr/bin/env bash
# TEZ Operator 数据备份
# 备份内容：MySQL 全库 dump + Redis dump.rdb + 配置（.env / docker-compose.yml / nginx/）
# 用法：./backup/backup.sh
# 环境：BACKUP_DIR / BACKUP_KEEP_DAYS / MYSQL_ROOT_PASSWORD（从 .env 读取）
#
# W1 注意：本脚本已就位但 cron / launchd 暂未启用，W4 末再开
set -euo pipefail

cd "$(dirname "$0")/.."

# 加载 .env（如果存在）
if [[ -f .env ]]; then
    # 仅导入 KEY=VALUE 行，避免奇怪的 shell 注入
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

BACKUP_DIR="${BACKUP_DIR:-./backup/data}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"
DATE=$(date +%Y%m%d_%H%M%S)

if [[ -z "${MYSQL_ROOT_PASSWORD:-}" ]]; then
    echo "❌ 未读到 MYSQL_ROOT_PASSWORD，请先配置 .env"
    exit 1
fi

mkdir -p "$BACKUP_DIR"
echo "📁 备份目标：$BACKUP_DIR"

# 1) MySQL 全库 dump
echo "📦 [1/3] 备份 MySQL..."
docker exec tez-mysql mysqldump \
    -uroot -p"${MYSQL_ROOT_PASSWORD}" \
    --single-transaction --quick --routines --triggers \
    "${MYSQL_DATABASE:-tez_operator}" 2>/dev/null | \
    gzip > "${BACKUP_DIR}/mysql_${DATE}.sql.gz"

# 2) Redis BGSAVE → 拷贝 dump.rdb
echo "📦 [2/3] 备份 Redis..."
docker exec tez-redis redis-cli BGSAVE > /dev/null
sleep 3
if [[ -f ./data/redis/dump.rdb ]]; then
    cp ./data/redis/dump.rdb "${BACKUP_DIR}/redis_${DATE}.rdb"
else
    echo "⚠️  ./data/redis/dump.rdb 不存在，跳过 Redis 备份"
fi

# 3) 配置文件
echo "📦 [3/3] 备份配置..."
tar -czf "${BACKUP_DIR}/config_${DATE}.tar.gz" \
    .env docker-compose.yml nginx/ 2>/dev/null || true

# 4) 清理旧文件
echo "🧹 清理 ${KEEP_DAYS} 天前的旧备份..."
find "$BACKUP_DIR" -maxdepth 1 -type f \( -name "mysql_*.sql.gz" -o -name "redis_*.rdb" -o -name "config_*.tar.gz" \) \
    -mtime +"${KEEP_DAYS}" -print -delete 2>/dev/null || true

echo "✅ 备份完成"
ls -lh "${BACKUP_DIR}" | tail -10
