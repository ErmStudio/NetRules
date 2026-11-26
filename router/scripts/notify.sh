#!/bin/sh
# Уведомление в Telegram. Настройки в /opt/etc/mihomo/ui.conf:
#   TG_TOKEN="123456:AA..."   TG_CHAT="123456789"
[ -f /opt/etc/mihomo/ui.conf ] && . /opt/etc/mihomo/ui.conf
[ -z "$TG_TOKEN" ] && exit 0
[ -z "$TG_CHAT" ] && exit 0
TEXT="$1"
[ -z "$TEXT" ] && exit 0
/opt/bin/curl -s --max-time 10 -o /dev/null \
  -d "chat_id=$TG_CHAT" -d "text=$TEXT" -d "parse_mode=HTML" \
  "https://api.telegram.org/bot$TG_TOKEN/sendMessage" 2>/dev/null
