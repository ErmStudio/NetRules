#!/bin/sh
# NetRules — установка на Keenetic (Entware).
# Использование:
#   sh install.sh          — базовая установка (одна подписка)
#   sh install.sh --itx    — с расширением «вторая подписка» (Xray + ITX)
#
# Ожидает, что рядом лежат каталоги: www/, scripts/, init.d/ (из репозитория router/).

PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH

BASE=/opt/etc/mihomo
SRC=$(cd "$(dirname "$0")" && pwd)
ITX=0
[ "$1" = "--itx" ] && ITX=1

say() { printf '\033[1;36m==>\033[0m %s\n' "$1"; }
die() { printf '\033[1;31mОшибка:\033[0m %s\n' "$1"; exit 1; }

[ -d /opt/etc ] || die "нет Entware (/opt/etc). Установите Entware на USB-накопитель."
[ -d "$SRC/www" ] || die "не найден каталог www рядом с установщиком"

say "1/7 каталоги"
mkdir -p "$BASE" "$BASE/www/cgi-bin" /opt/var/log /opt/var/run || die "не создать каталоги"

say "2/7 файлы панели"
cp -f "$SRC/www/index.html" "$BASE/www/index.html" || die "index.html"
cp -f "$SRC/www/cgi-bin/api.cgi" "$BASE/www/cgi-bin/api.cgi" || die "api.cgi"
chmod +x "$BASE/www/cgi-bin/api.cgi"

say "3/7 скрипты"
for f in "$SRC"/scripts/*; do
  b=$(basename "$f")
  case "$b" in
    template.yaml|ui.conf.example|rules-*.yaml|countries.txt) cp -f "$f" "$BASE/$b" ;;
    *) cp -f "$f" "$BASE/$b"; chmod +x "$BASE/$b" ;;
  esac
done

say "4/7 настройки"
if [ ! -f "$BASE/ui.conf" ]; then
  cp -f "$BASE/ui.conf.example" "$BASE/ui.conf" 2>/dev/null || printf 'MIHOMO_API="http://127.0.0.1:9090"\nMIHOMO_SECRET="change-me"\n' > "$BASE/ui.conf"
  chmod 600 "$BASE/ui.conf"
  # секрет генерируем, а не оставляем change-me: в template.yaml стоит плейсхолдер #SECRET#,
  # update.py подставит это значение в config.yaml
  GEN=$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24)
  if [ -n "$GEN" ]; then
    sed -i "s|^MIHOMO_SECRET=.*|MIHOMO_SECRET=\"$GEN\"|" "$BASE/ui.conf"
    echo "   создан ui.conf, секрет API сгенерирован"
  else
    echo "   создан ui.conf — впишите MIHOMO_SECRET"
  fi
fi
[ -s "$BASE/sub.url" ] || { printf 'Вставьте ссылку подписки: '; read -r U; printf '%s\n' "$U" > "$BASE/sub.url"; }

say "5/7 автозапуск (init.d)"
for s in "$SRC"/init.d/S9*; do
  [ -f "$s" ] || continue
  b=$(basename "$s")
  [ "$b" = "S95itx" ] && [ "$ITX" = "0" ] && continue
  cp -f "$s" "/opt/etc/init.d/$b"; chmod +x "/opt/etc/init.d/$b"
done

say "6/7 первое обновление подписки"
[ -x "$BASE/update.sh" ] && sh "$BASE/update.sh" >/dev/null 2>&1
[ -f "$BASE/config.yaml" ] || die "конфиг не собрался — проверьте sub.url и update.sh"

if [ "$ITX" = "1" ]; then
  say "7/7 расширение: вторая подписка (Xray)"
  opkg install xray-core >/dev/null 2>&1
  mkdir -p /opt/etc/itx
  echo "   Вставьте ссылку второй подписки (ITX):"
  read -r U2
  printf '%s\n' "$U2" > /opt/etc/itx/sub.url
  echo "   Дальше: /opt/etc/itx/update.sh (или S95itx start после первой сборки)"
else
  say "7/7 расширение «вторая подписка» не выбрано — панель без карточек ITX"
fi

say "Готово. Панель: http://<ip-роутера>:8090"
say "Не забудьте включить прокси и правила: /opt/etc/mihomo/rules.sh apply"
