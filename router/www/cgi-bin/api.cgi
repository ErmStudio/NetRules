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
itx_up=0; [ -f /opt/var/run/itx.pid ] && kill -0 "$(cat /opt/var/run/itx.pid 2>/dev/null)" 2>/dev/null && itx_up=1
google_itx=0; grep -q "gemini.google.com" /opt/etc/mihomo/rules-itx.yaml 2>/dev/null && google_itx=1
autosub=0; . /opt/etc/mihomo/ui.conf 2>/dev/null; [ "${AUTO_SUB:-1}" = "1" ] && autosub=1
autosub_h="${AUTO_SUB_H:-4}"
tg_notify=0; . /opt/etc/mihomo/ui.conf 2>/dev/null; [ "${TG_NOTIFY:-1}" = "1" ] && tg_notify=1
ads=0; grep -q "adspector" /opt/etc/mihomo/rules-ads.yaml 2>/dev/null && ads=1
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
    TZ0=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
    cpu_pct=0
    if [ -r /proc/stat ]; then
      CUR=$(awk '/^cpu /{b=$2+$3+$4+$7+$8+$9; i=$5+$6; print b" "i}' /proc/stat)
      PREV=$(cat /tmp/mh-cpu.prev 2>/dev/null)
      echo "$CUR" > /tmp/mh-cpu.prev
      if [ -n "$PREV" ]; then
        cpu_pct=$(echo "$PREV $CUR" | awk '{db=$3-$1; di=$4-$2; s=db+di; if(s>0) printf "%d", db*100/s; else print 0}')
      fi
    fi
    temp=0
    case "$TZ0" in
      [0-9]*) temp=$((TZ0 / 1000)) ;;
      *) temp=0 ;;
    esac
    mihomem=0
    MPID=$(ps 2>/dev/null | grep '[m]ihomo -d' | awk '{print $1}' | head -1)
    if [ -n "$MPID" ] && [ -r "/proc/$MPID/status" ]; then
      mihomem=$(awk '/VmRSS/{print int($2/1024)}' /proc/$MPID/status 2>/dev/null)
    fi
    [ -z "$load" ] && load=0
    [ -z "$mihomem" ] && mihomem=0
    tg=0; grep -q '^TG_TOKEN="..' /opt/etc/mihomo/ui.conf 2>/dev/null && tg=1
    printf '{"mihomo":%s,"vpn":%s,"video":%s,"social":%s,"zapret":%s,"itx":%s,"google_itx":%s,"tg":%s,"tg_notify":%s,"autosub":%s,"ads":%s,"autosub_h":"%s","nodes":%s,"last":"%s","uptime":%s,"memtotal":%s,"memavail":%s,"node":"%s","country":"%s","delay":"%s","mup":%s,"load":"%s","temp":%s,"cpu":%s,"mihomem":%s,"dl":%s,"ul":%s}\n' \
      "$mihomo_up" "$vpn_on" "$video_on" "$social_on" "$zapret_up" "$itx_up" "$google_itx" "$tg" "$tg_notify" "$autosub" "$ads" "$(esc "$autosub_h")" "$nodes" "$(esc "$lu")" "$up" "$memtot" "$memav" \
      "$(esc "$node")" "$(esc "$country")" "$(esc "$delay")" "$mup" "$(esc "$load")" "$temp" "$cpu_pct" "$mihomem" "$dl" "$ul"
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

  conns)
    printf 'Content-Type: application/json\n\n'
    if [ "$mihomo_up" = "1" ]; then
      ND=$(ndmc -c "show ip dhcp bindings" 2>/dev/null | tr -d '\033' | sed 's/\[K//g')
      printf '%s\n' "$ND" | awk '
        /^ *ip:/ { ip=$2 }
        /^ *hostname:/ { if (ip != "") { print ip "|" $2; ip="" } }
      ' > /tmp/dhcp-names.txt 2>/dev/null
      /opt/bin/curl -s --max-time 8 -H "$AUTH" "$API/connections" 2>/dev/null | /opt/bin/python3 -c "
