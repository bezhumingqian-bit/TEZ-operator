#!/usr/bin/env bash
# scripts/pre-commit-check.sh
# TEZ Operator - Git pre-commit 敏感数据扫描钩子
# 触发：git commit 前自动扫描 staged 文件,命中即拒绝
# 安装：./scripts/install-hooks.sh

set -euo pipefail

# 颜色
RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m'

log() { printf "${1}${2}${NC}\n"; }

# ============================================================
# 敏感数据模式（与 docs/16-数据安全规则.md 同步维护）
# ============================================================
declare -a PATTERNS=(
    # 真实固资号格式（TYSV + 8 位数字字母混合，且必须含字母+数字混合避免误伤）
    # 例如 TYSV20061X2A，但允许 TYSV00000001 这种全数字占位（占位无字母混合）
    'TYSV[0-9]{4}[0-9A-Z]*[A-Z][0-9A-Z]+'

    # 内部网段
    '9\.200\.'
    '100\.106\.'

    # 真实接口人英文名（已知样本）
    'peersli|matttyzhang|sagelxxiao|brivenchen|xiancondeng|jackxtjing|wbrucewang'

    # 真实机房名
    '上海茶'
    '沈阳边缘'

    # 真实客户名（按全词或上下文）
    '虎牙|\bYY\b|字节|小鹿|搜狐|声网'

    # 真实云地域 / Zone 名
    'ap-shanghai|ap-guangzhou|ap-beijing'

    # 真实 AppId / 计费标签 / 模块
    '1300840453'
    'p_edgezone'

    # 凭据关键字（绝不入仓）
    'AppSecret\s*=\s*[A-Za-z0-9]+'
    'access_token\s*=\s*[A-Za-z0-9]+'
    'refresh_token\s*=\s*[A-Za-z0-9]+'
    'BEGIN (RSA |EC )?PRIVATE KEY'
)

# 白名单文件（这些文件会跳过扫描）
declare -a WHITELIST_FILES=(
    "scripts/pre-commit-check.sh"        # 自身（含模式定义）
    "scripts/install-hooks.sh"
)

# ============================================================
# 主逻辑
# ============================================================

# 1. 取得 staged 文件列表
STAGED=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || true)

if [[ -z "$STAGED" ]]; then
    exit 0  # 无 staged 文件,放行
fi

log "$GREEN" "🔍 扫描 staged 文件中的敏感数据..."

VIOLATION_COUNT=0
VIOLATION_DETAILS=""

# 2. 逐文件扫描
while IFS= read -r file; do
    [[ -z "$file" || ! -f "$file" ]] && continue

    # 白名单跳过
    skip=0
    for w in "${WHITELIST_FILES[@]}"; do
        if [[ "$file" == "$w" ]]; then
            skip=1
            break
        fi
    done
    [[ $skip -eq 1 ]] && continue

    # 跳过二进制
    if file --mime "$file" 2>/dev/null | grep -qE 'charset=binary'; then
        continue
    fi

    # 对每个模式扫描 staged 内容
    for pattern in "${PATTERNS[@]}"; do
        # git show :file 拿 staged 内容,而不是工作区
        matches=$(git show ":$file" 2>/dev/null | grep -nE "$pattern" || true)
        if [[ -n "$matches" ]]; then
            VIOLATION_COUNT=$((VIOLATION_COUNT + 1))
            VIOLATION_DETAILS+="\n${RED}❌ ${file}${NC}: 命中模式 ${YELLOW}${pattern}${NC}\n"
            VIOLATION_DETAILS+="$(echo "$matches" | head -3 | sed 's/^/   /')\n"
        fi
    done
done <<< "$STAGED"

# 3. 决策
if [[ $VIOLATION_COUNT -gt 0 ]]; then
    log "$RED" "═══════════════════════════════════════════════════════"
    log "$RED" "🚨 提交被拒绝：检测到 ${VIOLATION_COUNT} 处敏感数据"
    log "$RED" "═══════════════════════════════════════════════════════"
    printf '%b' "$VIOLATION_DETAILS"
    log "$YELLOW" "\n📖 参考：.codebuddy/teams/tez-ops/docs/16-数据安全规则.md"
    log "$YELLOW" "💡 修复后重新 git add 并 git commit"
    log "$YELLOW" "🔓 紧急绕过(慎用)：git commit --no-verify"
    exit 1
fi

log "$GREEN" "✅ 敏感数据扫描通过，可以提交"
exit 0
