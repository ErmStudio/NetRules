#!/bin/sh
# Проверка одного узла: печатает OK|имя|задержка или BAD|имя|0
[ -f /opt/etc/mihomo/ui.conf ] && . /opt/etc/mihomo/ui.conf
API="${MIHOMO_API:-http://127.0.0.1:9090}"
SECRET="${MIHOMO_SECRET:-change-me}"
R=$(/opt/bin/curl -s --max-time 6 -H "Authorization: Bearer $SECRET" \
  "$API/proxies/$1/delay?url=http%3A%2F%2Fwww.gstatic.com%2Fgenerate_204&timeout=3000" 2>/dev/null)
D=$(echo "$R" | sed -n 's/.*"delay":\([0-9]*\).*/\1/p')
if [ -n "$D" ] && [ "$D" -gt 0 ]; then
  echo "OK|$1|$D"
else
  echo "BAD|$1|0"
fi