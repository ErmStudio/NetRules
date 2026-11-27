#!/bin/sh
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
BASE=/opt/etc/mihomo
LOG=/opt/var/log/mihomo-update.log
STATUS=$BASE/last_update.txt
URL=$(cat $BASE/sub.url 2>/dev/null)

now() { date "+%Y-%m-%d %H:%M"; }
fail() { echo "FAIL|$(now)|$1" > $STATUS; echo "$(now) FAIL: $1" >> $LOG; exit 1; }

[ -z "$URL" ] && fail "нет sub.url"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') update start ===" >> $LOG
/opt/bin/wget -q -U "mihomo/1.19.33" -O "$BASE/sub.json" "$URL" || fail "не скачалась подписка"
echo "downloaded $(wc -c < $BASE/sub.json) bytes" >> $LOG
OUT=$(/opt/bin/python3 "$BASE/update.py" 2>&1)
echo "$OUT" >> $LOG
NODES=$(printf "%s\n" "$OUT" | grep "^ok, nodes=" | tail -1)
echo "$NODES" | grep -q '^ok, nodes=' || fail "конвертация не удалась"
CNT=$(echo "$NODES" | sed 's/.*nodes=//')
/opt/etc/init.d/S99mihomo restart >> $LOG 2>&1
sleep 2
if netstat -ltn 2>/dev/null | grep -q ":7892"; then
  echo "OK|$(now)|$CNT" > $STATUS
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') update done, nodes=$CNT ===" >> $LOG
  ( sleep 2; /opt/etc/mihomo/speedtest.sh >/dev/null 2>&1; sleep 1; /opt/etc/mihomo/checkall.sh >/dev/null 2>&1 ) &
else
  echo "mihomo не поднялся, откатываю конфиг" >> $LOG
  cp -f $BASE/config.yaml.bak $BASE/config.yaml
  /opt/etc/init.d/S99mihomo restart >> $LOG 2>&1
  sleep 3
  if netstat -ltn 2>/dev/null | grep -q ":7892"; then
    fail "новый конфиг не заработал, откатился на предыдущий"
  else
    fail "mihomo не поднимается и после отката"
  fi
fi

# ротация лога: держим последние 60 строк
if [ "$(wc -l < $LOG)" -gt 200 ]; then
  tail -n 60 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
fi