#!/bin/sh
# Замер скорости узлов и закрепление лучшего.
# Настройки (необязательно) в /opt/etc/mihomo/ui.conf:
#   SPEEDTEST_CANDIDATES=10     сколько лучших по пингу проверять
#   SPEEDTEST_BYTES=1500000     размер тестового файла (байт)
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
[ -f /opt/etc/mihomo/ui.conf ] && . /opt/etc/mihomo/ui.conf
API="${MIHOMO_API:-http://127.0.0.1:9090}"
SECRET="${MIHOMO_SECRET:-change-me}"
AUTH="Authorization: Bearer $SECRET"
CAND="${SPEEDTEST_CANDIDATES:-10}"
BYTES="${SPEEDTEST_BYTES:-1500000}"
SPEEDURL="https://speed.cloudflare.com/__down?bytes=$BYTES"
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
t_of() {
  /opt/bin/curl -s -o /dev/null --max-time 30 --proxy "http://127.0.0.1:7890" \
    -w "%{time_total}" "$SPEEDURL" 2>/dev/null
}

MAP=$(/opt/bin/wget -q -O - --timeout=20 --header="$AUTH" \
  "$API/group/AUTO/delay?url=http%3A%2F%2Fwww.gstatic.com%2Fgenerate_204&timeout=3000" 2>/dev/null)
LIST=$(printf '%s' "$MAP" | tr ',' '\n' | sed 's/[{}"]//g;s/^ *//;s/ *$//' \
  | awk -F: 'NF==2 && $2>0 && $2<800 {print $2" "$1}' | sort -n | head -"$CAND")

[ -z "$LIST" ] && { echo "$(date '+%F %T') нет данных о задержках" >> $LOG; exit 1; }

: > $TMP
printf '%s\n' "$LIST" | while read -r ms nd; do
  [ -z "$nd" ] && continue
  sel "$nd"; sleep 1
  T=$(t_of); [ -z "$T" ] && T=99
  echo "$nd $T" >> $TMP
done

BEST=""
[ -s $TMP ] && BEST=$(awk 'NR==1 || $2<min {min=$2; b=$1} END {print b}' $TMP)

# подтверждение: перепроверяем победителя, при явном ухудшении берём второго
if [ -n "$BEST" ]; then
  sel "$BEST"; sleep 1
  T2=$(t_of); [ -z "$T2" ] && T2=99
  T1=$(awk -v n="$BEST" '$1==n{print $2; exit}' $TMP)
  awk -v a="$T1" -v b="$T2" 'BEGIN{exit !(b > a*2.5)}' && {
    SECOND=$(sort -k2 -n $TMP | awk 'NR==2{print $1}')
    if [ -n "$SECOND" ]; then
      echo "$(date '+%F %T') $BEST просел ($T1 → $T2), берём $SECOND" >> $LOG
      BEST=$SECOND
    fi
  }
  sel "$BEST"
fi

BESTC=""
[ -n "$BEST" ] && BESTC=$(cc "$BEST")

OUTJSON=""
while read -r nd t; do
  [ -z "$nd" ] && continue
  MB=$(awk -v t="$t" -v b="$BYTES" 'BEGIN{ if(t>0) printf "%.1f", (b*8/1000000)/t; else print "0" }')
  C=$(cc "$nd")
  OUTJSON="$OUTJSON${OUTJSON:+,}{\"node\":\"$nd\",\"country\":\"$C\",\"sec\":$t,\"mbps\":$MB}"
done < $TMP
rm -f $TMP

TS=$(date '+%Y-%m-%d %H:%M')
printf '{"time":"%s","best":"%s","bestcountry":"%s","results":[%s]}\n' "$TS" "$BEST" "$BESTC" "$OUTJSON" > $OUT
echo "$(date '+%F %T') тест: лучший $BEST ($BESTC), кандидатов $CAND по $BYTES Б" >> $LOG

if [ "$(wc -l < $LOG 2>/dev/null || echo 0)" -gt 300 ]; then
  tail -n 80 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
fi
