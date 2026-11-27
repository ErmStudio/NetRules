#!/bin/sh
# Снапшот счётчиков mihomo каждые 15 минут → приращение в журнал.
# Переживает рестарты: если счётчик уменьшился, значит процесс перезапустился
# и текущее значение и есть накопленное с момента старта.
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
[ -f /opt/etc/mihomo/ui.conf ] && . /opt/etc/mihomo/ui.conf
API="${MIHOMO_API:-http://127.0.0.1:9090}"
SECRET="${MIHOMO_SECRET:-change-me}"
BASE=/opt/etc/mihomo
STATE=$BASE/.traffic_state
JOURNAL=$BASE/traffic.csv

C=$(/opt/bin/curl -s --max-time 6 -H "Authorization: Bearer $SECRET" "$API/connections" 2>/dev/null)
DL=$(printf '%s' "$C" | sed -n 's/.*"downloadTotal":\([0-9]*\).*/\1/p' | head -1)
UL=$(printf '%s' "$C" | sed -n 's/.*"uploadTotal":\([0-9]*\).*/\1/p' | head -1)
[ -z "$DL" ] && exit 0
[ -z "$UL" ] && UL=0

PDL=0; PUL=0
FIRST=0
PREV=$(cat $STATE 2>/dev/null)
if [ -z "$PREV" ]; then FIRST=1; fi
if [ -n "$PREV" ]; then
  PDL=${PREV%|*}
  PUL=${PREV#*|}
  case "$PDL" in ''|*[!0-9]*) PDL=0 ;; esac
  case "$PUL" in ''|*[!0-9]*) PUL=0 ;; esac
fi

# если счётчик меньше предыдущего — mihomo перезапускался
if [ "$DL" -lt "$PDL" ]; then DDL=$DL; else DDL=$((DL - PDL)); fi
if [ "$UL" -lt "$PUL" ]; then DUL=$UL; else DUL=$((UL - PUL)); fi
[ "$DDL" -lt 0 ] && DDL=0
[ "$DUL" -lt 0 ] && DUL=0

echo "$DL|$UL" > $STATE
# первый запуск: только запоминаем базу, чтобы не записать весь накопленный счётчик в один день
[ "$FIRST" = "1" ] && exit 0
[ "$DDL" -eq 0 ] && [ "$DUL" -eq 0 ] && exit 0
echo "$(date +%F),$DDL,$DUL" >> $JOURNAL

# ротация: держим последние ~90 дней
if [ "$(wc -l < $JOURNAL 2>/dev/null || echo 0)" -gt 12000 ]; then
  tail -n 8000 $JOURNAL > $JOURNAL.tmp && mv $JOURNAL.tmp $JOURNAL
fi
