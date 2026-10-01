#!/usr/bin/env bash
# Plove 部署自检。**在 VPS 上跑**。
#
# 用法：
#     BASE_URL=https://plove.example.com ADMIN_TOKEN=xxx ./check.sh
#
# 不带 ADMIN_TOKEN 也能跑（会跳过后台那两项）。
# 退出码 0 = 全过；非 0 = 有失败项（可以塞进 CI 或部署脚本里当门禁）。

set -uo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"
REPO_DIR="${REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"

# 用仓库里那个 venv 的解释器；找不到就退回系统 python（只用于打印 JSON）。
# Linux 是 bin/python，Windows（Git Bash）是 Scripts/python.exe ——
# 同一份脚本在本机也能跑，不用为了自检专门留一台服务器。
PY="$REPO_DIR/backend/.venv/bin/python"
[[ -x "$PY" ]] || PY="$REPO_DIR/backend/.venv/Scripts/python.exe"
[[ -x "$PY" ]] || PY="$(command -v python3 || command -v python || echo python3)"

PASS=0
FAIL=0

ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; PASS=$((PASS + 1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAIL=$((FAIL + 1)); }
info() { printf '\n== %s ==\n' "$1"; }

# 只取状态码
code() { curl -s -o /dev/null -m 30 -w '%{http_code}' "$@" 2>/dev/null || echo "000"; }

info "1. 健康检查（应用活着吗）"
BODY="$(curl -s -m 10 "$BASE_URL/api/v1/health" || true)"
if [[ "$BODY" == *'"ok":true'* && "$BODY" == *'"status":"ok"'* ]]; then
    ok "GET /api/v1/health -> ok:true"
else
    bad "GET /api/v1/health 没返回预期信封：${BODY:0:200}"
fi

info "2. 信封形状（错误也要是 JSON，不能是 HTML）"
NOPE="$(curl -s -m 10 "$BASE_URL/api/v1/definitely-not-here" || true)"
if [[ "$NOPE" == *'"ok":false'* && "$NOPE" == *"NOT_FOUND"* ]]; then
    ok "不存在的路径 -> 统一错误信封"
else
    bad "不存在的路径没走信封（拿到的是 HTML？）：${NOPE:0:120}"
fi

info "3. 门是关着的（没凭证进不来）"
[[ "$(code "$BASE_URL/api/v1/sites")" == "401" ]] \
    && ok "GET /api/v1/sites 无令牌 -> 401" \
    || bad "GET /api/v1/sites 无令牌没有被拦住"

# 两种都是"拦住了"，含义不同：
#   401 = 配了令牌但没带（或带错）
#   403 = 压根没配令牌，后台整体拒绝服务
# 200 才是灾难 —— 后台没设防。
ADMIN_GUARD="$(code "$BASE_URL/api/v1/admin/status")"
if [[ "$ADMIN_GUARD" == "401" || "$ADMIN_GUARD" == "403" ]]; then
    ok "GET /api/v1/admin/status 无令牌 -> $ADMIN_GUARD（没被放进来）"
else
    bad "后台接口无令牌得到了 $ADMIN_GUARD —— 危险：后台没设防（检查 PLOVE_ADMIN_TOKEN）"
fi

info "4. 后台接口"
if [[ -z "$ADMIN_TOKEN" ]]; then
    printf '  SKIP  没给 ADMIN_TOKEN\n'
else
    [[ "$(code -H "X-Admin-Token: wrong" "$BASE_URL/api/v1/admin/status")" == "401" ]] \
        && ok "后台：错令牌 -> 401" \
        || bad "后台：错令牌没被拦住"

    ADMIN_BODY="$(curl -s -m 15 -H "X-Admin-Token: $ADMIN_TOKEN" "$BASE_URL/api/v1/admin/status" || true)"
    if [[ "$ADMIN_BODY" == *'"ok":true'* ]]; then
        ok "后台：正确令牌 -> 200"
        # 把关键状态顺手打出来，省得再去 Swagger 点一遍
        echo "$ADMIN_BODY" | "$PY" -c "
import json, sys
data = json.load(sys.stdin)['data']
print('        环境    :', data['env'])
print('        缓存    : %d 条 / 命中 %d / 未命中 %d' % (data['cache']['size'], data['cache']['hits'], data['cache']['misses']))
w = data['warmup']
print('        预热    : enabled=%s running=%s 上次=%s' % (w['enabled'], w['running'], w.get('last_finished_at')))
for site in data['sites']:
    print('        源 %-8s state=%s failures=%d' % (site['site'], site['state'], site['failures']))
" 2>/dev/null || true
    else
        bad "后台：正确令牌也没通过：${ADMIN_BODY:0:200}"
    fi
fi

info "5. 源站认不认这台机器（**最容易翻车的一步**）"
# 不走应用，直接用爬虫本体打源站。这样能把"源站封机房 IP"和"我们的代码有问题"
# 这两件事分开：这里失败 = 源站不认这台机器；这里成功而接口失败 = 我们的问题。
CR="$(ls -d "$REPO_DIR"/crawler 2>/dev/null || true)"
if [[ -z "$CR" || ! -x "$PY" ]]; then
    printf '  SKIP  找不到 %s 或 %s\n' "$CR" "$PY"
else
    for SITE in ai2048 ncat21; do
        [[ -f "$CR/sites/$SITE.py" ]] || continue
        START=$(date +%s.%N)
        OUT="$("$PY" "$CR/sites/$SITE.py" home 2>/dev/null | head -c 400 || true)"
        ELAPSED=$(awk -v a="$START" -v b="$(date +%s.%N)" 'BEGIN{printf "%.1f", b-a}')
        if [[ "$OUT" == *'"ok": true'* || "$OUT" == *'"ok":true'* ]]; then
            ok "$SITE home 可用（${ELAPSED}s）"
            # 本地量过 ncat21 约 9 秒。这里明显更慢的话，PLOVE_CRAWLER_TIMEOUT 要跟着调大。
            awk -v t="$ELAPSED" 'BEGIN{ if (t+0 > 15) print "        ⚠️ 比开发机上慢很多，建议把 PLOVE_CRAWLER_TIMEOUT 调大" }'
        else
            bad "$SITE home 失败：${OUT:0:160}"
            echo "        → 很可能是源站对机房 IP 另眼相待。先确认：curl -sI https://<源站域名>"
        fi
    done
fi

printf '\n----------------------------------------\n'
printf '通过 %d 项，失败 %d 项\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
