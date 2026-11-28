# NetRules — полная передача проекта

Документ для нового инженера (человека или ИИ). Читать сверху вниз: сначала суть, потом устройство, потом грабли.
Актуально на **28.11.2026**, версия **2.2.0**.

---

## 1. Что это

Панель управления прокси и обходом DPI на роутере **Keenetic Hopper KN-3811** (KeeneticOS 5.01, aarch64, Entware на USB).

Состав:
- **mihomo** 1.19.33 — прокси-ядро (режим `redir`), API на `127.0.0.1:9090`.
- **zapret / nfqws2** 1.0.7 — обход DPI для YouTube/Discord и пр., своя веб-морда на `:90`.
- **lighttpd** на `:8090` — отдаёт панель и `api.cgi` (docroot `/opt/etc/mihomo/www`).
- **Xray** (опционально) — для второй подписки на транспорте xhttp.

**Версия проекта:** файл `VERSION` (сейчас `2.2.0`), теги в GitHub `v2.2.0`, `v2.1.x`, `v1.9.x`…
**Репозиторий:** `git@github.com:ErmStudio/NetRules.git`, ветка `main`. Автор: Eugene Ermakov (Ermstudio), лицензия MIT + NOTICE (атрибуция обязательна).

---

## 2. Доступы и адреса

| Что | Значение |
|---|---|
| Роутер LAN | `192.168.1.1` |
| SSH (Entware dropbear) | порт `222`, `root`, пароль в сессии (не хранить в репо) |
| Панель NetRules | `http://192.168.1.1:8090` |
| UI mihomo (metacubexd) | `http://mihomo.lan:9090/ui/metacubexd/` |
| Zapret UI | `http://192.168.1.1:90` |
| Секрет API mihomo | в `/opt/etc/mihomo/ui.conf` (`MIHOMO_SECRET`) |

С Windows SSH удобно запускать через `SSH_ASKPASS`-хелпер (csc.exe), т.к. интерактивный ввод пароля недоступен.

---

## 3. Раскладка файлов

### На роутере

```
/opt/etc/mihomo/
  www/index.html          панель (всё в одном файле: HTML+CSS+JS)
  www/cgi-bin/api.cgi     CGI-API (posix sh + python3)
  config.yaml             сгенерированный конфиг mihomo (НЕ править руками — перезапишется)
  template.yaml           шаблон конфига (правим здесь; secret — плейсхолдер #SECRET#)
  rules-proxy.yaml        правила: что гнать через прокси (RULE-SET proxy-sites)
  rules-itx.yaml          правила Gemini → группа GEMINI
  rules-ads.yaml          правила блокировки рекламы (REJECT)
  itx-proxies.yaml        socks-прокси второй подписки (генерируется)
  ui.conf                 секреты и настройки (chmod 600)
  ui.conf.example         шаблон настроек
  update.sh / update.py   обновление основной подписки (sing-box JSON → YAML)
  speedtest.sh            замер скорости через отдельный порт 7893
  fullcheck.sh            проверка живости узлов + замер (обёртка)
  checkall.sh             проверка доступности всех узлов
  watchdog.sh             сторож mihomo: пробы, откаты, самовосстановление правил
  ensure_pin.sh           возврат на AUTO, если закреплённый узел мёртв после перезагрузки конфига
  route_check.py          мини-матчер правил: куда уйдёт запрос (без сети)
  tasks.sh                планировщик (заменяет cron)
  backup.sh               ежедневный бэкап в /storage/mihomo-backup/<дата>/
  backup-kit.sh           копия «restore-kit» на внутреннюю флешку /storage
  notify.sh               уведомления в Telegram
  quic_block.sh           блокировка QUIC к Google (для Gemini)
  rules.sh                применение/снятие iptables-правил (apply|clear)
  traffic_snapshot.sh     учёт трафика каждые 15 минут → traffic.csv
  traffic.csv             история трафика (date,download,upload)

/opt/etc/itx/             расширение «вторая подписка»
  sub.url                 ссылка подписки ITX
  sub.json                скачанный JSON (не бэкапится)
  build.py                JSON → Xray-конфиг со всеми узлами (для тестов)
  build_final.py          JSON → боевой Xray-конфиг (только живые узлы) + itx-proxies.yaml
  update.sh               полный цикл обновления второй подписки
  gemini_check.sh         проверка доступности Gemini через конкретный порт
  gemini_watch.sh         мягкий контроль: проверяет только текущий узел
  gemini_state.txt        результат последней проверки
  gemini_frozen.txt       «замороженные» узлы (name|until)
  blocklist.txt           чёрный список узлов (по IP)
  nodes.txt               name|port|remark|address

/opt/etc/init.d/
  S95itx                  запуск Xray
  S96mihomo-watchdog      сторож
  S97mihomo-autoupdate    планировщик
  S98mihomo-ui            lighttpd панели (:8090)
  S99mihomo               mihomo

/opt/var/log/
  mihomo.log, mihomo-speedtest.log, mihomo-watchdog.log,
  mihomo-update.log, mihomo-tasks.log, mihomo-backup.log, itx.log

/storage/mihomo-backup/<YYYYMMDD>/   ежедневные бэкапы (7 копий)
/storage/restore-kit/                аварийный комплект для восстановления
```

