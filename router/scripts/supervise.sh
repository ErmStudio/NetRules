#!/bin/sh
# Держит mihomo живым. Пока он работает — правила включены; как только умер — правила снимаются сразу.
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
BASE=/opt/etc/mihomo
LOG=/opt/var/log/mihomo.log
WLOG=/opt/var/log/mihomo-watchdog.log
PIDF=/opt/var/run/mihomo-supervisor.pid

echo $$ > $PIDF

if netstat -ltn 2>/dev/null | grep -q ":7892"; then
  echo "$(date '+%F %T') mihomo уже работает" >> $WLOG
else
  /opt/bin/mihomo -d $BASE -f $BASE/config.yaml </dev/null >>$LOG 2>&1 &
  MPID=$!
  echo $MPID > /opt/var/run/mihomo.pid
  i=0
  while [ $i -lt 30 ]; do
    netstat -ltn 2>/dev/null | grep -q ":7892" && break
    kill -0 $MPID 2>/dev/null || break
    sleep 1; i=$((i+1))
  done
  if netstat -ltn 2>/dev/null | grep -q ":7892"; then
    /opt/etc/mihomo/rules.sh apply
    echo "$(date '+%F %T') mihomo запущен, правила включены" >> $WLOG
  else
    /opt/etc/mihomo/rules.sh clear
    echo "$(date '+%F %T') mihomo НЕ запустился, правила выключены" >> $WLOG
  fi
fi

# ждём завершения mihomo (своего или чужого) и снимаем правила
while netstat -ltn 2>/dev/null | grep -q ":7892"; do
  sleep 3
done
/opt/etc/mihomo/rules.sh clear
rm -f $PIDF
echo "$(date '+%F %T') mihomo остановлен, правила сняты" >> $WLOG