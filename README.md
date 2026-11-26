# NetRules

Веб-панель управления маршрутизатором **Keenetic** с mihomo (Clash Meta) и zapret2.
Тёмный интерфейс, живые статусы, переключение правил в один клик, замер скорости узлов и мониторинг их здоровья.

> Сделано в **Ermstudio**.

---

## Возможности

**Панель (вкладка «Обзор»)**
- Статус mihomo, VPN-правил, соцсетей, видео и zapret — цветными индикаторами.
- Карточки: аптайм роутера, число узлов и живых из них, свободная RAM, текущий узел с задержкой и страной, трафик сессии, дата обновления подписки.
- Четыре независимых переключателя: VPN-прокси, соцсети, видео Google, zapret.
- Кнопки: обновить подписку, бэкап, перезапуск mihomo, переход в панель mihomo.

**Скорость**
- Замер скорости топ-5 узлов (реальная загрузка 2 МБ через каждый) и автоматическое закрепление лучшего.
- Полная проверка всех узлов: сколько живых и мёртвых, список неотвечающих.
- Автоматический замер каждые 2 часа и после каждого обновления подписки.

**Правила**
- Полный редактор списка правил mihomo прямо в браузере, с сохранением и применением.
- Переключатели лишь добавляют/убирают блоки в этом же файле — источник истины один.

**Логи**
- Шесть вкладок: mihomo, обновление, watchdog, задачи, скорость, zapret.
- Автообновление, тёмная тема, отдельная прокрутка.

**Устойчивость**
- Watchdog проверяет прокси каждые 60 секунд; при трёх сбоях перезапускает mihomo, при исчерпании лимита снимает правила (fail-safe).
- Если закреплённый узел умирает — возвращается авто-выбор по пингу и запускается новый замер.
- Ежедневный бэкап конфигов на внутреннюю флешку, ротация логов.

---

## Архитектура

```
Клиент ──► mangle MARK ──► nat REDIRECT :7892 ──► mihomo ──► PROXY / DIRECT
                                                        │
DIRECT ──► POSTROUTING ──► nfqws2 (zapret) ──► провайдер
```

- LAN-трафик на 80/443 помечается и уходит в mihomo (`redir`).
- mihomo решает: `PROXY` (туннель) или `DIRECT`.
- `DIRECT` отдаётся zapret2 для обхода DPI.
- DNS — DoH (Cloudflare + Google), зона `logistik.ru` — на корпоративный DNS.

Подробности — в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Установка

Требуется: Keenetic с Entware на USB, установленные `mihomo`, `zapret2`, `lighttpd`, `python3`, `curl`.

1. Скопируйте содержимое `router/` на роутер:

```sh
# скрипты
cp scripts/*.sh scripts/update.py scripts/rules-proxy.yaml /opt/etc/mihomo/
chmod +x /opt/etc/mihomo/*.sh

# веб-панель
mkdir -p /opt/etc/mihomo/www/cgi-bin
cp www/index.html /opt/etc/mihomo/www/
cp www/cgi-bin/api.cgi /opt/etc/mihomo/www/cgi-bin/
chmod +x /opt/etc/mihomo/www/cgi-bin/api.cgi

# автозапуск
cp init.d/S9* /opt/etc/init.d/
chmod +x /opt/etc/init.d/S9*
```

2. Создайте `/opt/etc/mihomo/ui.conf` (см. `scripts/ui.conf.example`) и поменяйте секрет.
3. Перезапустите: `/opt/etc/init.d/S98mihomo-ui restart` и `/opt/etc/init.d/S99mihomo restart`.
4. Откройте `http://<router>:8090/`.

---

## Настройка

`/opt/etc/mihomo/ui.conf`:

```sh
MIHOMO_API="http://127.0.0.1:9090"
MIHOMO_SECRET="ваш-секрет"
```

Секрет должен совпадать с `secret` в конфиге mihomo (`external-controller`).

---

## API

Все методы — `GET/POST /cgi-bin/api.cgi?action=...`:

| action | назначение |
|---|---|
| `status` | состояние: mihomo, vpn, видео, соцсети, zapret, узлы, RAM, трафик, текущий узел |
| `rules_get` / `rules_set` | чтение и запись списка правил |
| `toggle_vpn` / `toggle_social` / `toggle_video` / `toggle_zapret` | переключатели |
| `speedtest` / `speed_last` | замер топ-5 узлов и последний результат |
| `nodecheck` / `health` | полная проверка узлов и её результат |
| `update` / `backup` / `restart` | обслуживание |
| `logs&f=mihomo\|update\|watchdog\|tasks\|speed\|zapret` | логи |

---

## Структура

```
router/
  www/index.html          интерфейс (одна страница, вкладки)
  www/cgi-bin/api.cgi     JSON API поверх CGI
  scripts/
    speedtest.sh          замер скорости и закрепление лучшего узла
    check1.sh             проверка одного узла
    checkall.sh           проверка всех узлов
    watchdog.sh           сторож с фейловером
    tasks.sh              расписание: подписка, бэкап, тесты
    update.sh / update.py обновление подписки и конвертация
    rules.sh              iptables-правила mihomo
    supervise.sh          супервизор запуска
    backup.sh             бэкап на внутреннюю флешку
    lighttpd.conf         веб-сервер панели (:8090)
    rules-proxy.yaml      список правил
  init.d/                 автозапуск S96–S99
docs/ARCHITECTURE.md      как это устроено
```

---

## Лицензия

MIT — см. [LICENSE](LICENSE).

Автор: **Ermstudio**.
