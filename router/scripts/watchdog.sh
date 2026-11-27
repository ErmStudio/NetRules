#!/bin/sh
# Watchdog mihomo: проверяет реальную работоспособность через прокси-порт.
# Больше не дёргает тест всей группы (227 узлов) и не снимает правила.
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
[ -f /opt/etc/mihomo/ui.conf ] && . /opt/etc/mihomo/ui.conf
SECRET="${MIHOMO_SECRET:-change-me}"
AUTH="Authorization: Bearer $SECRET"
API="${MIHOMO_API:-http://127.0.0.1:9090}"
LOG=/opt/var/log/mihomo-watchdog.log
PIDF=/opt/var/run/mihomo-watchdog.pid

if [ -f "$PIDF" ] && kill -0 "$(cat $PIDF 2>/dev/null)" 2>/dev/null; then
  echo "watchdog already running"
  exit 0
fi
echo $$ > $PIDF

fails=0
pinfails=0
restarts=0
soft=0
window=$(date +%s)

say() { echo "$(date '+%F %T') $1" >> $LOG; }

probe() {
  C=$(/opt/bin/curl -s -o /dev/null -w "%{http_code}" --max-time 8 \
      --proxy "http://127.0.0.1:7890" "http://www.gstatic.com/generate_204" 2>/dev/null)
  [ "$C" = "204" ]
}

set_auto() {
  /opt/bin/curl -s -o /dev/null --max-time 8 -X PUT -H "$AUTH" \
    -H "Content-Type: application/json" -d '{"name":"AUTO"}' "$API/proxies/PROXY" 2>/dev/null
}

now_node() {
  /opt/bin/curl -s --max-time 5 -H "$AUTH" "$API/proxies/PROXY" 2>/dev/null \
    | sed -n 's/.*"now":"\([^"]*\)".*/\1/p'
}

while true; do
  if ! netstat -ltn 2>/dev/null | grep -q ":7892"; then
    say "порт 7892 закрыт — поднимаю mihomo"
    /opt/etc/init.d/S99mihomo start >> $LOG 2>&1
    sleep 10
    continue
  fi

  # не мешаем проверке узлов
  if [ -f /tmp/mh-checking ] || [ -f /tmp/mh-fullcheck ]; then
    sleep 10
    continue
  fi

  if probe; then
    [ "$fails" -gt 0 ] && say "прокси снова отвечает"
    fails=0; soft=0

    # если узел закреплён вручную — проверяем именно его
    N=$(now_node)
    if [ -n "$N" ] && [ "$N" != "AUTO" ]; then
      D=$(/opt/bin/curl -s --max-time 6 -H "$AUTH" \
          "$API/proxies/$N/delay?url=http%3A%2F%2Fwww.gstatic.com%2Fgenerate_204&timeout=5000" 2>/dev/null)
      if echo "$D" | grep -q '"delay"'; then
        pinfails=0
      else
        pinfails=$((pinfails+1))
        say "закреплённый узел $N не отвечает ($pinfails из 2)"
        if [ "$pinfails" -ge 2 ]; then
          set_auto
          say "переключил на авто-выбор (AUTO)"
          /bin/sh /opt/etc/mihomo/notify.sh "NetRules: узел $N не отвечает, вернул авто-выбор" >/dev/null 2>&1 &
          pinfails=0
        fi
      fi
    fi
  else
    fails=$((fails+1))
    say "прокси не отвечает ($fails из 6)"

    if [ "$fails" -eq 3 ] && [ "$soft" = "0" ]; then
      set_auto
      soft=1
      say "мягкое лечение: переключил на авто-выбор без перезапуска"
      /bin/sh /opt/etc/mihomo/notify.sh "NetRules: прокси не отвечает, переключил на авто-выбор" >/dev/null 2>&1 &
      sleep 20
      continue
    fi

    if [ "$fails" -ge 6 ]; then
      now=$(date +%s)
      if [ $((now - window)) -gt 3600 ]; then restarts=0; window=$now; fi
      restarts=$((restarts+1))
      if [ "$restarts" -le 3 ]; then
        say "перезапуск mihomo ($restarts за час)"
        /opt/etc/init.d/S99mihomo restart >> $LOG 2>&1
        sleep 10
      else
        say "перезапусков уже 3 за час — жду, правила НЕ снимаю"
        /bin/sh /opt/etc/mihomo/notify.sh "NetRules: mihomo не отвечает, требуется разбор" >/dev/null 2>&1 &
        sleep 60
        restarts=0; window=$(date +%s)
      fi
      fails=0; soft=0
    fi
  fi

  if [ "$(wc -l < $LOG 2>/dev/null || echo 0)" -gt 300 ]; then
    tail -n 60 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
  fi
  sleep 60
done
