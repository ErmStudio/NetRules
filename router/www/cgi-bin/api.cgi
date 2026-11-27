#!/bin/sh
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin

RULES=/opt/etc/mihomo/rules-proxy.yaml
CFG=/opt/etc/mihomo/config.yaml
STATUS=/opt/etc/mihomo/last_update.txt
LOGDIR=/opt/var/log
[ -f /opt/etc/mihomo/ui.conf ] && . /opt/etc/mihomo/ui.conf
API="${MIHOMO_API:-http://127.0.0.1:9090}"
SECRET="${MIHOMO_SECRET:-change-me}"
AUTH="Authorization: Bearer $SECRET"
SPEEDURL="https://speed.cloudflare.com/__down?bytes=2000000"

esc() {
  printf '%s' "$1" | tr -d '\r' | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | sed -e ':a' -e 'N' -e '$!ba' -e 's/\n/\\n/g'
}
jstr() { printf '"%s"' "$(esc "$1")"; }

q="$QUERY_STRING"
act=$(printf '%s' "$q" | sed -n 's/.*action=\([a-z_]*\).*/\1/p')
fld=$(printf '%s' "$q" | sed -n 's/.*f=\([a-z0-9_]*\).*/\1/p')

mihomo_up=0; netstat -ltn 2>/dev/null | grep -q ':7892' && mihomo_up=1
vpn_on=0; [ -f /opt/var/run/mihomo.enabled ] && vpn_on=1
video_on=0; grep -q 'googlevideo' "$RULES" 2>/dev/null && video_on=1
social_on=0; grep -q 'DOMAIN-SUFFIX,instagram.com' "$RULES" 2>/dev/null && social_on=1
zapret_up=0; ps 2>/dev/null | grep -q '[n]fqws2' && zapret_up=1
nodes=$(grep -c '^    server: ' "$CFG" 2>/dev/null); [ -z "$nodes" ] && nodes=0
lu=$(cat "$STATUS" 2>/dev/null)
up=$(awk '{print int($1)}' /proc/uptime 2>/dev/null)
memtot=$(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null)
memav=$(awk '/MemAvailable/{print $2}' /proc/meminfo 2>/dev/null)

