# API NetRules

Все методы — `GET` или `POST` на `/cgi-bin/api.cgi?action=<метод>`. Ответ всегда JSON.
Идентификация не требуется: панель рассчитана на доверенную локальную сеть.

## Состояние

### `status`
```json
{
  "mihomo": 1, "vpn": 1, "video": 0, "social": 0, "zapret": 1, "tg": 0,
  "nodes": 221, "last": "OK|2026-11-26 06:00|221",
  "uptime": 100978, "memtotal": 497680, "memavail": 249472,
  "node": "20189311_vless_grpc_13443-2", "country": "Финляндия",
  "delay": "30", "mup": 1529, "load": "0.46", "mihomem": 67,
  "dl": 3519155, "ul": 5825769
}
```
- `mihomo` — слушает ли порт 7892
- `vpn` — включены ли правила (файл-намерение `/opt/var/run/mihomo.enabled`)
- `video` / `social` — есть ли соответствующие блоки в правилах
- `mup` — аптайм mihomo в секундах, `mihomem` — RSS в МБ, `load` — load average
- `dl` / `ul` — счётчики mihomo за текущую сессию

### `config`
```json
{"router":"http://192.168.1.1/","zapret":"http://192.168.1.1:90/","mihomo":"...","tg":0}
```

## Переключатели

`toggle_vpn`, `toggle_social`, `toggle_video`, `toggle_zapret`

Параметр `on=1` включает, `on=0` выключает, без параметра — инвертирует.
Правила применяются горячей перезагрузкой (`PUT /providers/rules/proxy-sites`),
без перезапуска mihomo.

## Правила

- `rules_get` → `{"rules": "payload:\n ..."}`
- `rules_set` (POST, тело `rules=<текст>`) — запись файла правил

## Сеть

### `conns`
```json
{
  "total": 113,
  "devices": [{"ip":"192.168.1.121","name":"Xiaomi","n":34,"dl":2005271}],
  "domains": [{"host":"api.telegram.org","n":5,"policy":"PROXY","rule":"RuleSet/proxy-sites","stalled":0,"stallsec":0,"ok":5}]
}
```
`stalled` — число зависших соединений, `stallsec` — максимальное время зависания,
`ok` — число соединений с полученными данными.

### `add_rule&host=<домен>&policy=proxy|direct|reject`
Добавляет правило и применяет его.

### `bulk_proxy&hosts=<домен1,домен2,...>`
Массово переводит домены в прокси. IP-адреса пропускаются (`skipped`).

### `probe&host=<домен|IP>`
Проверка доступности напрямую с роутера: `{"ok":true,"code":"200","sec":"0.46"}`.

### `myip`
Фактический IP и страна выхода через туннель (сервисы: ifconfig.co, myip.com, ipinfo.io).

## Скорость

- `speedtest` → замер топ-5 узлов и закрепление лучшего
- `speed_last` → последний результат
- `nodecheck` → полная проверка всех узлов (может занять ~20 с)
- `health` → последний результат проверки
- `history` → история задержки `{"points":[[epoch,ms],...]}`

## Трафик

`traffic_daily` → `{"rows":[["2026-11-27",549567,1757572], ...]}` — по дням, до 30 записей.

## Обслуживание

- `update` — обновить подписку
- `backup` — создать бэкап
- `backups` — список копий `{"items":[{"name":"20261127","kb":228,"ts":0}]}`
- `restore&dir=<имя>` — восстановить копию
- `restart` — перезапустить mihomo
- `notify_test` — тестовое уведомление в Telegram

## Логи

`logs&f=mihomo|update|watchdog|tasks|speed|zapret` → `{"log":"..."}`
