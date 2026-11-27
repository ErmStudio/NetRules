#!/bin/sh
# Синхронизация restore-kit на внутреннюю флешку и дополнение сегодняшнего бэкапа.
# Запускается из backup.sh и из S95restore-kit (раз в сутки).
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
SRC=/opt/etc/mihomo
KIT=/opt/etc/restore-kit
DST=/storage/mihomo-backup/$(date +%Y%m%d)
LOG=/opt/var/log/restore-kit.log
STATUS=$SRC/restore-kit-status.txt
LOCK=/tmp/restore-kit.lock

# не запускать два экземпляра одновременно
if [ -f "$LOCK" ]; then
  PID=$(cat "$LOCK" 2>/dev/null)
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    exit 0
  fi
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

# дополнительные файлы в сегодняшний бэкап (если backup.sh уже создал каталог)
if [ -d "$DST" ]; then
  for f in ui.conf VERSION countries.txt device-names.txt; do
    [ -f "$SRC/$f" ] && cp -f "$SRC/$f" "$DST/" 2>/dev/null
  done
  if [ -d /opt/etc/nfqws2/lists ]; then
    mkdir -p "$DST/nfqws2-lists"
    cp -f /opt/etc/nfqws2/lists/* "$DST/nfqws2-lists/" 2>/dev/null
  fi
fi

# restore-kit: копируем через временный каталог, чтобы не потерять старый при сбое
KIT_KB=0
if [ -d "$KIT" ]; then
  rm -rf /storage/restore-kit.new
  if cp -a "$KIT" /storage/restore-kit.new 2>/dev/null; then
    rm -rf /storage/restore-kit.old
    [ -d /storage/restore-kit ] && mv /storage/restore-kit /storage/restore-kit.old
    mv /storage/restore-kit.new /storage/restore-kit
    rm -rf /storage/restore-kit.old
    KIT_KB=$(du -sk /storage/restore-kit 2>/dev/null | awk '{print $1}')
    echo "$(date '+%F %T') restore-kit: ${KIT_KB:-?} КБ" >> $LOG
  else
    rm -rf /storage/restore-kit.new
    echo "$(date '+%F %T') ОШИБКА: restore-kit не скопирован" >> $LOG
  fi
fi

# права: S95 и скрипты должны быть исполняемыми после копирования по SMB
chmod 755 /opt/etc/mihomo/*.sh /opt/etc/init.d/S9* /opt/etc/init.d/S28mihomo 2>/dev/null

# поднять суточный watcher, если он ещё не запущен (после первого запуска/перезагрузки)
[ -x /opt/etc/init.d/S95restore-kit ] && /opt/etc/init.d/S95restore-kit start >/dev/null 2>&1

{
  echo "date: $(date '+%F %T')"
  echo "restore-kit-kb: ${KIT_KB:-0}"
  echo "daily-kb: $(du -sk "$DST" 2>/dev/null | awk '{print $1}')"
  echo "storage: $(df -k /storage 2>/dev/null | tail -1)"
  echo "s95: $(ls -l /opt/etc/init.d/S95restore-kit 2>/dev/null | awk '{print $1}')"
  echo "backup-kit: $(ls -l /opt/etc/mihomo/backup-kit.sh 2>/dev/null | awk '{print $1}')"
  echo "s95-pid: $(cat /opt/var/run/restore-kit.pid 2>/dev/null)"
  KITOK=1; MISS=""
  for f in mihomo/ui.conf mihomo/sub.url mihomo/config.yaml mihomo/www/index.html MANIFEST.txt restore-files.sh; do
    [ -s "/storage/restore-kit/$f" ] || { KITOK=0; MISS="$MISS $f"; }
  done
  echo "integrity: $([ "$KITOK" = "1" ] && echo OK || echo "FAIL:$MISS")"
} > "$STATUS" 2>/dev/null

if [ "$(wc -l < $LOG 2>/dev/null || echo 0)" -gt 100 ]; then
  tail -n 30 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
fi
