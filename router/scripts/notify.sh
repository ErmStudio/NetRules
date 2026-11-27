#!/bin/sh
# Уведомление в Telegram.
# Настройки в /opt/etc/mihomo/ui.conf: TG_TOKEN, TG_CHAT, TG_NOTIFY
[ -f /opt/etc/mihomo/ui.conf ] && . /opt/etc/mihomo/ui.conf
[ "${TG_NOTIFY:-1}" = "1" ] || exit 0
[ -z "$TG_TOKEN" ] && exit 0
[ -z "$TG_CHAT" ] && exit 0
TEXT="$1"
[ -z "$TEXT" ] && exit 0
API="https://api.telegram.org/bot$TG_TOKEN/sendMessage"

send() {
  /opt/bin/curl -s --max-time 12 -o /tmp/tg.out "$@" \
    -d "chat_id=$TG_CHAT" -d "text=$TEXT" -d "parse_mode=HTML" "$API" 2>/dev/null
  grep -q '"ok":true' /tmp/tg.out 2>/dev/null
}

# 1) через основной прокси mihomo (chromavpn)
send --proxy http://127.0.0.1:7890 && exit 0
# 2) через локальный SOCKS узла ITX (если Xray запущен)
if [ -f /opt/var/run/itx.pid ] && kill -0 "$(cat /opt/var/run/itx.pid 2>/dev/null)" 2>/dev/null; then
  send --socks5-hostname 127.0.0.1:21101 && exit 0
fi
# 3) напрямую (последняя попытка)
send && exit 0
exit 1