import sys, json, collections
from datetime import datetime, timezone
try:
    d = json.load(sys.stdin)
except Exception:
    print('{\"total\":0,\"devices\":[],\"domains\":[]}')
    raise SystemExit
names = {}
for src in ('/tmp/dhcp-names.txt', '/opt/etc/mihomo/device-names.txt'):
    try:
        for line in open(src, encoding='utf-8'):
            if '|' in line:
                k, v = line.rstrip('\n').split('|', 1)
                if v.strip():
                    names[k.strip()] = v.strip()
    except Exception:
        pass

def age_sec(x):
    s = x.get('start') or ''
    try:
        t = datetime.fromisoformat(s.replace('Z', '+00:00'))
        return (datetime.now(timezone.utc) - t).total_seconds()
    except Exception:
        return 0

c = d.get('connections') or []
dev = collections.Counter(); dom = collections.Counter(); dl = collections.Counter()
pol = collections.defaultdict(collections.Counter)
stall = collections.Counter(); stallage = collections.defaultdict(float); okc = collections.Counter()
rules = collections.defaultdict(collections.Counter)
for x in c:
    m = x.get('metadata') or {}
    ip = m.get('sourceIP') or '?'
    h = m.get('host') or m.get('sniffHost') or m.get('destinationIP') or '?'
    dev[ip] += 1; dom[h] += 1
    down = x.get('download') or 0
    up = x.get('upload') or 0
    dl[ip] += down
    ch = x.get('chains') or []
    p = 'PROXY' if 'PROXY' in ch else (ch[0] if ch else '?')
    pol[h][p] += 1
    r = x.get('rule') or ''
    rp = x.get('rulePayload') or ''
    if r:
        rules[h][r + ('/' + rp if rp else '')] += 1
    a = age_sec(x)
    if down > 0:
        okc[h] += 1
    elif up > 100 and a > 6:
        stall[h] += 1
        if a > stallage[h]:
            stallage[h] = a

