#!/usr/bin/env bash
# Plove 数据库备份。
#
# 用法：
#     sudo -u plove bash deploy/backup.sh
# 定时（crontab -u plove -e）：
#     10 4 * * * /bin/bash /opt/plove/deploy/backup.sh >> /var/log/plove-backup.log 2>&1
#
# 环境变量（都有默认值，一般不用设）：
#     BACKUP_DIR   备份放哪      默认 /var/backups/plove
#     KEEP         保留多少份    默认 14
#     ENV_FILE     配置从哪读    默认 /opt/plove/backend/.env

set -uo pipefail

ENV_FILE="${ENV_FILE:-/opt/plove/backend/.env}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/plove}"
KEEP="${KEEP:-14}"

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*"; }
die() { printf '[%s] 失败：%s\n' "$(date '+%F %T')" "$*" >&2; exit 1; }

[[ -r "$ENV_FILE" ]] || die "读不到 $ENV_FILE"

# 从 .env 里取出连接串。**不 source 那个文件** —— 它是 ini 风格的，
# 里面还有别的变量，source 进来会污染环境，而且注释里的字符可能被解释成命令。
URL="$(grep -E '^PLOVE_DATABASE_URL=' "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
[[ -n "$URL" ]] || die "$ENV_FILE 里没有 PLOVE_DATABASE_URL"

# 只处理 MySQL。本地 SQLite 不需要这种备份（拷一个文件就行）。
case "$URL" in
    mysql*) ;;
    *)   log "数据库不是 MySQL（$URL 的前缀），跳过"; exit 0 ;;
esac

# mysql+pymysql://用户:密码@主机:端口/库名?charset=...
REST="${URL#mysql+pymysql://}"
CREDS="${REST%%@*}"
HOSTPART="${REST#*@}"
DB="${HOSTPART%%\?*}"
DB="${DB##*/}"

DB_USER="${CREDS%%:*}"
DB_PASS="${CREDS#*:}"
DB_HOST_PORT="${HOSTPART%%/*}"
DB_HOST="${DB_HOST_PORT%%:*}"
DB_PORT="${DB_HOST_PORT##*:}"
[[ "$DB_PORT" == "$DB_HOST" ]] && DB_PORT=3306

command -v mysqldump >/dev/null 2>&1 || die "没有 mysqldump（apt install mysql-client）"

mkdir -p "$BACKUP_DIR" || die "建不了 $BACKUP_DIR"
STAMP="$(date '+%Y%m%d-%H%M%S')"
OUT="$BACKUP_DIR/$DB-$STAMP.sql.gz"

# 密码走环境变量而不是命令行参数：命令行参数在 ps 里对所有人可见。
# --single-transaction：不锁表（InnoDB），备份时线上照常读写。
if ! MYSQL_PWD="$DB_PASS" mysqldump \
        --host="$DB_HOST" --port="$DB_PORT" --user="$DB_USER" \
        --single-transaction --quick --routines \
        --default-character-set=utf8mb4 \
        "$DB" 2>/tmp/plove-backup.err | gzip > "$OUT"; then
    rm -f "$OUT"
    die "mysqldump 失败：$(head -3 /tmp/plove-backup.err)"
fi

SIZE="$(du -h "$OUT" | cut -f1)"
log "备份完成：$OUT（$SIZE）"

# 空文件或极小文件说明有问题（正常的库至少几百字节）。这种备份留着反而骗人。
BYTES="$(stat -c %s "$OUT" 2>/dev/null || echo 0)"
if [[ "$BYTES" -lt 200 ]]; then
    log "⚠️ 备份只有 ${BYTES} 字节，可疑。请人工确认：gunzip -c $OUT | head"
fi

# 只留最近 KEEP 份
COUNT="$(find "$BACKUP_DIR" -maxdepth 1 -name "$DB-*.sql.gz" | wc -l)"
if [[ "$COUNT" -gt "$KEEP" ]]; then
    # shellcheck disable=SC2012
    ls -1t "$BACKUP_DIR"/"$DB"-*.sql.gz | tail -n +$((KEEP + 1)) | while read -r old; do
        rm -f "$old" && log "清掉旧备份：$(basename "$old")"
    done
fi

log "当前保留 $(find "$BACKUP_DIR" -maxdepth 1 -name "$DB-*.sql.gz" | wc -l) 份"
