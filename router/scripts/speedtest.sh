#!/bin/sh
# Замер скорости узлов и закрепление лучшего.
# Метод: качаем до 1.2 с (или 3 МБ), считаем Мбит/с по фактически принятым байтам.
# Настройки (необязательно) в /opt/etc/mihomo/ui.conf:
#   SPEEDTEST_CANDIDATES=10   сколько лучших по пингу проверять
#   SPEEDTEST_CAP=3000000     максимум байт на один замер
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
[ -f /opt/etc/mihomo/ui.conf ] && . /opt/etc/mihomo/ui.conf
API="${MIHOMO_API:-http://127.0.0.1:9090}"
SECRET="${MIHOMO_SECRET:-change-me}"
AUTH="Authorization: Bearer $SECRET"
CAND="${SPEEDTEST_CANDIDATES:-10}"
CAP="${SPEEDTEST_CAP:-3000000}"
URL="https://speed.cloudflare.com/__down?bytes=$CAP"
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

# печатает "байты|секунды" — сколько успели принять за ~1.2 с
measure() {
  R=$(/opt/bin/curl -s -o /dev/null --max-time 1.2 --proxy "http://127.0.0.1:7890" \
      -w "%{size_download} %{time_total}" "$URL" 2>/dev/null)
  B=$(printf '%s' "$R" | awk '{print $1}')
  T=$(printf '%s' "$R" | awk '{print $2}')
  case "$B" in ''|*[!0-9]*) B=0 ;; esac
  case "$T" in ''|*[!0-9.]*) T=0 ;; esac
  echo "$B|$T"
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
  M=$(measure); B=${M%|*}; T=${M#*|}
  echo "$nd $ms $B $T" >> $TMP
done

BEST=""
[ -s $TMP ] && BEST=$(awk 'NF==4 && $4>0 {r=$3/$4; if (r>max) {max=r; b=$1}} END {print b}' $TMP)

# контрольный повтор победителя: просадка в 2.5+ раза -> второй по скорости
if [ -n "$BEST" ]; then
  sel "$BEST"; sleep 1
  M2=$(measure); B2=${M2%|*}; T2=${M2#*|}
  if [ "$B2" -gt 0 ] && [ "$T2" != "0" ]; then
    R1=$(awk -v n="$BEST" '$1==n && $4>0 {print $3/$4}' $TMP | head -1)
    R2=$(awk -v b="$B2" -v t="$T2" 'BEGIN{printf "%.2f", b/t}')
    SLOW=$(awk -v a="$R1" -v b="$R2" 'BEGIN{print (a>0 && b < a/2.5) ? 1 : 0}')
    if [ "$SLOW" = "1" ]; then
      SECOND=$(awk 'NF==4 && $4>0 && $1!="'"$BEST"'" {r=$3/$4; print r, $1}' $TMP | sort -rn | head -1 | awk '{print $2}')
      [ -n "$SECOND" ] && { echo "$(date '+%F %T') $BEST просел, берём $SECOND" >> $LOG; BEST=$SECOND; }
    fi
  fi
  sel "$BEST"
fi

BESTC=""
[ -n "$BEST" ] && BESTC=$(cc "$BEST")

OUTJSON=""
while read -r nd ms b t; do
  [ -z "$nd" ] && continue
  MB=$(awk -v b="$b" -v t="$t" 'BEGIN{ if(t>0) printf "%.1f", (b*8/1000000)/t; else print "0" }')
  C=$(cc "$nd")
  OUTJSON="$OUTJSON${OUTJSON:+,}{\"node\":\"$nd\",\"country\":\"$C\",\"ms\":$ms,\"mbps\":$MB}"
done < $TMP
rm -f $TMP

TS=$(date '+%Y-%m-%d %H:%M')
printf '{"time":"%s","best":"%s","bestcountry":"%s","results":[%s]}\n' "$TS" "$BEST" "$BESTC" "$OUTJSON" > $OUT
echo "$(date '+%F %T') тест: лучший $BEST ($BESTC), кандидатов $CAND, до $CAP Б" >> $LOG

if [ "$(wc -l < $LOG 2>/dev/null || echo 0)" -gt 300 ]; then
  tail -n 80 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
fi
