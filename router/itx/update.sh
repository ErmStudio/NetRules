#!/bin/sh
# Обновление второй подписки (ITX): скачать, проверить страны/задержки, собрать конфиг.
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH

BASE=/opt/etc/itx
SUB=$(cat "$BASE/sub.url" 2>/dev/null)
LOG=/opt/var/log/itx-update.log
say() { echo "$(date '+%F %T') $1" >> $LOG; }

[ -z "$SUB" ] && { say "нет sub.url"; exit 1; }
say "=== обновление ITX ==="

HW=$(cat "$BASE/hwid" 2>/dev/null)
if [ -z "$HW" ]; then
  HW=$(echo "netrules-device" | md5sum | awk '{print $1}')
  echo "$HW" > "$BASE/hwid"
fi

/opt/bin/curl -s --max-time 60 "$SUB" \
  -H "User-Agent: Happ/2.11.0" -H "x-hwid: $HW" -H "x-device-os: android" \
  -H "x-ver-os: 14" -H "x-device-model: Pixel 7" -H "x-ver-app: 2.11.0" \
  -o "$BASE/sub.json" || { say "ошибка скачивания"; exit 1; }
[ -s "$BASE/sub.json" ] || { say "пустой ответ"; exit 1; }
say "скачано $(wc -c < $BASE/sub.json) байт"

# конфиг со всеми узлами — для проверки
/opt/bin/python3 "$BASE/build.py" >/dev/null 2>&1
[ -f "$BASE/config.json" ] || { say "build.py не собрал конфиг"; exit 1; }

/opt/etc/init.d/S95itx restart >/dev/null 2>&1
sleep 4

# страна выхода + задержка по каждому порту
: > /tmp/itx-geo.txt
cat > /tmp/itx_geo1.sh <<'SH'
#!/bin/sh
P=$1
LOC=$(/opt/bin/curl -s --max-time 8 --socks5-hostname 127.0.0.1:$P "https://www.cloudflare.com/cdn-cgi/trace" 2>/dev/null | sed -n 's/^loc=//p')
T=$(/opt/bin/curl -s -o /dev/null --max-time 6 --socks5-hostname 127.0.0.1:$P -w "%{time_total}" "http://www.gstatic.com/generate_204" 2>/dev/null)
[ -z "$LOC" ] && LOC=XX
[ -z "$T" ] && T=99
echo "$P $LOC $T" >> /tmp/itx-geo.txt
SH
chmod +x /tmp/itx_geo1.sh
P0=$(/opt/bin/python3 -c "
import json
m=json.load(open('/opt/etc/itx/meta.json'))
print(' '.join(str(x['port']) for x in m))
")
printf '%s\n' $P0 | xargs -I{} -P 10 /tmp/itx_geo1.sh {}
say "проверено узлов: $(wc -l < /tmp/itx-geo.txt)"

# финальный конфиг только из живых
/opt/bin/python3 "$BASE/build_final.py" >> $LOG 2>&1
/opt/etc/init.d/S95itx restart >/dev/null 2>&1
sleep 3

# перечит конфиг mihomo (провайдер socks обновился)
. /opt/etc/mihomo/ui.conf
S="${MIHOMO_SECRET:-change-me}"
/opt/bin/curl -s -o /dev/null --max-time 20 -X PUT -H "Authorization: Bearer $S" \
  -H "Content-Type: application/json" -d '{"path":"/opt/etc/mihomo/config.yaml"}' \
  "http://127.0.0.1:9090/configs?force=false" 2>/dev/null

CNT=$(grep -c '"type": "socks"' /opt/etc/mihomo/itx-proxies.yaml 2>/dev/null)
say "готово, узлов в модуле: $CNT"
