#!/bin/sh
# Совмещённая проверка: живость всех узлов + замер скорости и закрепление лучшего.
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
LOCK=/tmp/mh-fullcheck
LOG=/opt/var/log/mihomo-speedtest.log

if [ -f "$LOCK" ]; then
  echo "$(date '+%F %T') fullcheck уже идёт, пропуск" >> $LOG
  exit 0
fi
touch "$LOCK"
trap 'rm -f $LOCK' EXIT

/bin/sh /opt/etc/mihomo/checkall.sh >/dev/null 2>&1
sleep 1
/bin/sh /opt/etc/mihomo/speedtest.sh >/dev/null 2>&1
