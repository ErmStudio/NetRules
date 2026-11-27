#!/bin/sh
# Мягкий контроль Gemini: проверяем только текущий узел ITX.
# Недоступен → заморозка на 6 часов и поиск замены (не более 3 попыток).
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
[ -f /opt/etc/mihomo/ui.conf ] && . /opt/etc/mihomo/ui.conf
S="${MIHOMO_SECRET:-change-me}"
API="${MIHOMO_API:-http://127.0.0.1:9090}"
AUTH="Authorization: Bearer $S"
BASE=/opt/etc/itx
STATE=$BASE/gemini_state.txt
LOG=/opt/var/log/itx.log
FROZEN=$BASE/gemini_frozen.txt
NODES=$BASE/nodes.txt

say() { echo "$(date '+%F %T') $1" >> $LOG; }

[ -f /opt/var/run/itx.pid ] && kill -0 "$(cat /opt/var/run/itx.pid 2>/dev/null)" 2>/dev/null || exit 0
[ -f "$NODES" ] || exit 0

CUR=$(/opt/bin/curl -s --max-time 6 -H "$AUTH" "$API/proxies/ITX" 2>/dev/null | sed -n 's/.*"now":"\([^"]*\)".*/\1/p')
[ -z "$CUR" ] && { say "gemini: не удалось узнать текущий узел"; exit 0; }

port_of() {
  awk -F'|' -v n="$1" '$1==n{print $2; exit}' "$NODES" 2>/dev/null
}

PORT=$(port_of "$CUR")
[ -z "$PORT" ] && { say "gemini: узел $CUR не найден в списке"; exit 0; }

RES=$(/opt/etc/itx/gemini_check.sh "$PORT")
say "gemini: текущий узел $CUR → $RES"
echo "$(date '+%F %T')|$CUR|$RES" > "$STATE"
[ "$RES" = "available" ] && exit 0

NOW=$(date +%s)
echo "$CUR|$((NOW + 21600))" >> "$FROZEN"
say "gemini: $CUR заморожен на 6 часов"

TRIES=0
# порядок перебора: сначала самые быстрые узлы ITX по данным последнего замера
ORDER=$(/opt/bin/python3 -c "
import json
try:
    d = json.load(open('/opt/etc/mihomo/speedtest.json'))
except Exception:
    raise SystemExit
rows = [(x.get('mbps', 0), x.get('node', '')) for x in d.get('results', []) if x.get('src') == 'itx']
rows.sort(reverse=True)
for _, n in rows:
    print(n)
" 2>/dev/null)

while IFS='|' read -r NAME NPORT REST; do
  [ -z "$NAME" ] && continue
  [ "$NAME" = "$CUR" ] && continue
  [ "$TRIES" -ge 5 ] && break
  UNTIL=$(awk -F'|' -v n="$NAME" '$1==n{print $2; exit}' "$FROZEN" 2>/dev/null)
  if [ -n "$UNTIL" ] && [ "$UNTIL" -gt "$NOW" ]; then continue; fi
  # пропускаем узлы, которых нет в списке самых быстрых (если замер был)
  if [ -n "$ORDER" ] && ! printf '%s\n' "$ORDER" | grep -qxF "$NAME"; then continue; fi
  R=$(/opt/etc/itx/gemini_check.sh "$NPORT")
  TRIES=$((TRIES + 1))
  say "gemini: пробую $NAME → $R"
  if [ "$R" = "available" ]; then
    /opt/bin/curl -s -o /dev/null --max-time 8 -X PUT -H "$AUTH" \
      -H "Content-Type: application/json" -d "{\"name\":\"$NAME\"}" "$API/proxies/ITX" 2>/dev/null
    if grep -q '^ITX_PIN=' /opt/etc/mihomo/ui.conf 2>/dev/null; then
      sed -i "s|^ITX_PIN=.*|ITX_PIN=\"$NAME\"|" /opt/etc/mihomo/ui.conf
    else
      printf '\nITX_PIN="%s"\n' "$NAME" >> /opt/etc/mihomo/ui.conf
    fi
    echo "$(date '+%F %T')|$NAME|available" > "$STATE"
    say "gemini: переключил на $NAME"
    /bin/sh /opt/etc/mihomo/notify.sh "NetRules: Gemini переключён на $NAME" >/dev/null 2>&1 &
    exit 0
  fi
done < "$NODES"

say "gemini: рабочих узлов не нашлось за $TRIES попыток"
/bin/sh /opt/etc/mihomo/notify.sh "NetRules: Gemini недоступен, рабочий узел не найден" >/dev/null 2>&1 &

awk -F'|' -v now="$NOW" '$2 > now' "$FROZEN" > "$FROZEN.tmp" 2>/dev/null && mv "$FROZEN.tmp" "$FROZEN"
