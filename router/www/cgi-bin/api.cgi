#!/bin/sh
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin

RULES=/opt/etc/mihomo/rules-proxy.yaml
CFG=/opt/etc/mihomo/config.yaml
STATUS=/opt/etc/mihomo/last_update.txt
LOGDIR=/opt/var/log
API="http://127.0.0.1:9090"
AUTH="Authorization: Bearer dshsecret"
SPEEDURL="https://speed.cloudflare.com/__down?bytes=2000000"

esc() {
  printf '%s' "$1" | tr -d '\r' | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | sed -e ':a' -e 'N' -e '$!ba' -e 's/\n/\\n/g'
}
jstr() { printf '"%s"' "$(esc "$1")"; }

q="$QUERY_STRING"
act=$(printf '%s' "$q" | sed -n 's/.*action=\([a-z_]*\).*/\1/p')
fld=$(printf '%s' "$q" | sed -n 's/.*f=\([a-z0-9_]*\).*/\1/p')

mihomo_up=0; netstat -ltn 2>/dev/null | grep -q ':7892' && mihomo_up=1
vpn_on=0; iptables -t nat -S PREROUTING 2>/dev/null | grep -q 'MH_REDIR' && vpn_on=1
video_on=0; grep -q 'googlevideo' "$RULES" 2>/dev/null && video_on=1
social_on=0; grep -q 'DOMAIN-SUFFIX,instagram.com' "$RULES" 2>/dev/null && social_on=1
zapret_up=0; ps 2>/dev/null | grep -q '[n]fqws2' && zapret_up=1
nodes=$(grep -c '^    server: ' "$CFG" 2>/dev/null); [ -z "$nodes" ] && nodes=0
lu=$(cat "$STATUS" 2>/dev/null)
up=$(awk '{print int($1)}' /proc/uptime 2>/dev/null)
memtot=$(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null)
memav=$(awk '/MemAvailable/{print $2}' /proc/meminfo 2>/dev/null)

restart_bg() { ( /opt/etc/init.d/S99mihomo restart >/dev/null 2>&1 & ); }
select_node() {
  /opt/bin/curl -s -o /dev/null --max-time 8 -X PUT \
    -H "Authorization: Bearer dshsecret" -H "Content-Type: application/json" \
    -d "{\"name\":\"$1\"}" "$API/proxies/PROXY" 2>/dev/null
}

