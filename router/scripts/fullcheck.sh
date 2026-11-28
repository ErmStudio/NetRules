#!/bin/sh
# Совмещённая проверка: живость всех узлов + замер скорости и закрепление лучшего.
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
LOCK=/tmp/mh-fullcheck
LOG=/opt/var/log/mihomo-speedtest.log

# lock с отметкой времени: если прошлый прогон убили (kill -9, перезагрузка),
# файл оставался навсегда и fullcheck больше никогда не запускался
if [ -f "$LOCK" ]; then
  TS=$(cat "$LOCK" 2>/dev/null)
  case "$TS" in ''|*[!0-9]*) TS=0 ;; esac
  if [ "$TS" -gt 0 ] && [ $(( $(date +%s) - TS )) -lt 1800 ]; then
    echo "$(date '+%F %T') fullcheck уже идёт, пропуск" >> $LOG
    exit 0
  fi
  echo "$(date '+%F %T') снят зависший lock fullcheck" >> $LOG
  rm -f "$LOCK"
fi
date +%s > "$LOCK"
trap 'rm -f $LOCK' EXIT

/bin/sh /opt/etc/mihomo/checkall.sh >/dev/null 2>&1
sleep 1
/bin/sh /opt/etc/mihomo/speedtest.sh >/dev/null 2>&1