doms = sorted(dom.items(), key=lambda kv: (-stall[kv[0]], -kv[1]))[:20]
out = {
  'total': len(c),
  'up': d.get('uploadTotal', 0),
  'down': d.get('downloadTotal', 0),
  'devices': [{'ip': k, 'name': names.get(k, ''), 'n': v, 'dl': dl[k]} for k, v in dev.most_common(10)],
  'domains': [{
      'host': k, 'n': v,
      'policy': pol[k].most_common(1)[0][0],
      'rule': rules[k].most_common(1)[0][0] if rules[k] else '',
      'stalled': stall[k],
      'ok': okc[k],
      'stallsec': int(stallage[k]),
  } for k, v in doms],
}
print(json.dumps(out, ensure_ascii=False))
"
    else
      printf '{"total":0,"devices":[],"domains":[]}\n'
    fi
    ;;

  bulk_proxy)
    hosts=$(printf '%s' "$q" | sed -n 's/.*hosts=\([^&]*\).*/\1/p' | sed 's/%2C/,/g;s/%2E/./g')
    added=0; skipped=0; OLDIFS=$IFS; IFS=','
    for h in $hosts; do
      [ -z "$h" ] && continue
      case "$h" in
        *[A-Za-z]*) ;;
        *) skipped=$((skipped+1)); continue ;;
      esac
      if grep -q "DOMAIN-SUFFIX,$h\$" "$RULES" 2>/dev/null; then continue; fi
      sed -i "s|^  # === SOCIAL-BEGIN ===|  - DOMAIN-SUFFIX,$h\n\n  # === SOCIAL-BEGIN ===|" "$RULES"
      added=$((added+1))
    done
    IFS=$OLDIFS
    reload_rules
    printf 'Content-Type: application/json\n\n{"ok":true,"added":%s,"skipped":%s}\n' "$added" "$skipped"
    ;;

  probe)
    host=$(printf '%s' "$q" | sed -n 's/.*host=\([^&]*\).*/\1/p' | sed 's/%2E/./g')
    [ -z "$host" ] && { printf 'Content-Type: application/json\n\n{"ok":false,"error":"нет host"}\n'; exit 0; }
    case "$host" in
      *[0-9].[0-9]*) URL="http://$host/" ;;
      *) URL="https://$host/" ;;
    esac
    RES=$(/opt/bin/curl -s -o /dev/null --max-time 7 -w "%{http_code} %{time_total}" "$URL" 2>/dev/null)
    CODE=$(printf '%s' "$RES" | awk '{print $1}')
    SEC=$(printf '%s' "$RES" | awk '{print $2}')
    [ -z "$CODE" ] && CODE=0
    [ -z "$SEC" ] && SEC=0
    printf 'Content-Type: application/json\n\n{"ok":true,"code":"%s","sec":"%s"}\n' "$CODE" "$SEC"
    ;;

  version)
    LOCAL=$(cat /opt/etc/mihomo/VERSION 2>/dev/null | tr -d '\r\n')
    [ -z "$LOCAL" ] && LOCAL="0.0.0"
    REMOTE=$(/opt/bin/curl -s --max-time 20 "https://raw.githubusercontent.com/ErmStudio/NetRules/main/VERSION" 2>/dev/null | tr -d '\r\n ')
    if [ -z "$REMOTE" ]; then
      printf 'Content-Type: application/json\n\n{"ok":false,"local":"%s","error":"нет связи с GitHub"}\n' "$LOCAL"
      exit 0
    fi
    if [ "$LOCAL" = "$REMOTE" ]; then
      UPD=false
    else
      NEW=$(printf '%s\n%s\n' "$LOCAL" "$REMOTE" | sort -V | tail -1)
      if [ "$NEW" = "$REMOTE" ]; then UPD=true; else UPD=false; fi
    fi
    printf 'Content-Type: application/json\n\n{"ok":true,"local":"%s","remote":"%s","update":%s}\n' "$LOCAL" "$REMOTE" "$UPD"
    ;;

  self_update)
    printf 'Content-Type: application/json\n\n'
    if [ -f /tmp/netrules-updating ]; then
      printf '{"ok":false,"error":"обновление уже идёт"}\n'
      exit 0
    fi
    touch /tmp/netrules-updating
    /bin/sh /opt/etc/mihomo/netrules_update.sh >/dev/null 2>&1
    RC=$?
    rm -f /tmp/netrules-updating
    if [ -f /opt/etc/mihomo/update_result.json ]; then
      cat /opt/etc/mihomo/update_result.json
    else
      printf '{"ok":false,"error":"нет результата (код %s)"}\n' "$RC"
    fi
    ;;

  update_log)
    printf 'Content-Type: application/json\n\n'
    printf '{"log":%s}\n' "$(jstr "$(tail -n 40 /opt/var/log/netrules-update.log 2>/dev/null)")"
    ;;

  set_interval)
    h=$(printf '%s' "$q" | sed -n 's/.*hours=\([0-9]*\).*/\1/p')
    m=$(printf '%s' "$q" | sed -n 's/.*minutes=\([0-9]*\).*/\1/p')
    case "$m" in 15|30) h=0 ;; *) m=0 ;; esac
    case "$h" in 0|1|2|3|4|6|8|12|24) ;; *) h=3 ;; esac
    CONF=/opt/etc/mihomo/ui.conf
    touch "$CONF"
    if grep -q '^SPEEDTEST_EVERY_M=' "$CONF" 2>/dev/null; then
      sed -i "s|^SPEEDTEST_EVERY_M=.*|SPEEDTEST_EVERY_M=\"$m\"|" "$CONF"
    else
      printf '\nSPEEDTEST_EVERY_M="%s"\n' "$m" >> "$CONF"
    fi
    if grep -q '^SPEEDTEST_EVERY_H=' "$CONF" 2>/dev/null; then
      sed -i "s|^SPEEDTEST_EVERY_H=.*|SPEEDTEST_EVERY_H=\"$h\"|" "$CONF"
    else
      printf '\nSPEEDTEST_EVERY_H="%s"\n' "$h" >> "$CONF"
    fi
    ( sleep 1
      kill "$(cat /opt/var/run/mihomo-tasks.pid 2>/dev/null)" 2>/dev/null
      rm -f /opt/var/run/mihomo-tasks.pid
      /opt/etc/init.d/S97mihomo-autoupdate start >/dev/null 2>&1
    ) >/dev/null 2>&1 &
    printf 'Content-Type: application/json\n\n{"ok":true,"hours":%s,"minutes":%s}\n' "$h" "$m"
    ;;
  itx_on)
    /opt/etc/init.d/S95itx start >/dev/null 2>&1
    sleep 2
    /opt/bin/curl -s -o /dev/null --max-time 8 -X PUT -H "Authorization: Bearer $SECRET" \
      -H "Content-Type: application/json" -d '{"path":"/opt/etc/mihomo/config.yaml"}' \
      "$API/configs?force=false" 2>/dev/null
    printf 'Content-Type: application/json\n\n{"ok":true,"itx":1}\n'
    ;;

  itx_off)
    /opt/etc/init.d/S95itx stop >/dev/null 2>&1
    printf 'Content-Type: application/json\n\n{"ok":true,"itx":0}\n'
    ;;

  google_itx_on)
    printf 'payload:\n  - DOMAIN-SUFFIX,gemini.google.com\n  - DOMAIN-SUFFIX,bard.google.com\n  - DOMAIN-SUFFIX,generativelanguage.googleapis.com\n  - DOMAIN-SUFFIX,aistudio.google.com\n  - DOMAIN-SUFFIX,notebooklm.google.com\n  - DOMAIN-SUFFIX,deepmind.google\n  - DOMAIN-SUFFIX,deepmind.com\n' > /opt/etc/mihomo/rules-itx.yaml
    /opt/bin/curl -s -o /dev/null --max-time 10 -X PUT -H "Authorization: Bearer $SECRET" \
      "$API/providers/rules/itx-rules" 2>/dev/null
    printf 'Content-Type: application/json\n\n{"ok":true,"google_itx":1}\n'
    ;;

  google_itx_off)
    printf 'payload: []\n' > /opt/etc/mihomo/rules-itx.yaml
    /opt/bin/curl -s -o /dev/null --max-time 10 -X PUT -H "Authorization: Bearer $SECRET" \
      "$API/providers/rules/itx-rules" 2>/dev/null
    printf 'Content-Type: application/json\n\n{"ok":true,"google_itx":0}\n'
    ;;

  itx_list)
    printf 'Content-Type: application/json\n\n'
    /opt/bin/curl -s --max-time 6 -H "Authorization: Bearer $SECRET" "$API/proxies/ITX" 2>/dev/null | /opt/bin/python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print('{\"now\":\"\",\"all\":[]}')
    raise SystemExit
