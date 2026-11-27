#!/bin/sh
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
BASE=/opt/etc/mihomo
LOG=/opt/var/log/mihomo-tasks.log
PIDF=/opt/var/run/mihomo-tasks.pid
[ -f /opt/etc/mihomo/ui.conf ] && . /opt/etc/mihomo/ui.conf
MIHOMO_API="${MIHOMO_API:-http://127.0.0.1:9090}"
MIHOMO_SECRET="${MIHOMO_SECRET:-change-me}"
SPEEDTEST_EVERY_H="${SPEEDTEST_EVERY_H:-3}"
NODEHEALTH_EVERY_H="${NODEHEALTH_EVERY_H:-6}"
if [ -f $PIDF ] && kill -0 "$(cat $PIDF 2>/dev/null)" 2>/dev/null; then
  echo "tasks already running"
  exit 0
fi
echo $$ > $PIDF

while true; do
  H=$(date +%H)
  HN=$(echo $H | sed "s/^0//")
  D=$(date +%d%m%Y)
  W=$(date +%w)

  # каждый час — точка истории задержки
  HM2=$(date +%Y%m%d%H)
  if [ "$HM2" != "$(cat $BASE/.last_hist 2>/dev/null)" ]; then
    echo "$HM2" > $BASE/.last_hist
    /opt/etc/mihomo/delayhist.sh
  fi
  # каждые 15 минут — снапшот трафика (устойчив к перезапускам mihomo)
  MN=$(date +%M)
  case "$MN" in
    00|15|30|45)
      MARK=$(date +%Y%m%d%H%M)
      if [ "$MARK" != "$(cat $BASE/.last_traffic 2>/dev/null)" ]; then
        echo "$MARK" > $BASE/.last_traffic
        /opt/etc/mihomo/traffic_snapshot.sh
      fi
      ;;
  esac

  # 06:00 ежедневно — обновление подписки
  if [ "$H" = "06" ] && [ "$D" != "$(cat $BASE/.last_sub 2>/dev/null)" ]; then
    echo "$D" > $BASE/.last_sub
    echo "$(date '+%F %T') задача: обновление подписки" >> $LOG
    /opt/etc/mihomo/update.sh
  fi

  # 05:10 ежедневно — бэкап конфигов
  if [ "$H" = "05" ] && [ "$D" != "$(cat $BASE/.last_backup 2>/dev/null)" ]; then
    echo "$D" > $BASE/.last_backup
    /opt/etc/mihomo/backup.sh
  fi

  # каждые 2 часа — замер скорости узлов и закрепление лучшего
  HM=$(date +%Y%m%d%H)
  if [ "$SPEEDTEST_EVERY_H" -gt 0 ] && [ $((HN % SPEEDTEST_EVERY_H)) -eq 0 ] && [ "$HM" != "$(cat $BASE/.last_speed 2>/dev/null)" ]; then
    echo "$HM" > $BASE/.last_speed
    echo "$(date '+%F %T') задача: проверка узлов и замер скорости" >> $LOG
    /opt/etc/mihomo/fullcheck.sh
  fi
  # 05:00 по воскресеньям — обновление пакета mihomo
  if [ "$H" = "05" ] && [ "$W" = "0" ] && [ "$D" != "$(cat $BASE/.last_pkg 2>/dev/null)" ]; then
    echo "$D" > $BASE/.last_pkg
    echo "$(date '+%F %T') задача: обновление пакета mihomo" >> $LOG
    opkg update >/dev/null 2>&1
    BEFORE=$(opkg list-installed mihomo 2>/dev/null | awk '{print $3}')
    opkg upgrade mihomo >> $LOG 2>&1
    AFTER=$(opkg list-installed mihomo 2>/dev/null | awk '{print $3}')
    echo "$(date '+%F %T') версия: $BEFORE -> $AFTER" >> $LOG
    if [ "$BEFORE" != "$AFTER" ]; then
      /opt/etc/init.d/S99mihomo restart >> $LOG 2>&1
      sleep 8
      if netstat -ltn 2>/dev/null | grep -q ":7892"; then
        echo "$(date '+%F %T') после обновления mihomo работает" >> $LOG
      else
        echo "$(date '+%F %T') ВНИМАНИЕ: mihomo не поднялся после обновления пакета" >> $LOG
      fi
    fi
  fi

  if [ "$(wc -l < $LOG 2>/dev/null || echo 0)" -gt 200 ]; then tail -n 50 $LOG > $LOG.tmp && mv $LOG.tmp $LOG; fi
  sleep 300
done