case "$act" in
  status)
    node=""; country=""; delay=""; dl=0; ul=0
    if [ "$mihomo_up" = "1" ]; then
      P=$(/opt/bin/wget -q -O - --timeout=4 --header="$AUTH" "$API/proxies/PROXY" 2>/dev/null)
      node=$(printf '%s' "$P" | sed -n 's/.*"now":"\([^"]*\)".*/\1/p' | head -1)
      if [ "$node" = "AUTO" ] || [ -z "$node" ]; then
        A=$(/opt/bin/wget -q -O - --timeout=4 --header="$AUTH" "$API/proxies/AUTO" 2>/dev/null)
        node=$(printf '%s' "$A" | sed -n 's/.*"now":"\([^"]*\)".*/\1/p' | head -1)
        delay=$(printf '%s' "$A" | sed -n 's/.*"delay":\([0-9]*\).*/\1/p' | head -1)
      else
        N=$(/opt/bin/wget -q -O - --timeout=4 --header="$AUTH" "$API/proxies/$node" 2>/dev/null)
        delay=$(printf '%s' "$N" | sed -n 's/.*"delay":\([0-9]*\).*/\1/p' | tail -1)
      fi
      C=$(/opt/bin/wget -q -O - --timeout=4 --header="$AUTH" "$API/connections" 2>/dev/null)
      dl=$(printf '%s' "$C" | sed -n 's/.*"downloadTotal":\([0-9]*\).*/\1/p' | head -1)
      ul=$(printf '%s' "$C" | sed -n 's/.*"uploadTotal":\([0-9]*\).*/\1/p' | head -1)
      country=$(awk -F"|" -v n="$node" '$1==n{print $2; exit}' /opt/etc/mihomo/countries.txt 2>/dev/null)
      [ -z "$dl" ] && dl=0
      [ -z "$ul" ] && ul=0
    fi
    mup=0
    if [ "$mihomo_up" = "1" ]; then
      MP=$(ps 2>/dev/null | grep '[m]ihomo -d' | awk '{print $1}' | head -1)
      if [ -n "$MP" ] && [ -r "/proc/$MP/stat" ]; then
        ST=$(awk '{print $22}' /proc/$MP/stat 2>/dev/null)
        UP=$(awk '{print int($1)}' /proc/uptime 2>/dev/null)
        [ -n "$ST" ] && mup=$((UP - ST/100))
      fi
    fi
    printf 'Content-Type: application/json\n\n'
    printf '{"mihomo":%s,"vpn":%s,"video":%s,"social":%s,"zapret":%s,"nodes":%s,"last":"%s","uptime":%s,"memtotal":%s,"memavail":%s,"node":"%s","country":"%s","delay":"%s","mup":%s,"dl":%s,"ul":%s}\n' \
      "$mihomo_up" "$vpn_on" "$video_on" "$social_on" "$zapret_up" "$nodes" "$(esc "$lu")" "$up" "$memtot" "$memav" \
      "$(esc "$node")" "$(esc "$country")" "$(esc "$delay")" "$mup" "$dl" "$ul"
    ;;

  rules_get)
    mup=0
    if [ "$mihomo_up" = "1" ]; then
      MP=$(ps 2>/dev/null | grep '[m]ihomo -d' | awk '{print $1}' | head -1)
      if [ -n "$MP" ] && [ -r "/proc/$MP/stat" ]; then
        ST=$(awk '{print $22}' /proc/$MP/stat 2>/dev/null)
        UP=$(awk '{print int($1)}' /proc/uptime 2>/dev/null)
        [ -n "$ST" ] && mup=$((UP - ST/100))
      fi
    fi
    printf 'Content-Type: application/json\n\n'
    printf '{"rules":%s}\n' "$(jstr "$(cat "$RULES" 2>/dev/null)")"
    ;;

  rules_set)
    LEN=${CONTENT_LENGTH:-0}
    BODY=$(dd bs=1 count="$LEN" 2>/dev/null)
    DATA=$(printf '%s' "$BODY" | sed '1s/^rules=//' | tr -d '\r')
    printf '%s' "$DATA" > "$RULES.tmp"
    if head -1 "$RULES.tmp" | grep -q '^payload:'; then
      mv "$RULES.tmp" "$RULES"; restart_bg
      printf 'Content-Type: application/json\n\n{"ok":true}\n'
    else
      rm -f "$RULES.tmp"
      printf 'Content-Type: application/json\n\n{"ok":false,"error":"файл должен начинаться с payload:"}\n'
    fi
    ;;

  toggle_video)
    if [ "$video_on" = "1" ]; then sed -i '/googlevideo/d' "$RULES"; new=0
    else sed -i 's|^  # === VIDEO-BEGIN ===|  # === VIDEO-BEGIN ===\n  - DOMAIN-SUFFIX,googlevideo.com|' "$RULES"; new=1; fi
    restart_bg
    printf 'Content-Type: application/json\n\n{"ok":true,"video":%s}\n' "$new"
    ;;

  toggle_social)
    if [ "$social_on" = "1" ]; then
      sed -i '/DOMAIN-SUFFIX,instagram.com/d;/DOMAIN-SUFFIX,cdninstagram.com/d;/DOMAIN-SUFFIX,facebook.com/d;/DOMAIN-SUFFIX,fbcdn.net/d;/DOMAIN-SUFFIX,whatsapp.com/d;/DOMAIN-SUFFIX,whatsapp.net/d' "$RULES"; new=0
    else
      sed -i 's|^  # === SOCIAL-BEGIN ===|  # === SOCIAL-BEGIN ===\n  - DOMAIN-SUFFIX,instagram.com\n  - DOMAIN-SUFFIX,cdninstagram.com\n  - DOMAIN-SUFFIX,facebook.com\n  - DOMAIN-SUFFIX,fbcdn.net\n  - DOMAIN-SUFFIX,whatsapp.com\n  - DOMAIN-SUFFIX,whatsapp.net|' "$RULES"; new=1
    fi
    restart_bg
    printf 'Content-Type: application/json\n\n{"ok":true,"social":%s}\n' "$new"
    ;;

  toggle_vpn)
    if [ "$vpn_on" = "1" ]; then ( /opt/etc/init.d/S99mihomo stop >/dev/null 2>&1 & ); new=0
    else ( /opt/etc/init.d/S99mihomo start >/dev/null 2>&1 & ); new=1; fi
    printf 'Content-Type: application/json\n\n{"ok":true,"vpn":%s}\n' "$new"
    ;;

  toggle_zapret)
    if [ "$zapret_up" = "1" ]; then
      /opt/etc/init.d/S51nfqws2 stop >/dev/null 2>&1; new=0
    else
      /opt/etc/init.d/S51nfqws2 start >/dev/null 2>&1; sleep 2; new=1
      ps 2>/dev/null | grep -q '[n]fqws2' || new=0
    fi
    printf 'Content-Type: application/json\n\n{"ok":true,"zapret":%s}\n' "$new"
    ;;

  speedtest)
    /bin/sh /opt/etc/mihomo/speedtest.sh >/dev/null 2>&1
    mup=0
    if [ "$mihomo_up" = "1" ]; then
      MP=$(ps 2>/dev/null | grep '[m]ihomo -d' | awk '{print $1}' | head -1)
      if [ -n "$MP" ] && [ -r "/proc/$MP/stat" ]; then
        ST=$(awk '{print $22}' /proc/$MP/stat 2>/dev/null)
        UP=$(awk '{print int($1)}' /proc/uptime 2>/dev/null)
        [ -n "$ST" ] && mup=$((UP - ST/100))
      fi
    fi
    printf 'Content-Type: application/json\n\n'
    cat /opt/etc/mihomo/speedtest.json 2>/dev/null || printf '{"ok":false}\n'
    ;;

  conns)
    printf 'Content-Type: application/json\n\n'
    if [ "$mihomo_up" = "1" ]; then
      /opt/bin/curl -s --max-time 8 -H "$AUTH" "$API/connections" 2>/dev/null | /opt/bin/python3 -c "