print(json.dumps({'now': d.get('now') or '', 'all': d.get('all') or []}, ensure_ascii=False))
"
    ;;

  itx_pick)
    name=$(printf '%s' "$q" | sed -n 's/.*name=\([^&]*\).*/\1/p' | sed 's/%20/ /g;s/%2F/\//g')
    /opt/bin/curl -s -o /dev/null --max-time 10 -X PUT -H "Authorization: Bearer $SECRET" \
      -H "Content-Type: application/json" -d "{\"name\":\"$name\"}" "$API/proxies/ITX" 2>/dev/null
    CONF=/opt/etc/mihomo/ui.conf
    if grep -q '^ITX_PIN=' "$CONF" 2>/dev/null; then
      sed -i "s|^ITX_PIN=.*|ITX_PIN=\"$name\"|" "$CONF"
    else
      printf '\nITX_PIN="%s"\n' "$name" >> "$CONF"
    fi
    printf 'Content-Type: application/json\n\n{"ok":true,"now":"%s"}\n' "$name"
    ;;

  tg_notify_on)
    CONF=/opt/etc/mihomo/ui.conf
    touch "$CONF"
    if grep -q '^TG_NOTIFY=' "$CONF" 2>/dev/null; then
      sed -i 's|^TG_NOTIFY=.*|TG_NOTIFY="1"|' "$CONF"
    else
      printf '\nTG_NOTIFY="1"\n' >> "$CONF"
    fi
    printf 'Content-Type: application/json\n\n{"ok":true,"tg_notify":1}\n'
    ;;

  tg_notify_off)
    CONF=/opt/etc/mihomo/ui.conf
    touch "$CONF"
    if grep -q '^TG_NOTIFY=' "$CONF" 2>/dev/null; then
      sed -i 's|^TG_NOTIFY=.*|TG_NOTIFY="0"|' "$CONF"
    else
      printf '\nTG_NOTIFY="0"\n' >> "$CONF"
    fi
    printf 'Content-Type: application/json\n\n{"ok":true,"tg_notify":0}\n'
    ;;

  itx_block)
    name=$(printf '%s' "$q" | sed -n 's/.*name=\([^&]*\).*/\1/p' | sed 's/%20/ /g;s/%2F/\//g')
    ADDR=$(awk -F"|" -v n="$name" '$1==n{print $4; exit}' /opt/etc/itx/nodes.txt 2>/dev/null)
    if [ -n "$ADDR" ]; then
      grep -qx "$ADDR" /opt/etc/itx/blocklist.txt 2>/dev/null || echo "$ADDR" >> /opt/etc/itx/blocklist.txt
      ( /opt/bin/python3 /opt/etc/itx/build_final.py >/dev/null 2>&1
        /opt/etc/init.d/S95itx restart >/dev/null 2>&1
        sleep 3
        . /opt/etc/mihomo/ui.conf
        /opt/bin/curl -s -o /dev/null --max-time 15 -X PUT -H "Authorization: Bearer $SECRET" \
          -H "Content-Type: application/json" -d '{"path":"/opt/etc/mihomo/config.yaml"}' \
          "http://127.0.0.1:9090/configs?force=false" ) >/dev/null 2>&1 &
      printf 'Content-Type: application/json\n\n{"ok":true,"blocked":"%s","rebuild":true}\n' "$ADDR"
    else
      printf 'Content-Type: application/json\n\n{"ok":false,"error":"node not found"}\n'
    fi
    ;;

  autosub_on)
    CONF=/opt/etc/mihomo/ui.conf
    touch "$CONF"
    if grep -q '^AUTO_SUB=' "$CONF" 2>/dev/null; then
      sed -i 's|^AUTO_SUB=.*|AUTO_SUB="1"|' "$CONF"
    else
      printf '\nAUTO_SUB="1"\n' >> "$CONF"
    fi
    printf 'Content-Type: application/json\n\n{"ok":true,"autosub":1}\n'
    ;;

  autosub_off)
    CONF=/opt/etc/mihomo/ui.conf
    touch "$CONF"
    if grep -q '^AUTO_SUB=' "$CONF" 2>/dev/null; then
      sed -i 's|^AUTO_SUB=.*|AUTO_SUB="0"|' "$CONF"
    else
      printf '\nAUTO_SUB="0"\n' >> "$CONF"
    fi
    printf 'Content-Type: application/json\n\n{"ok":true,"autosub":0}\n'
    ;;

  set_autosub)
    h=$(printf '%s' "$q" | sed -n 's/.*hours=\([0-9]*\).*/\1/p')
    case "$h" in 1|2|3|4|6|8|12|24) ;; *) h=4 ;; esac
    CONF=/opt/etc/mihomo/ui.conf
    touch "$CONF"
    if grep -q '^AUTO_SUB_H=' "$CONF" 2>/dev/null; then
      sed -i "s|^AUTO_SUB_H=.*|AUTO_SUB_H=\"$h\"|" "$CONF"
    else
      printf '\nAUTO_SUB_H="%s"\n' "$h" >> "$CONF"
    fi
    ( sleep 1
      kill "$(cat /opt/var/run/mihomo-tasks.pid 2>/dev/null)" 2>/dev/null
      rm -f /opt/var/run/mihomo-tasks.pid
      /opt/etc/init.d/S97mihomo-autoupdate start >/dev/null 2>&1 ) >/dev/null 2>&1 &
    printf 'Content-Type: application/json\n\n{"ok":true,"hours":%s}\n' "$h"
    ;;

  ads_on)
    /bin/cp /opt/etc/mihomo/rules-ads.yaml.full /opt/etc/mihomo/rules-ads.yaml 2>/dev/null
    /opt/bin/curl -s -o /dev/null --max-time 10 -X PUT -H "Authorization: Bearer $SECRET" "$API/providers/rules/ads" 2>/dev/null
    printf 'Content-Type: application/json\n\n{"ok":true,"ads":1}\n'
    ;;

  ads_off)
    printf 'payload: []\n' > /opt/etc/mihomo/rules-ads.yaml
    /opt/bin/curl -s -o /dev/null --max-time 10 -X PUT -H "Authorization: Bearer $SECRET" "$API/providers/rules/ads" 2>/dev/null
    printf 'Content-Type: application/json\n\n{"ok":true,"ads":0}\n'
    ;;

  gemini_check)
    : > /tmp/gm-res.txt
    cat > /tmp/gm1.sh <<'SH'
