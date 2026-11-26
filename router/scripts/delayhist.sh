#!/bin/sh
# Добавляет точку истории задержки текущего узла.
# Файл: /opt/etc/mihomo/delay_history  (строки "epoch|ms")
[ -f /opt/etc/mihomo/ui.conf ] && . /opt/etc/mihomo/ui.conf
API="${MIHOMO_API:-http://127.0.0.1:9090}"
SECRET="${MIHOMO_SECRET:-change-me}"
HIST=/opt/etc/mihomo/delay_history

R=$(/opt/bin/curl -s --max-time 6 -H "Authorization: Bearer $SECRET" \
  "$API/proxies/AUTO/delay?url=http%3A%2F%2Fwww.gstatic.com%2Fgenerate_204&timeout=4000" 2>/dev/null)
D=$(echo "$R" | sed -n 's/.*"delay":\([0-9]*\).*/\1/p')
[ -z "$D" ] && exit 0
echo "$(date +%s)|$D" >> $HIST
if [ "$(wc -l < $HIST 2>/dev/null || echo 0)" -gt 400 ]; then
  tail -n 200 $HIST > $HIST.tmp && mv $HIST.tmp $HIST
fi
