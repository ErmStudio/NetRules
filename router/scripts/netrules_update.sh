#!/bin/sh
# Обновление NetRules из GitHub.
# Использование: netrules_update.sh [force]
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
BASE=/opt/etc/mihomo
REPO="${NETRULES_REPO:-EugeneErmakov/NetRules}"
BRANCH="${NETRULES_BRANCH:-main}"
TMP=/tmp/netrules-upd
RES=$BASE/update_result.json
LOG=/opt/var/log/netrules-update.log

say() { echo "$(date '+%F %T') $1" >> $LOG; }
fail() {
  printf '{"ok":false,"error":"%s"}\n' "$1" > $RES
  say "ОШИБКА: $1"
  rm -rf $TMP
  exit 1
}

LOCAL=$(cat $BASE/VERSION 2>/dev/null | tr -d '\r\n')
[ -z "$LOCAL" ] && LOCAL="0.0.0"

REMOTE=$(/opt/bin/curl -s --max-time 20 "https://raw.githubusercontent.com/$REPO/$BRANCH/VERSION" 2>/dev/null | tr -d '\r\n ')
[ -z "$REMOTE" ] && fail "нет связи с GitHub"

if [ "$LOCAL" = "$REMOTE" ] && [ "$1" != "force" ]; then
  printf '{"ok":true,"uptodate":true,"local":"%s","remote":"%s"}\n' "$LOCAL" "$REMOTE" > $RES
  say "уже последняя версия $LOCAL"
  exit 0
fi

say "обновление $LOCAL -> $REMOTE"
rm -rf $TMP; mkdir -p $TMP
/opt/bin/curl -sL --max-time 180 -o $TMP/src.tgz \
  "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH" || fail "не скачался архив"
[ -s $TMP/src.tgz ] || fail "пустой архив"

tar xzf $TMP/src.tgz -C $TMP 2>/dev/null || fail "не распаковался архив"
DIR=$(ls -d $TMP/NetRules-* 2>/dev/null | head -1)
[ -n "$DIR" ] && [ -d "$DIR/router/www" ] || fail "неожиданная структура архива"

# бэкап текущего состояния
BK=/storage/netrules-backup/$(date +%Y%m%d-%H%M%S)
mkdir -p "$BK" 2>/dev/null
cp -a $BASE/www "$BK/" 2>/dev/null
cp -a $BASE/*.sh "$BK/" 2>/dev/null
cp -f $BASE/VERSION "$BK/VERSION" 2>/dev/null

# код (пользовательские данные не трогаем)
cp -f "$DIR/router/www/index.html" $BASE/www/ 2>/dev/null
cp -f "$DIR/router/www/cgi-bin/api.cgi" $BASE/www/cgi-bin/ 2>/dev/null
for f in "$DIR"/router/scripts/*.sh "$DIR/router/scripts/update.py" "$DIR/router/scripts/lighttpd.conf"; do
  [ -f "$f" ] || continue
  b=$(basename "$f")
  case "$b" in
    ui.conf|rules-proxy.yaml) continue ;;
  esac
  cp -f "$f" $BASE/"$b" 2>/dev/null
done
chmod +x $BASE/*.sh $BASE/www/cgi-bin/api.cgi 2>/dev/null
echo "$REMOTE" > $BASE/VERSION

rm -rf $TMP
printf '{"ok":true,"uptodate":false,"local":"%s","remote":"%s","backup":"%s"}\n' "$LOCAL" "$REMOTE" "$BK" > $RES
say "обновлено до $REMOTE, бэкап: $BK"

# перезапуск интерфейса и демонов — после ответа
( sleep 1
  /opt/etc/init.d/S98mihomo-ui restart >/dev/null 2>&1
  for d in tasks watchdog; do
    pf=/opt/var/run/mihomo-$d.pid
    [ -f $pf ] && kill "$(cat $pf)" 2>/dev/null
    rm -f $pf
  done
  /opt/etc/init.d/S97mihomo-autoupdate start >/dev/null 2>&1
  /opt/etc/init.d/S96mihomo-watchdog start >/dev/null 2>&1
) >/dev/null 2>&1 &

exit 0