### В репозитории

```
router/www/index.html          копия панели
router/www/cgi-bin/api.cgi     копия API
router/scripts/*               копии скриптов
router/init.d/*                копии автозапуска
router/itx/*                   скрипты расширения (build*, update, gemini_*)
router/install.sh              установщик: базовый или `--itx`
docs/ARCHITECTURE.md           устройство
docs/API.md                    описание методов API
docs/RECOVERY.md               восстановление после поломки диска
docs/HANDOVER.md               этот документ
README.md, CHANGELOG.md, VERSION, LICENSE, NOTICE, CONTRIBUTING.md
```

---

## 4. Как ходит трафик

1. **iptables (nat)** заворачивает TCP 80/443 с `192.168.1.0/24` в цепочку `MH_REDIR` → REDIRECT на `7892` (redir-порт mihomo). Применяется `rules.sh apply`, а также из `S99mihomo` при старте.
2. **mihomo** по правилам решает: `PROXY` (chroma) / `ITX` (вторая подписка) / `DIRECT` / `REJECT`.
3. **zapret** отдельно обрабатывает часть трафика (YouTube и др.) через NFQUEUE.
4. **QUIC (UDP 443)** к подсетям Google отклоняется (`quic_block.sh`), чтобы браузеры падали на TCP и шли через прокси. Это критично для Gemini.

### Группы в mihomo

| Группа | Тип | Назначение |
|---|---|---|
| `AUTO` | url-test | все узлы chroma |
| `PROXY` | select | рабочий выбор: `AUTO` + узлы chroma + узлы ITX (`use: [itx]`) |
| `ITX` | select | только узлы второй подписки (SOCKS через Xray) |
| `GEMINI` | **fallback** | `ITX` → `ITXFAST` → `PROXY`: сначала узел ITX, потом другие узлы ITX, в крайнем случае закреплённый PROXY |
| `ITXFAST` | url-test | замер задержек узлов ITX |
| `TEST` | select | песочница для замера скорости (порт 7893) |

### Правила (порядок важен)

```
(в начале rules)  DoH → DIRECT: dns.google, cloudflare-dns.com, one.one.one.one,
                              dns.quad9.net, doh.opendns.com, 8.8.8.8/8.8.4.4/1.1.1.1/1.0.0.1
rules-ads.yaml      → REJECT (реклама, трекеры)
rules-itx.yaml      → GEMINI (вся сессия Gemini: веб, приложение, аккаунт, OneGoogle)
proxy-sites         → PROXY (openai, claude, photos.google, googlevideo, telegram-домены и др.)
MATCH               → DIRECT
```

---

## 5. Подписки

### Основная (chroma)
`update.sh` качает `sub.url` (sing-box JSON), `update.py` конвертирует в YAML-прокси, подставляет в `template.yaml`, пишет `config.yaml`. Применение — **горячей перезагрузкой** `PUT /configs` (без перезапуска, аптайм не рвётся).

Расписание: каждые `AUTO_SUB_H` часов (по умолчанию 4) или каждые `AUTO_SUB_M` минут (0 = выключено). Точка запуска — минута `:04`.

