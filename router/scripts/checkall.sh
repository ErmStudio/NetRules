#!/bin/sh
# Полная проверка всех узлов: сколько живых и мёртвых.
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
HOME="${HOME:-/root}"
export HOME
[ -f /opt/etc/mihomo/ui.conf ] && . /opt/etc/mihomo/ui.conf
API="${MIHOMO_API:-http://127.0.0.1:9090}"
SECRET="${MIHOMO_SECRET:-change-me}"
AUTH="Authorization: Bearer $SECRET"
OUT=/opt/etc/mihomo/nodes_health.json
CT=/opt/etc/mihomo/countries.txt
LOG=/opt/var/log/mihomo-speedtest.log
LOCK=/tmp/mh-checking
TMP=/tmp/mh-nodes.txt
RES=/tmp/mh-health.txt

# lock с отметкой времени, чтобы убитый прогон не блокировал проверки навсегда
if [ -f "$LOCK" ]; then
  TS=$(cat "$LOCK" 2>/dev/null)
  case "$TS" in ''|*[!0-9]*) TS=0 ;; esac
  if [ "$TS" -gt 0 ] && [ $(( $(date +%s) - TS )) -lt 1800 ]; then
    echo "$(date '+%F %T') проверка узлов уже идёт, пропуск" >> $LOG
    exit 0
  fi
  echo "$(date '+%F %T') снят зависший lock проверки" >> $LOG
  rm -f "$LOCK"
fi
date +%s > "$LOCK"
trap 'rm -f $LOCK' EXIT

i=0
while [ $i -lt 20 ]; do
  netstat -ltn 2>/dev/null | grep -q ":7892" && break
  sleep 1; i=$((i+1))
done
V=$(/opt/bin/curl -s --max-time 5 -H "$AUTH" "$API/version" 2>/dev/null)
case "$V" in
  *version*) ;;
  *) echo "$(date "+%F %T") проверка отменена: mihomo не готов" >> $LOG; exit 2 ;;
esac

/opt/bin/curl -s --max-time 15 -H "$AUTH" "$API/proxies" \
  | /opt/bin/python3 -c "
import sys, json
d = json.load(sys.stdin).get('proxies', {})
skip = ('Selector','URLTest','Direct','Reject','RejectDrop','Pass','Compatible')
for k, v in d.items():
    if v.get('type') not in skip:
        print(k)
" > $TMP

echo "$(date '+%F %T') старт проверки узлов" >> $LOG
TOT=$(wc -l < $TMP | tr -d ' ')
[ "$TOT" -eq 0 ] && { echo "нет узлов" >> $LOG; exit 1; }

: > $RES
xargs -I{} -P 16 /opt/etc/mihomo/check1.sh {} < $TMP >> $RES 2>/dev/null

ALIVE=$(grep -c '^OK|' $RES)
DEAD=$(grep -c '^BAD|' $RES)
if [ "$ALIVE" -eq 0 ]; then
  # mihomo мог только что стартовать — даём ему паузу и повторяем один раз
  sleep 6
  : > $RES
  xargs -I{} -P 16 /opt/etc/mihomo/check1.sh {} < $TMP >> $RES 2>/dev/null
  ALIVE=$(grep -c '^OK|' $RES)
  DEAD=$(grep -c '^BAD|' $RES)
  echo "$(date '+%F %T') повторная проверка: живых $ALIVE из $TOT" >> $LOG
fi
if [ "$ALIVE" -eq 0 ]; then
  echo "$(date '+%F %T') проверка не удалась: ни один узел не ответил (mihomo занят?)" >> $LOG
  rm -f $TMP $RES
  exit 2
fi
DLIST=$(grep '^BAD|' $RES | cut -d'|' -f2 | head -15 | /opt/bin/python3 -c "
import sys, json
items = [l.strip() for l in sys.stdin if l.strip()]
print(json.dumps(items, ensure_ascii=False))
")
TS=$(date '+%Y-%m-%d %H:%M')
printf '{"time":"%s","total":%s,"alive":%s,"dead":%s,"deadlist":%s}\n' \
  "$TS" "$TOT" "$ALIVE" "$DEAD" "$DLIST" > $OUT
echo "$(date '+%F %T') проверка узлов: живых $ALIVE из $TOT" >> $LOG

rm -f $TMP $RES
if [ "$(wc -l < $LOG 2>/dev/null || echo 0)" -gt 300 ]; then
  tail -n 80 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
fi
