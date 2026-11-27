#!/bin/sh
# Проверка доступности Gemini через конкретный SOCKS-порт ITX.
# Использование: gemini_check.sh <socks_port>
# Вывод: available | partial | blocked | unknown
PORT="$1"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
BODY=/tmp/gm-$PORT.html

CODE=$(/opt/bin/curl -s -o "$BODY" -w "%{http_code}" --max-time 15 \
       --socks5-hostname 127.0.0.1:"$PORT" -A "$UA" \
       "https://gemini.google.com/" 2>/dev/null)
[ -z "$CODE" ] && { echo unknown; exit; }

case "$CODE" in
  403|429) echo blocked; exit ;;
esac

# согласие на cookies — реальную проверку не пройти
if grep -q "consent\." "$BODY" 2>/dev/null; then echo unknown; exit; fi

# флаг доступности в служебном объекте страницы
if grep -q '45631641\\\?":true\|,null,true' "$BODY" 2>/dev/null; then
  echo available
elif grep -q '45631641\\\?":false' "$BODY" 2>/dev/null; then
  echo partial
else
  echo unknown
fi
rm -f "$BODY"