import sys, json, collections
try:
    d = json.load(sys.stdin)
except Exception:
    print('{\"total\":0,\"devices\":[],\"domains\":[]}')
    raise SystemExit
c = d.get('connections') or []
dev = collections.Counter(); dom = collections.Counter(); dl = collections.Counter()
for x in c:
    m = x.get('metadata') or {}
    ip = m.get('sourceIP') or '?'
    h = m.get('host') or m.get('sniffHost') or m.get('destinationIP') or '?'
    dev[ip] += 1; dom[h] += 1
    dl[ip] += (x.get('download') or 0)
out = {
  'total': len(c),
  'up': d.get('uploadTotal', 0),
  'down': d.get('downloadTotal', 0),
  'devices': [{'ip': k, 'n': v, 'dl': dl[k]} for k, v in dev.most_common(10)],
  'domains': [{'host': k, 'n': v} for k, v in dom.most_common(12)],
}
print(json.dumps(out, ensure_ascii=False))
"
    else
      printf '{"total":0,"devices":[],"domains":[]}\n'
    fi
    ;;
  nodecheck)
    /bin/sh /opt/etc/mihomo/checkall.sh >/dev/null 2>&1
    mup=0
    if [ "$mihomo_up" = "1" ]; then
      MP=$(ps 2>/dev/null | grep '[m]ihomo -d' | awk '{print $1}' | head -1)
      if [ -n "$MP" ] && [ -r "/proc/$MP/stat" ]; then
        ST=$(awk '{print $22}' /proc/$MP/stat 2>/dev/null)
        UP=$(awk '{print int($1)}' /proc/uptime 2>/dev/null)
        [ -n "$ST" ] && mup=$((UP - ST/100))
      fi
    fi
    printf 'Content-Type: application/json\n\n'
    cat /opt/etc/mihomo/nodes_health.json 2>/dev/null || printf '{"ok":false}\n'
    ;;

  health)
    mup=0
    if [ "$mihomo_up" = "1" ]; then
      MP=$(ps 2>/dev/null | grep '[m]ihomo -d' | awk '{print $1}' | head -1)
      if [ -n "$MP" ] && [ -r "/proc/$MP/stat" ]; then
        ST=$(awk '{print $22}' /proc/$MP/stat 2>/dev/null)
        UP=$(awk '{print int($1)}' /proc/uptime 2>/dev/null)
        [ -n "$ST" ] && mup=$((UP - ST/100))
      fi
    fi
    printf 'Content-Type: application/json\n\n'
    cat /opt/etc/mihomo/nodes_health.json 2>/dev/null || printf '{"ok":false}\n'
    ;;
  speed_last)
    mup=0
    if [ "$mihomo_up" = "1" ]; then
      MP=$(ps 2>/dev/null | grep '[m]ihomo -d' | awk '{print $1}' | head -1)
      if [ -n "$MP" ] && [ -r "/proc/$MP/stat" ]; then
        ST=$(awk '{print $22}' /proc/$MP/stat 2>/dev/null)
        UP=$(awk '{print int($1)}' /proc/uptime 2>/dev/null)
        [ -n "$ST" ] && mup=$((UP - ST/100))
      fi
    fi
    printf 'Content-Type: application/json\n\n'
    cat /opt/etc/mihomo/speedtest.json 2>/dev/null || printf '{"ok":false}\n'
    ;;
  restart) ( /opt/etc/init.d/S99mihomo restart >/dev/null 2>&1 & ); printf 'Content-Type: application/json\n\n{"ok":true}\n' ;;
  update)  ( /opt/etc/mihomo/update.sh >/dev/null 2>&1 & );            printf 'Content-Type: application/json\n\n{"ok":true}\n' ;;
  backup)  /opt/etc/mihomo/backup.sh >/dev/null 2>&1;                  printf 'Content-Type: application/json\n\n{"ok":true}\n' ;;

  logs)
    case "$fld" in
      update)   file=$LOGDIR/mihomo-update.log ;;
      watchdog) file=$LOGDIR/mihomo-watchdog.log ;;
      tasks)    file=$LOGDIR/mihomo-tasks.log ;;
      zapret)   file=$LOGDIR/nfqws2.log ;;
      speed)    file=$LOGDIR/mihomo-speedtest.log ;;
      *)        file=$LOGDIR/mihomo.log ;;
    esac
    mup=0
    if [ "$mihomo_up" = "1" ]; then
      MP=$(ps 2>/dev/null | grep '[m]ihomo -d' | awk '{print $1}' | head -1)
      if [ -n "$MP" ] && [ -r "/proc/$MP/stat" ]; then
        ST=$(awk '{print $22}' /proc/$MP/stat 2>/dev/null)
        UP=$(awk '{print int($1)}' /proc/uptime 2>/dev/null)
        [ -n "$ST" ] && mup=$((UP - ST/100))
      fi
    fi
    printf 'Content-Type: application/json\n\n'
    printf '{"log":%s}\n' "$(jstr "$(tail -n 60 "$file" 2>/dev/null)")"
    ;;

  *)
    printf 'Content-Type: application/json\n\n{"error":"unknown action"}\n'
    ;;
esac