### Вторая (ITX, xhttp — mihomo не умеет)
Xray читает JSON подписки и поднимает **по одному SOCKS-порту на узел** (21101…21130), mihomo видит их как обычные socks5-прокси.

- `build.py` — все 70 узлов (для проверки).
- `build_final.py` — боевой набор: страна выхода через `cloudflare.com/cdn-cgi/trace` + задержка, исключаются RU/BY/CN/IR/KP/SY/CU и узлы медленнее 3 с.
- `update.sh` — полный цикл (скачать → проверить страны → собрать → перезапустить Xray → перезагрузить mihomo). Запускается вместе с основной подпиской и ежедневно.

Память Xray: ~33 МБ (от числа узлов почти не зависит).

### Чёрный список ITX
`blocklist.txt` — адреса узлов, исключаемых при сборке. Кнопка «Блэклист» в панели добавляет текущий узел и пересобирает модуль.

---

## 6. Выбор узла и замер скорости

- Замер идёт **через порт 7893** (listener `speedtest` → группа `TEST`), поэтому рабочий узел не переключается во время прогона. Победитель закрепляется в `PROXY` одним переключением в конце.
- Кандидаты: **половина из chroma + половина из ITX** (иначе ITX никогда не попадал в топ: у него +40–80 мс из-за лишнего хопа).
- Измерение: скачивание до 1.2 с (не больше 3 МБ), Мбит/с по фактически принятым байтам.
- Период: `SPEEDTEST_EVERY_H` (часы) или `SPEEDTEST_EVERY_M` (15/30 минут).

---

## 7. Gemini — самая тонкая часть

### Почему рвётся
Google определяет регион **не по одной странице**, а по совокупности служебных запросов сессии, и все они должны выходить из одной страны. Проверено на живом трафике (перехват `GET /connections` с `metadata.sniffHost`): у Gemini три независимых канала, и если хоть один уходит напрямую с российского IP, получается «смешанный регион».

### Какие хосты реально нужны (замерено, не догадки)
| Что | Хосты |
|---|---|
| веб, страница и история | `gemini.google.com`, `bard.google.com` |
| **веб, сам запрос и стрим ответа** | `geminiweb-pa.clients6.google.com` (WebChannel) |
| приложение (текст) | `robinfrontend-pa.googleapis.com` |
| приложение (realtime) | `pubsub.googleapis.com` |
| приложение/веб: файлы и AI Studio | `content-push.googleapis.com`, `alkalimakersuite-pa.clients6.google.com` |
| аккаунт и сессия | `accounts`, `myaccount`, `ogs`, `apis`, `consent`, `scone-pa`, `googleusercontent`, `photoslibrary` |

Симптом «страница открылась, история есть, но отправка падает» = `geminiweb-pa` шёл DIRECT. Симптом «в приложении не поддерживается страна» = `robinfrontend-pa` шёл DIRECT. История чатов при этом грузится, потому что она едет с `gemini.google.com`.

### Что сделано
1. Все хосты из таблицы — в `rules-itx.yaml` (группа `GEMINI`). Остальной Google (поиск, YouTube, `mtalk`/`fcm` — push, `play`/`android` — Play) намеренно **не** трогаем: иначе падение узла = нет пушей и нет Play.
2. QUIC к Google перекрыт (`quic_block.sh`), иначе браузер ходил UDP напрямую с RU-IP.
3. Группа `GEMINI` = fallback `ITX → ITXFAST → PROXY`: падение узла ITX больше не уводит Gemini в случайную (потенциально российскую) страну.
4. Watchdog раз в 30 минут проверяет **страну выхода туннеля** (запрос через `PROXY`, а не DIRECT); RU/BY/KZ → переключение на AUTO.
5. Российские узлы из подписки отбрасываются в `update.py` — автоматика не может тихо подменить страну.
6. **Терпение.** После смены маршрута Google пересчитывает регион не мгновенно: в проверенном случае приложение заработало через пару часов, голос — ещё через два. Не спешить менять правила каждые 10 минут.

