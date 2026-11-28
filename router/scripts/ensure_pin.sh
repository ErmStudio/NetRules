#!/bin/sh
# Страховка от «мёртвого закреплённого узла».
# После горячей перезагрузки конфига mihomo иногда восстанавливает в группе PROXY
# узел, которого уже нет в подписке или который не отвечает. Тогда весь прокси-трафик
# (Telegram, ChatGPT, Telegram-звонки) висит до таймаута, пока watchdog не переключит
# на AUTO через три неудачные пробы — это минуты.
# Здесь проверка занимает секунды: если выбранный узел помечен как неживой,
# сразу возвращаем авто-выбор.
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
[ -f /opt/etc/mihomo/ui.conf ] && . /opt/etc/mihomo/ui.conf
AUTH="Authorization: Bearer ${MIHOMO_SECRET:-change-me}"
API="${MIHOMO_API:-http://127.0.0.1:9090}"
LOG=/opt/var/log/mihomo-watchdog.log

RES=$(/opt/bin/curl -s --max-time 8 -H "$AUTH" "$API/proxies" 2>/dev/null | /opt/bin/python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)["proxies"]
except Exception:
    raise SystemExit
n = (d.get("PROXY") or {}).get("now") or ""
if n in ("", "AUTO", "ITX", "ITXFAST"):
    print("SKIP")
    raise SystemExit
h = (d.get(n) or {}).get("history") or []
if not h:
    # сразу после перезагрузки конфига истории проверок ещё нет —
    # это не признак смерти узла, не трогаем
    print("SKIP")
    raise SystemExit
print("DEAD" if h[-1].get("delay", 0) == 0 else "OK")
' 2>/dev/null)

[ "$RES" = "DEAD" ] || exit 0
/opt/bin/curl -s -o /dev/null --max-time 8 -X PUT -H "$AUTH" \
  -H "Content-Type: application/json" -d '{"name":"AUTO"}' "$API/proxies/PROXY" 2>/dev/null
echo "$(date '+%F %T') закреплённый узел не отвечает — переключил PROXY на AUTO" >> $LOG
/bin/sh /opt/etc/mihomo/notify.sh "NetRules: закреплённый узел не отвечает, вернул авто-выбор" >/dev/null 2>&1 &
exit 0
