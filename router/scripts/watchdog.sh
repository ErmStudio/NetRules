#!/bin/sh
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
LOG=/opt/var/log/mihomo-watchdog.log
PIDF=/opt/var/run/mihomo-watchdog.pid
API="http://127.0.0.1:9090/proxies/AUTO/delay?url=http%3A%2F%2Fwww.gstatic.com%2Fgenerate_204&timeout=6000"

echo $$ > $PIDF

fails=0
pinfails=0
restarts=0
window=$(date +%s)

# Если узел закреплён вручную (PROXY != AUTO) и перестал отвечать —
# возвращаем авто-выбор и запускаем новый замер скорости в фоне.
check_pinned() {
  NOW=$(/opt/bin/curl -s --max-time 5 -H "$AUTH" http://127.0.0.1:9090/proxies/PROXY 2>/dev/null \
        | sed -n 's/.*"now":"\([^"]*\)".*/\1/p')
  case "$NOW" in
    ""|AUTO) pinfails=0; return ;;
  esac
  R=$(/opt/bin/curl -s --max-time 8 -H "$AUTH" \
      "http://127.0.0.1:9090/proxies/$NOW/delay?url=http%3A%2F%2Fwww.gstatic.com%2Fgenerate_204&timeout=5000" 2>/dev/null)
  if echo "$R" | grep -q '"delay"'; then
    pinfails=0
  else
    pinfails=$((pinfails+1))
    echo "$(date '+%F %T') закреплённый узел $NOW не отвечает ($pinfails из 2)" >> $LOG
    if [ "$pinfails" -ge 2 ]; then
      /opt/bin/curl -s -o /dev/null --max-time 8 -X PUT -H "$AUTH" -H "Content-Type: application/json" \
        -d '{"name":"AUTO"}' http://127.0.0.1:9090/proxies/PROXY 2>/dev/null
      echo "$(date '+%F %T') узел умер — вернул авто-выбор по пингу (AUTO)" >> $LOG
      /bin/sh /opt/etc/mihomo/notify.sh "NetRules: узел $NOW не отвечает, вернул авто-выбор" >/dev/null 2>&1 &
      ( /opt/etc/mihomo/speedtest.sh >/dev/null 2>&1 & )
      pinfails=0
    fi
  fi
}

while true; do
  if ! netstat -ltn 2>/dev/null | grep -q ":7892"; then
    echo "$(date '+%F %T') порт 7892 закрыт, поднимаю" >> $LOG
    /opt/etc/init.d/S99mihomo start >> $LOG 2>&1
    sleep 10
  else
    R=$(/opt/bin/wget -q -O - --timeout=8 --tries=1 --header="$AUTH" "$API" 2>/dev/null)
    if echo "$R" | grep -q '"delay"'; then
      if [ "$fails" -gt 0 ]; then
        echo "$(date '+%F %T') проверка снова проходит" >> $LOG
      fi
      fails=0
      check_pinned
    else
      fails=$((fails+1))
      echo "$(date '+%F %T') проверка прокси не прошла ($fails из 3)" >> $LOG
      if [ "$fails" -ge 3 ]; then
        now=$(date +%s)
        if [ $((now - window)) -gt 3600 ]; then restarts=0; window=$now; fi
        restarts=$((restarts+1))
        if [ "$restarts" -le 3 ]; then
          echo "$(date '+%F %T') похоже завис, перезапуск ($restarts за час)" >> $LOG
          /bin/sh /opt/etc/mihomo/notify.sh "NetRules: mihomo завис, перезапуск #$restarts" >/dev/null 2>&1 &
          /opt/etc/init.d/S99mihomo restart >> $LOG 2>&1
        else
          echo "$(date '+%F %T') лимит перезапусков исчерпан — снимаю правила, нужен разбор" >> $LOG
          /bin/sh /opt/etc/mihomo/notify.sh "NetRules: mihomo не поднимается, правила сняты — нужен разбор" >/dev/null 2>&1 &
          /opt/etc/mihomo/rules.sh clear
          restarts=0; window=$now
        fi
        fails=0
        sleep 10
      fi
    fi
  fi
  if [ "$(wc -l < $LOG 2>/dev/null || echo 0)" -gt 300 ]; then tail -n 60 $LOG > $LOG.tmp && mv $LOG.tmp $LOG; fi
  sleep 60
done