### Как проверяется доступность
`gemini_check.sh <socks_port>`: запрос `https://gemini.google.com/` и поиск служебного флага `45631641`:
- `…":true` → **available**
- `…":false` → **partial** (страница открылась, но регион не нравится; часто лечится входом в аккаунт)
- 403/429 → **blocked**
- страница согласия/нет флага → **unknown**

Метод найден в проекте [routeprofiles](https://github.com/throneproj/routeprofiles).

### Мягкий контроль (`gemini_watch.sh`, раз в час в :20)
Проверяется **только текущий узел**. Недоступен → «заморозка» на 6 часов → перебор до 5 узлов **от самого быстрого** (по данным последнего замера) → первый доступный закрепляется в `ITX_PIN` и в группе `ITX`, уведомление в Telegram.

Массовую проверку всех узлов (кнопка «Gemini») использовать редко: 30 запросов с одного IP могут привлечь внимание Google.

---

## 8. UI панели (index.html)

Один файл, без сборки. Тёмная/светлая тема (`localStorage nr-theme`), горячие клавиши `1–6`, `R`, `V`, `Esc`.

Вкладки: **Обзор**, **Скорость**, **Сеть**, **Сервис**, **Правила**, **Логи**.

Обзор: карточки аптаймов/CPU(`%`)/RAM/узлов/обновления, «Текущий узел», «Трафик прокси», карточка «Узел ITX» (селект + Применить/Проверить/Gemini/Блэклист), карточка «Обновление подписки» (тумблер + периоды), 8 тумблеров: Прокси, Zapret, ITX, Google через ITX, Соцсети, Уведомления, Автоблокировка рекламы, Google видео.

Шапка: огоньки `mihomo / прокси / соцсети / видео / zapret / xray`.

Если второй подписки нет (`itx_available: 0` в `config`), все ITX-карточки **скрываются** — проект остаётся универсальным для одного провайдера.

---

## 9. API (`api.cgi`)

Методы: `status`, `config`, `version`, `self_update`, `update_log`, `rules_get/_set`,
`toggle_vpn/_social/_video/_zapret`, `speedtest`, `speed_last`, `nodecheck`, `health`, `conns`,
`add_rule`, `bulk_proxy`, `probe`, `myip`, `rename_device`, `backups`, `restore`, `history`,
`traffic_daily`, `notify_test`, `logs&f=`, `set_interval`, `set_autosub`, `fullcheck`,
`itx_list`, `itx_pick`, `itx_block`, `itx_on/_off`, `google_itx_on/_off`, `tg_notify_on/_off`,
`autosub_on/_off`, `ads_on/_off`, `gemini_check`, `route_check` (+`&host=`).

`route_check` — мини-матчер правил (`route_check.py`): читает `rules:` из `config.yaml` и локальные `rules-*.yaml`, отдаёт для каждого хоста `policy`/`rule`/`ok`. Сети не касается, поэтому работает даже когда прокси лежит. В панели — карточка **«Маршруты Gemini»** (раздел «Сервис»).

`config` отдаёт: `router`, `zapret`, `mihomo`, `version`, `subtitle`, `contact`, `interval`, `tg`, `itx_available`.

---

## 10. Планировщик (`tasks.sh`, цикл раз в минуту)

| Когда | Что |
|---|---|
| каждые 15 мин | снапшот трафика (`traffic.csv`) |
| каждые `SPEEDTEST_EVERY_H/M` | `fullcheck.sh` (живость + замер) |
| каждые `AUTO_SUB_H/M` | обновление основной подписки + ITX |
| 04:30 | обновление ITX (если ещё не обновилось) |
| :20 каждый час | `gemini_watch.sh` |
| 05:10 | бэкап + проверка `restore-kit` |

---

## 11. Грабли (проверено на практике)

- `sleep 0.3` **не работает** (busybox без FANCY_SLEEP) — только целые секунды.
- `pkill` есть не всегда; надёжнее `ps | awk` + `kill -9`.
- busybox `tar` умеет только распаковывать.
- **Keenetic (ndm) периодически перезаписывает nat-таблицу** — правило `MH_REDIR` пропадает, трафик уходит напрямую, Telegram отваливается. Watchdog проверяет `--to-ports 7892` и восстанавливает. Внимание: `iptables -S` печатает `--to-ports`, а не `redir ports`.
- Правила `IP-CIDR,…,no-resolve` **не матчатся для доменных запросов** — для Telegram нужны DOMAIN-SUFFIX-правила.
- `cat /proc/stat`: учитывать `iowait` как простой, иначе CPU% завышается в разы.
- Нельзя править `config.yaml` — он перегенерируется из `template.yaml`.
- Правки скриптов на диске не подхватываются уже запущенным процессом — перезапускать сервис.
- mihomo API: `PUT /configs?force=false` — горячая перезагрузка; `PUT /providers/rules/<name>` — только правила.
- `api.cgi` — POSIX sh; вставлять блоки только через python-скрипты (кавычки в PowerShell ломают heredoc).
- **DNS не трогать.** DoH (Google/Cloudflare) настроен у пользователя; любые правила, отправляющие DoH «напрямую», могут убить резолв. Этот урок уже получен. В версии 2.2.0 в начале `rules` стоят явные `DIRECT` для `dns.google`, `cloudflare-dns.com`, `one.one.one.one`, `dns.quad9.net`, `doh.opendns.com` и адресов `8.8.8.8/8.8.4.4/1.1.1.1/1.0.0.1` — не удалять.
- **Горячая перезагрузка конфига сбрасывает выбор в `PROXY`** и может поставить узел, которого уже нет в подписке: прокси-трафик висит до таймаута. Лечится `ensure_pin.sh` (вызывается из `update.sh` и watchdog). Проверять после любой перезагрузки.
- **`secret` в mihomo не применяется горячей перезагрузкой.** `PUT /configs` вернёт 204, но контроллер продолжит требовать старый секрет. Менять только через перезапуск `S99mihomo` и сразу перезапускать `S96`/`S97` — они держат секрет в переменных с момента старта.
- **`update.sh` должен сам читать `ui.conf`.** Без этого при ручном запуске `MIHOMO_SECRET` пустой, `PUT /configs` получает 401, а скрипт рапортует успех (порт-то открыт). Так уже терялись правки.
- **Регион Google проверяется по хостам, а не по странице.** Ловушки — `*-pa.clients6.google.com` (веб, WebChannel) и `*-pa.googleapis.com` (приложение). Если «страница открылась, а действие падает» — искать, какой служебный хост ушёл DIRECT.
- **Смотреть, куда реально ушло соединение:** `GET /connections`, поле `metadata.sniffHost` (не `metadata.host` — оно часто пустое) + `rule`, `rulePayload`, `chains`. Самый быстрый способ проверить правило без браузера.
- **Имена узлов ITX содержат пробелы** («ITX-28 NL 269ms»). Любые промежуточные таблицы и JSON — только с разделителем `|`, иначе поля съезжают и получается битый JSON (панель при этом показывает пустой список, ошибка глушится в `.catch()`).
- **`awk` печатает большие числа в экспоненте** (`7.58e+06`), а `sort -n` понимает только обычную запись — быстрые значения уезжают в конец. Перед сортировкой форматировать: `printf "%.0f"`.
- **Страна из `countries.txt` — это подпись из подписки, а не реальный выход.** Узел с подписью «Финляндия» выходил из Бразилии. Проверять только `https://ipinfo.io/country` через туннель.
- **Watchdog меряет страну только через домен, который реально идёт через `PROXY`.** `www.cloudflare.com` не попадает ни под одно правило → DIRECT → видит IP роутера (Россия). Именно это полгода давало ложные переключения каждые 30 минут.

---

## 12. Восстановление

См. `docs/RECOVERY.md`. Кратко: код из GitHub (`install.sh` или `--itx`), настройки из `/storage/mihomo-backup/<дата>/`, проверка `status`/`config`.

---

## 13. Стиль работы с владельцем

- Минимум изменений, всё обратимо. Сначала подтверждение — потом правки.
- Не трогать инфраструктуру (DNS, маршруты «полу-интернета») без явной просьбы.
- Честные цифры: если измерение шумит — признать, а не показывать красивое.
- Проверять результат после каждого шага (`sh -n`, статус, реальный запрос).
- Уведомления в Telegram — только о реальных проблемах (есть троттлинг 30 минут).