#!/bin/sh
P=$1
N=$(awk -F'|' -v p="$P" '$2==p{print $1; exit}' /opt/etc/itx/nodes.txt 2>/dev/null)
S=$(/opt/etc/itx/gemini_check.sh "$P")
echo "$P|$N|$S" >> /tmp/gm-res.txt
SH
    chmod +x /tmp/gm1.sh
    for P in $(awk -F'|' '{print $2}' /opt/etc/itx/nodes.txt 2>/dev/null); do echo "$P"; done \
      | xargs -I{} -P 6 /tmp/gm1.sh {}
    GOOD=$(grep "|available$" /tmp/gm-res.txt | head -1 | cut -d"|" -f1)
    if [ -n "$GOOD" ]; then
      NAME=$(awk -F'|' -v p="$GOOD" '$2==p{print $1; exit}' /opt/etc/itx/nodes.txt 2>/dev/null)
      /opt/bin/curl -s -o /dev/null --max-time 8 -X PUT -H "Authorization: Bearer $SECRET" \
        -H "Content-Type: application/json" -d "{\"name\":\"$NAME\"}" "$API/proxies/ITX" 2>/dev/null
    fi
    printf 'Content-Type: application/json\n\n'
    /opt/bin/python3 -c "
import json
rows=[]
try:
    for line in open('/tmp/gm-res.txt'):
        p=line.strip().split('|')
        if len(p)==3: rows.append({'port':p[0],'name':p[1],'status':p[2]})
