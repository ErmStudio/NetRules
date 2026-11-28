#!/bin/sh
# Страховка от «мёртвого закреплённого узла».
# После горячей перезагрузки конфига mihomo иногда восстанавливает в группе PROXY
# узел, которого уже нет в подписке или который не отвечает. Тогда весь прокси-трафик
# (Telegram, звонки, чаты) висит до таймаута, пока watchdog не переключит на AUTO
# через три неудачные пробы — это минуты.
# Здесь: если последняя проверка узла дала задержку 0, узел перепроверяется активно,
# и только при повторном отказе возвращается авто-выбор.
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
print(("MAYBE|" + n) if h[-1].get("delay", 0) == 0 else "OK")
' 2>/dev/null)

NODE=""
case "$RES" in
  "MAYBE|"*)
    NODE=${RES#MAYBE|}
    ENC=$(printf '%s' "$NODE" | sed 's/ /%20/g')
    D=$(/opt/bin/curl -s --max-time 9 -H "$AUTH" \
        "$API/proxies/$ENC/delay?url=http%3A%2F%2Fwww.gstatic.com%2Fgenerate_204&timeout=5000" 2>/dev/null)
    case "$D" in
      *'"delay"'*)
        # узел ответил — предыдущий нулевой замер был случайным, не трогаем
        exit 0 ;;
    esac
    ;;
  *)
    exit 0 ;;
esac

/opt/bin/curl -s -o /dev/null --max-time 8 -X PUT -H "$AUTH" \
  -H "Content-Type: application/json" -d '{"name":"AUTO"}' "$API/proxies/PROXY" 2>/dev/null
echo "$(date '+%F %T') узел ${NODE:-?} не отвечает — переключил PROXY на AUTO" >> $LOG
/bin/sh /opt/etc/mihomo/notify.sh "NetRules: закреплённый узел не отвечает, вернул авто-выбор" >/dev/null 2>&1 &
exit 0
