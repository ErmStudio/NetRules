#!/bin/sh
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
SRC=/opt/etc/mihomo
DST=/storage/mihomo-backup/$(date +%Y%m%d)
LOG=/opt/var/log/mihomo-backup.log
mkdir -p "$DST" || exit 1

# конфиги
for f in config.yaml template.yaml rules-proxy.yaml sub.url; do
  [ -f "$SRC/$f" ] && cp -f "$SRC/$f" "$DST/" 2>/dev/null
done
[ -f /opt/etc/nfqws2/nfqws2.conf ] && cp -f /opt/etc/nfqws2/nfqws2.conf "$DST/" 2>/dev/null
[ -f /opt/etc/dropbear/authorized_keys ] && cp -f /opt/etc/dropbear/authorized_keys "$DST/" 2>/dev/null

# скрипты и веб-морда (tar в прошивке не умеет создавать архивы)
mkdir -p "$DST/scripts"
cp -f "$SRC"/*.sh "$SRC"/*.py "$DST/scripts/" 2>/dev/null
cp -f "$SRC/lighttpd.conf" "$DST/scripts/" 2>/dev/null
cp -rf "$SRC/www" "$DST/scripts/" 2>/dev/null
for i in S96mihomo-watchdog S97mihomo-autoupdate S98mihomo-ui S99mihomo; do
  [ -f "/opt/etc/init.d/$i" ] && cp -f "/opt/etc/init.d/$i" "$DST/scripts/" 2>/dev/null
done

chmod 600 "$DST"/* 2>/dev/null
echo "$(date '+%F %T') бэкап: $DST (конфигов: $(ls "$DST" | wc -l), скриптов: $(ls "$DST/scripts" | wc -l))" >> $LOG

ls -1dt /storage/mihomo-backup/*/ 2>/dev/null | tail -n +8 | while read d; do rm -rf "$d"; done
if [ "$(wc -l < $LOG 2>/dev/null || echo 0)" -gt 100 ]; then tail -n 30 $LOG > $LOG.tmp && mv $LOG.tmp $LOG; fi