#!/bin/sh
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
SRC=/opt/etc/mihomo
DST=/storage/mihomo-backup/$(date +%Y%m%d)
LOG=/opt/var/log/mihomo-backup.log
KIT=/opt/etc/restore-kit
STATUS=$SRC/restore-kit-status.txt
mkdir -p "$DST" || exit 1

# конфиги
for f in config.yaml template.yaml rules-proxy.yaml rules-itx.yaml rules-ads.yaml sub.url ui.conf ui.conf.example VERSION countries.txt device-names.txt; do
  [ -f "$SRC/$f" ] && cp -f "$SRC/$f" "$DST/" 2>/dev/null
done
[ -f /opt/etc/nfqws2/nfqws2.conf ] && cp -f /opt/etc/nfqws2/nfqws2.conf "$DST/" 2>/dev/null
[ -f /opt/etc/dropbear/authorized_keys ] && cp -f /opt/etc/dropbear/authorized_keys "$DST/" 2>/dev/null

# списки zapret (раньше не бэкапились)
if [ -d /opt/etc/nfqws2/lists ]; then
  mkdir -p "$DST/nfqws2-lists"
  cp -f /opt/etc/nfqws2/lists/* "$DST/nfqws2-lists/" 2>/dev/null
fi

# расширение «вторая подписка» (если установлено)
if [ -d /opt/etc/itx ]; then
  mkdir -p "$DST/itx"
  for f in sub.url blocklist.txt nodes.txt config.json; do
    [ -f "/opt/etc/itx/$f" ] && cp -f "/opt/etc/itx/$f" "$DST/itx/" 2>/dev/null
  done
  cp -f /opt/etc/itx/*.sh /opt/etc/itx/*.py "$DST/itx/" 2>/dev/null
fi
# скрипты и веб-морда (tar в прошивке не умеет создавать архивы)
mkdir -p "$DST/scripts"
cp -f "$SRC"/*.sh "$SRC"/*.py "$DST/scripts/" 2>/dev/null
cp -f "$SRC/lighttpd.conf" "$DST/scripts/" 2>/dev/null
cp -rf "$SRC/www" "$DST/scripts/" 2>/dev/null
for i in S95itx S96mihomo-watchdog S97mihomo-autoupdate S98mihomo-ui S99mihomo; do
  [ -f "/opt/etc/init.d/$i" ] && cp -f "/opt/etc/init.d/$i" "$DST/scripts/" 2>/dev/null
done

chmod 600 "$DST"/* 2>/dev/null
chmod 600 "$DST/nfqws2-lists"/* 2>/dev/null
echo "$(date '+%F %T') бэкап: $DST (конфигов: $(ls "$DST" | wc -l), скриптов: $(ls "$DST/scripts" | wc -l))" >> $LOG

# --- restore-kit на внутреннюю флешку (переживает смерть USB) ---
sync_kit() {
  [ -d "$KIT" ] || return 1
  rm -rf /storage/restore-kit.new
  if cp -a "$KIT" /storage/restore-kit.new 2>/dev/null; then
    rm -rf /storage/restore-kit.old
    [ -d /storage/restore-kit ] && mv /storage/restore-kit /storage/restore-kit.old
    mv /storage/restore-kit.new /storage/restore-kit
    rm -rf /storage/restore-kit.old
    return 0
  fi
  rm -rf /storage/restore-kit.new
  return 1
}

KIT_KB=0
if sync_kit; then
  KIT_KB=$(du -sk /storage/restore-kit 2>/dev/null | awk '{print $1}')
  echo "$(date '+%F %T') restore-kit обновлён: ${KIT_KB:-?} КБ" >> $LOG
else
  echo "$(date '+%F %T') ВНИМАНИЕ: restore-kit не скопирован" >> $LOG
fi
# проверка целостности restore-kit: ключевые файлы должны быть на месте
KITOK=1
MISSING=""
for f in ui.conf sub.url config.yaml scripts/www/index.html scripts/www/cgi-bin/api.cgi; do
  if [ ! -s "/storage/restore-kit/$f" ]; then
    KITOK=0
    MISSING="$MISSING $f"
  fi
done
{
  echo "date: $(date '+%F %T')"
  echo "restore-kit-kb: ${KIT_KB:-0}"
  echo "daily-kb: $(du -sk "$DST" 2>/dev/null | awk '{print $1}')"
  echo "integrity: $([ "$KITOK" = "1" ] && echo OK || echo "FAIL:${MISSING}")"
  echo "storage: $(df -k /storage 2>/dev/null | tail -1)"
} > "$STATUS" 2>/dev/null
if [ "$KITOK" = "0" ]; then
  echo "$(date '+%F %T') restore-kit НЕПОЛНЫЙ:$MISSING" >> $LOG
  /bin/sh /opt/etc/mihomo/notify.sh "NetRules: restore-kit неполный —$MISSING" >/dev/null 2>&1 &
fi

# ротация ежедневных бэкапов: 7 копий
ls -1dt /storage/mihomo-backup/*/ 2>/dev/null | tail -n +8 | while read d; do rm -rf "$d"; done
if [ "$(wc -l < $LOG 2>/dev/null || echo 0)" -gt 100 ]; then tail -n 30 $LOG > $LOG.tmp && mv $LOG.tmp $LOG; fi

# отдельный скрипт синхронизации kit — живёт независимо от обновлений NetRules
[ -f /opt/etc/mihomo/backup-kit.sh ] && /bin/sh /opt/etc/mihomo/backup-kit.sh