except Exception:
    pass
ok=[r for r in rows if r['status']=='available']
print(json.dumps({'ok':True,'total':len(rows),'available':len(ok),
                  'pinned':ok[0]['name'] if ok else '',
                  'nodes':rows}, ensure_ascii=False))
"
    ;;

  config)
    VER=$(cat /opt/etc/mihomo/VERSION 2>/dev/null || echo "1.0.0")
    MODEL=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\000' | sed 's/ *$//')
    [ -z "$MODEL" ] && MODEL="Keenetic"
    MV=$(/opt/bin/curl -s --max-time 4 -H "Authorization: Bearer $SECRET" "$API/version" 2>/dev/null | sed -n 's/.*"version":"\([^"]*\)".*/\1/p' | head -1)
    ZV=$(/opt/usr/bin/nfqws2 --version 2>/dev/null | sed -n 's/.*version v\([0-9.]*\).*/\1/p' | head -1)
    PARTS="$MODEL"
    [ -n "$MV" ] && PARTS="$PARTS · mihomo $MV"
    [ -n "$ZV" ] && PARTS="$PARTS · zapret $ZV"
    SUB="${SITE_SUBTITLE:-$PARTS}"
    CONTACT="${CONTACT_URL:-https://github.com/ErmStudio/NetRules/issues/new}"
    INTERVAL="${SPEEDTEST_EVERY_H:-3}"
    ITXAVAIL=0; [ -f /opt/etc/itx/sub.json ] && ITXAVAIL=1
    tg=0; grep -q '^TG_TOKEN=.\+' /opt/etc/mihomo/ui.conf 2>/dev/null && tg=1
    R_URL="${ROUTER_URL:-http://192.168.1.1/}"
    Z_URL="${ZAPRET_URL:-http://192.168.1.1:90/}"
    M_URL="${MIHOMO_UI_URL:-http://mihomo.lan:9090/ui/metacubexd/}"
    printf 'Content-Type: application/json\n\n'
    printf '{"router":"%s","zapret":"%s","mihomo":"%s","version":"%s","subtitle":"%s","contact":"%s","interval":"%s","tg":%s,"itx_available":%s}\n' \
      "$(esc "$R_URL")" "$(esc "$Z_URL")" "$(esc "$M_URL")" "$(esc "$VER")" "$(esc "$SUB")" "$(esc "$CONTACT")" "$(esc "$INTERVAL")" "$tg" "$ITXAVAIL"
    ;;
  myip)
    printf 'Content-Type: application/json\n\n'
    R=""
    for U in "https://ifconfig.co/json" "https://api.myip.com" "https://ipinfo.io/json"; do
      R=$(/opt/bin/curl -s --max-time 10 --proxy "http://127.0.0.1:7890" "$U" 2>/dev/null)
      case "$R" in
        *rate*l*mit*|*429*|"") R="" ;;
        \{*) break ;;
        *) R="" ;;
      esac
    done
    if [ -n "$R" ]; then printf '%s\n' "$R"; else printf '{"error":"сервисы не ответили"}\n'; fi
    ;;

  add_rule)
    host=$(printf '%s' "$q" | sed -n 's/.*host=\([^&]*\).*/\1/p' | sed 's/%2E/./g;s/%2F/\//g')
    pol=$(printf '%s' "$q" | sed -n 's/.*policy=\([a-z]*\).*/\1/p')
    [ -z "$host" ] && { printf 'Content-Type: application/json\n\n{"ok":false,"error":"нет host"}\n'; exit 0; }
    case "$pol" in proxy|direct|reject) ;; *) pol=proxy ;; esac
    case "$pol" in
      proxy)
        grep -q "DOMAIN-SUFFIX,$host\$" "$RULES" 2>/dev/null || \
          sed -i "s|^  # === SOCIAL-BEGIN ===|  - DOMAIN-SUFFIX,$host\n\n  # === SOCIAL-BEGIN ===|" "$RULES"
        ;;
      direct|reject)
        UP=$(echo "$pol" | tr 'a-z' 'A-Z')
        for f in /opt/etc/mihomo/config.yaml /opt/etc/mihomo/template.yaml; do
          [ -f "$f" ] || continue
          grep -q "DOMAIN-SUFFIX,$host,$UP" "$f" || \
            sed -i "s|^rules:|rules:\n  - DOMAIN-SUFFIX,$host,$UP|" "$f"
        done
        ;;
    esac
    reload_config
    printf 'Content-Type: application/json\n\n{"ok":true,"host":"%s","policy":"%s"}\n' "$host" "$pol"
    ;;

  rename_device)
    ip=$(printf '%s' "$q" | sed -n 's/.*ip=\([0-9.]*\).*/\1/p')
    nm=$(printf '%s' "$q" | sed -n 's/.*name=\([^&]*\).*/\1/p' | sed 's/%20/ /g;s/+/ /g')
    CN=/opt/etc/mihomo/device-names.txt
    [ -z "$ip" ] && { printf 'Content-Type: application/json\n\n{"ok":false}\n'; exit 0; }
    touch "$CN"
    grep -v "^$ip|" "$CN" > "$CN.tmp" 2>/dev/null; mv "$CN.tmp" "$CN" 2>/dev/null
    [ -n "$nm" ] && echo "$ip|$nm" >> "$CN"
    printf 'Content-Type: application/json\n\n{"ok":true}\n'
    ;;

  backups)
    printf 'Content-Type: application/json\n\n{"items":['
    first=1
    for d in /storage/mihomo-backup/*/; do
      [ -d "$d" ] || continue
      n=$(basename "$d")
      sz=$(du -sk "$d" 2>/dev/null | awk '{print $1}')
      ts=$(stat -c %Y "$d" 2>/dev/null)
      [ $first -eq 0 ] && printf ','
      first=0
      printf '{"name":"%s","kb":%s,"ts":%s}' "$n" "${sz:-0}" "${ts:-0}"
    done
    printf ']}\n'
    ;;

  restore)
    d=$(printf '%s' "$q" | sed -n 's/.*dir=\([0-9]*\).*/\1/p')
    B="/storage/mihomo-backup/$d"
    if [ -n "$d" ] && [ -d "$B" ]; then
      cp -f "$B"/* /opt/etc/mihomo/ 2>/dev/null
      chmod +x /opt/etc/mihomo/*.sh 2>/dev/null
      restart_bg
      printf 'Content-Type: application/json\n\n{"ok":true}\n'
    else
      printf 'Content-Type: application/json\n\n{"ok":false,"error":"нет такой копии"}\n'
    fi
    ;;

  history)
    HIST=/opt/etc/mihomo/delay_history
    printf 'Content-Type: application/json\n\n{"points":['
    tail -n 60 "$HIST" 2>/dev/null | awk -F'|' 'BEGIN{f=1} NF==2 {printf "%s[%s,%s]", (f?"":","), $1, $2; f=0}'
    printf ']}\n'
    ;;

  traffic_daily)
    printf 'Content-Type: application/json\n\n'
    /opt/bin/python3 -c "
import collections, json
agg = collections.OrderedDict()
try:
    for line in open('/opt/etc/mihomo/traffic.csv', encoding='utf-8'):
        p = line.strip().split(',')
        if len(p) != 3:
            continue
        d, dl, ul = p
        try:
            dl = int(dl); ul = int(ul)
        except Exception:
            continue
        a = agg.setdefault(d, [0, 0])
        a[0] += dl; a[1] += ul
except FileNotFoundError:
    pass
rows = [[k, v[0], v[1]] for k, v in sorted(agg.items())][-30:]
print(json.dumps({'rows': rows}, ensure_ascii=False))
"
    ;;

  notify_test)
    /bin/sh /opt/etc/mihomo/notify.sh "NetRules: тестовое уведомление ✅"
    printf 'Content-Type: application/json\n\n{"ok":true}\n'
    ;;

  fullcheck)
    ( /bin/sh /opt/etc/mihomo/fullcheck.sh >/dev/null 2>&1 & ) &
    printf 'Content-Type: application/json\n\n{"ok":true,"started":true}\n'
    ;;
  nodecheck)
    if [ "$mihomo_up" != "1" ]; then
      printf 'Content-Type: application/json\n\n{"ok":false,"error":"mihomo не запущен"}\n'
      exit 0
    fi
    /bin/sh /opt/etc/mihomo/checkall.sh >/dev/null 2>&1
    RC=$?
    if [ "$RC" = "2" ]; then
      printf 'Content-Type: application/json\n\n{"ok":false,"error":"mihomo не готов, проверка отменена"}\n'
      exit 0
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
