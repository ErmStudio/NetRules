#!/bin/sh
# Замер скорости топ-узлов по задержке, закрепление лучшего.
# Результат: /opt/etc/mihomo/speedtest.json
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
[ -f /opt/etc/mihomo/ui.conf ] && . /opt/etc/mihomo/ui.conf
API="${MIHOMO_API:-http://127.0.0.1:9090}"
SECRET="${MIHOMO_SECRET:-change-me}"
AUTH="Authorization: Bearer $SECRET"
SPEEDURL="https://speed.cloudflare.com/__down?bytes=2000000"
OUT=/opt/etc/mihomo/speedtest.json
CT=/opt/etc/mihomo/countries.txt
LOG=/opt/var/log/mihomo-speedtest.log
TMP=/tmp/mh-speed.txt

sel() {
  /opt/bin/curl -s -o /dev/null --max-time 8 -X PUT \
    -H "Authorization: Bearer $SECRET" -H "Content-Type: application/json" \
    -d "{\"name\":\"$1\"}" "$API/proxies/PROXY" 2>/dev/null
}

cc() { awk -F'|' -v n="$1" '$1==n{print $2; exit}' $CT 2>/dev/null; }

MAP=$(/opt/bin/wget -q -O - --timeout=20 --header="$AUTH" \
  "$API/group/AUTO/delay?url=http%3A%2F%2Fwww.gstatic.com%2Fgenerate_204&timeout=3000" 2>/dev/null)
LIST=$(printf '%s' "$MAP" | tr ',' '\n' | sed 's/[{}"]//g;s/^ *//;s/ *$//' \
  | awk -F: 'NF==2 {print $2" "$1}' | sort -n | head -5)

[ -z "$LIST" ] && { echo "$(date '+%F %T') нет данных о задержках" >> $LOG; exit 1; }

: > $TMP
printf '%s\n' "$LIST" | while read -r ms nd; do
  [ -z "$nd" ] && continue
  sel "$nd"; sleep 1
  T=$(/opt/bin/curl -s -o /dev/null --max-time 30 --proxy "http://127.0.0.1:7890" \
        -w "%{time_total}" "$SPEEDURL" 2>/dev/null)
  [ -z "$T" ] && T=99
  echo "$nd $T" >> $TMP
done

BEST=""
[ -s $TMP ] && BEST=$(awk 'NR==1 || $2<min {min=$2; b=$1} END {print b}' $TMP)
BESTC=""
[ -n "$BEST" ] && { BESTC=$(cc "$BEST"); sel "$BEST"; }

OUTJSON=""
while read -r nd t; do
  [ -z "$nd" ] && continue
  MB=$(awk -v t="$t" 'BEGIN{ if(t>0) printf "%.1f", 16/t; else print "0" }')
  C=$(cc "$nd")
  OUTJSON="$OUTJSON${OUTJSON:+,}{\"node\":\"$nd\",\"country\":\"$C\",\"sec\":$t,\"mbps\":$MB}"
done < $TMP
rm -f $TMP

TS=$(date '+%Y-%m-%d %H:%M')
printf '{"time":"%s","best":"%s","bestcountry":"%s","results":[%s]}\n' "$TS" "$BEST" "$BESTC" "$OUTJSON" > $OUT
echo "$(date '+%F %T') тест: лучший $BEST ($BESTC)" >> $LOG

if [ "$(wc -l < $LOG 2>/dev/null || echo 0)" -gt 200 ]; then
  tail -n 60 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
fi