restart_bg() { ( /opt/etc/init.d/S99mihomo restart >/dev/null 2>&1 & ); }
reload_rules() {
  /opt/bin/curl -s -o /dev/null --max-time 10 -X PUT \
    -H "Authorization: Bearer $SECRET" "$API/providers/rules/proxy-sites" 2>/dev/null
}
reload_config() {
  /opt/bin/curl -s -o /dev/null --max-time 15 -X PUT \
    -H "Authorization: Bearer $SECRET" -H "Content-Type: application/json" \
    -d '{"path":"/opt/etc/mihomo/config.yaml"}' "$API/configs?force=false" 2>/dev/null
}
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
    load=$(awk '{print $1}' /proc/loadavg 2>/dev/null)
    mihomem=0
    MPID=$(ps 2>/dev/null | grep '[m]ihomo -d' | awk '{print $1}' | head -1)
    if [ -n "$MPID" ] && [ -r "/proc/$MPID/status" ]; then
      mihomem=$(awk '/VmRSS/{print int($2/1024)}' /proc/$MPID/status 2>/dev/null)
    fi
    [ -z "$load" ] && load=0
    [ -z "$mihomem" ] && mihomem=0
    tg=0; grep -q '^TG_TOKEN="..' /opt/etc/mihomo/ui.conf 2>/dev/null && tg=1
    printf '{"mihomo":%s,"vpn":%s,"video":%s,"social":%s,"zapret":%s,"tg":%s,"nodes":%s,"last":"%s","uptime":%s,"memtotal":%s,"memavail":%s,"node":"%s","country":"%s","delay":"%s","mup":%s,"load":"%s","mihomem":%s,"dl":%s,"ul":%s}\n' \
      "$mihomo_up" "$vpn_on" "$video_on" "$social_on" "$zapret_up" "$tg" "$nodes" "$(esc "$lu")" "$up" "$memtot" "$memav" \
      "$(esc "$node")" "$(esc "$country")" "$(esc "$delay")" "$mup" "$(esc "$load")" "$mihomem" "$dl" "$ul"
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
      mv "$RULES.tmp" "$RULES"; reload_rules
      printf 'Content-Type: application/json\n\n{"ok":true}\n'
    else
      rm -f "$RULES.tmp"
      printf 'Content-Type: application/json\n\n{"ok":false,"error":"файл должен начинаться с payload:"}\n'
    fi
    ;;

  toggle_video)
    want=$(printf '%s' "$q" | sed -n 's/.*[&?]on=\([01]\).*/\1/p')
    if [ -z "$want" ]; then [ "$video_on" = "1" ] && want=0 || want=1; fi
    if [ "$want" = "1" ]; then
      grep -q 'googlevideo' "$RULES" 2>/dev/null || \
        sed -i 's|^  # === VIDEO-BEGIN ===|  # === VIDEO-BEGIN ===\n  - DOMAIN-SUFFIX,googlevideo.com|' "$RULES"
    else
      sed -i '/googlevideo/d' "$RULES"
    fi
    reload_rules
    printf 'Content-Type: application/json\n\n{"ok":true,"video":%s}\n' "$want"
    ;;

  toggle_social)
    want=$(printf '%s' "$q" | sed -n 's/.*[&?]on=\([01]\).*/\1/p')
    if [ -z "$want" ]; then [ "$social_on" = "1" ] && want=0 || want=1; fi
    if [ "$want" = "1" ]; then
      grep -q 'DOMAIN-SUFFIX,instagram.com' "$RULES" 2>/dev/null || \
        sed -i 's|^  # === SOCIAL-BEGIN ===|  # === SOCIAL-BEGIN ===\n  - DOMAIN-SUFFIX,instagram.com\n  - DOMAIN-SUFFIX,cdninstagram.com\n  - DOMAIN-SUFFIX,facebook.com\n  - DOMAIN-SUFFIX,fbcdn.net\n  - DOMAIN-SUFFIX,whatsapp.com\n  - DOMAIN-SUFFIX,whatsapp.net|' "$RULES"
    else
      sed -i '/DOMAIN-SUFFIX,instagram.com/d;/DOMAIN-SUFFIX,cdninstagram.com/d;/DOMAIN-SUFFIX,facebook.com/d;/DOMAIN-SUFFIX,fbcdn.net/d;/DOMAIN-SUFFIX,whatsapp.com/d;/DOMAIN-SUFFIX,whatsapp.net/d' "$RULES"
    fi
    reload_rules
    printf 'Content-Type: application/json\n\n{"ok":true,"social":%s}\n' "$want"
    ;;

  toggle_vpn)
    want=$(printf '%s' "$q" | sed -n 's/.*[&?]on=\([01]\).*/\1/p')
    if [ -z "$want" ]; then [ "$vpn_on" = "1" ] && want=0 || want=1; fi
    if [ "$want" = "1" ]; then
      ( /opt/etc/init.d/S99mihomo start >/dev/null 2>&1 & )
    else
      ( /opt/etc/init.d/S99mihomo stop >/dev/null 2>&1 & )
    fi
    printf 'Content-Type: application/json\n\n{"ok":true,"vpn":%s}\n' "$want"
    ;;

  toggle_zapret)
    want=$(printf '%s' "$q" | sed -n 's/.*[&?]on=\([01]\).*/\1/p')
    if [ -z "$want" ]; then [ "$zapret_up" = "1" ] && want=0 || want=1; fi
    if [ "$want" = "1" ]; then
      /opt/etc/init.d/S51nfqws2 start >/dev/null 2>&1
      sleep 2
      ps 2>/dev/null | grep -q '[n]fqws2' || want=0
    else
      /opt/etc/init.d/S51nfqws2 stop >/dev/null 2>&1
    fi
    printf 'Content-Type: application/json\n\n{"ok":true,"zapret":%s}\n' "$want"
    ;;

  speedtest)
    /bin/sh /opt/etc/mihomo/fullcheck.sh >/dev/null 2>&1
    printf 'Content-Type: application/json\n\n'
    cat /opt/etc/mihomo/speedtest.json 2>/dev/null || printf '{"ok":false}\n'
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
