# NetRules

**Веб-панель управления маршрутизатором Keenetic: mihomo (Clash Meta) + zapret2.**
Тёмный интерфейс, живой мониторинг, переключение правил в один клик, замер скорости узлов и проверка их здоровья.

[![Version](https://img.shields.io/badge/version-1.2.2-4f8cff.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-4f8cff.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-Keenetic-22d3ee)
![Shell](https://img.shields.io/badge/shell-POSIX-34d399)

> Сделано в **Ermstudio** · автор [Eugene Ermakov](https://github.com/ErmStudio)
> Репозиторий: **https://github.com/ErmStudio/NetRules** · [релизы](https://github.com/ErmStudio/NetRules/tags)

---

## Что умеет

**Обзор**
- Статус mihomo, прокси-правил, соцсетей, видео и zapret — цветными индикаторами.
- Карточки: аптайм роутера и mihomo, CPU, RAM, узлы, трафик с живым графиком, дата обновления подписки.
- Четыре переключателя: прокси, соцсети, видео Google, zapret — с горячей перезагрузкой **без разрыва соединений**.
- Кнопки: обновить подписку, бэкап, перезапуск, панели mihomo/zapret, админка роутера.

**Сеть**
- Активные соединения по устройствам (имена берутся из DHCP Keenetic) и по доменам.
- Политика каждого домена: `PROXY` / `DIRECT` / `REJECT`.
- Пометка «висящих» доменов — вероятная DPI-блокировка.
- Клик по домену → правило «через VPN / напрямую / блокировать».
- Массовая кнопка «все ⚠ → VPN».
- Реальная проверка доступности домена напрямую с роутера.

**Скорость**
- Замер скорости топ-5 узлов (скачивание 2 МБ через каждый) с закреплением лучшего.
- Автоматический замер каждые 2 часа и после обновления подписки.
- Полная проверка всех узлов: живые/мёртвые, список неотвечающих.
- История задержки и страна фактического выхода.

**Правила и логи**
- Полный редактор списка правил mihomo в браузере.
- Шесть вкладок логов: mihomo, обновление, watchdog, задачи, скорость, zapret.

**Устойчивость**
- Watchdog каждую минуту: перезапуск при зависании, fail-safe снятие правил.
- Возврат на авто-выбор, если закреплённый узел умер.
- Ежедневный бэкап конфигов на внутреннюю флешку, ротация логов.
- Учёт трафика по дням снапшотами каждые 15 минут — переживает перезапуски.

---

## Требования

- Keenetic с Entware на USB (тестировалось на Hopper KN-3811, KeeneticOS 5.x)
- `mihomo`, `zapret2` (nfqws2), `lighttpd`, `python3`, `curl`
- Свободное место под логи и бэкапы

---

## Установка

```sh
# 1. скрипты
cp router/scripts/*.sh router/scripts/update.py router/scripts/rules-proxy.yaml /opt/etc/mihomo/
chmod +x /opt/etc/mihomo/*.sh

# 2. веб-панель
mkdir -p /opt/etc/mihomo/www/cgi-bin
cp router/www/index.html /opt/etc/mihomo/www/
cp router/www/cgi-bin/api.cgi /opt/etc/mihomo/www/cgi-bin/
chmod +x /opt/etc/mihomo/www/cgi-bin/api.cgi

# 3. конфиг (обязательно!)
cp router/scripts/ui.conf.example /opt/etc/mihomo/ui.conf
chmod 600 /opt/etc/mihomo/ui.conf
vi /opt/etc/mihomo/ui.conf     # адреса, секрет API, Telegram

# 4. автозапуск
cp router/init.d/S9* /opt/etc/init.d/
chmod +x /opt/etc/init.d/S9*

# 5. запуск
/opt/etc/init.d/S99mihomo restart
/opt/etc/init.d/S98mihomo-ui restart
```

Открыть: `http://<адрес-роутера>:8090/`

---

## Настройка

Все параметры — в `/opt/etc/mihomo/ui.conf` (см. `ui.conf.example`):

| Параметр | Назначение | По умолчанию |
|---|---|---|
| `MIHOMO_API` | адрес API mihomo | `http://127.0.0.1:9090` |
| `MIHOMO_SECRET` | секрет API (должен совпадать с `secret` в конфиге mihomo) | — |
| `ROUTER_URL` | ссылка «Админка роутера» | `http://192.168.1.1/` |
| `ZAPRET_URL` | ссылка «Панель zapret» | `http://192.168.1.1:90/` |
| `MIHOMO_UI_URL` | ссылка «Панель mihomo» | `http://mihomo.lan:9090/ui/metacubexd/` |
| `TG_TOKEN` | токен Telegram-бота | не задан |
| `TG_CHAT` | chat_id получателя | не задан |

Файл содержит секреты — он в `.gitignore` и **не должен попадать в репозиторий**.

---

## API

`GET/POST /cgi-bin/api.cgi?action=...`

| action | назначение |
|---|---|
| `status` | состояние: mihomo, прокси, видео, соцсети, zapret, узлы, RAM, CPU, трафик |
| `config` | ссылки интерфейса и флаг Telegram |
| `rules_get` / `rules_set` | чтение и запись правил |
| `toggle_vpn` / `toggle_social` / `toggle_video` / `toggle_zapret` | переключатели (`&on=1\|0`) |
| `conns` | активные соединения: устройства, домены, политика, зависания |
| `add_rule` / `bulk_proxy` | добавить правило домену / массово перевести в прокси |
| `probe` | проверка доступности домена напрямую |
| `speedtest` / `speed_last` | замер узлов и последний результат |
| `nodecheck` / `health` | полная проверка узлов и её результат |
| `history` / `traffic_daily` | история задержки и трафик по дням |
| `myip` | фактический IP выхода через туннель |
| `backups` / `restore` | список и восстановление бэкапов |
| `update` / `backup` / `restart` | обслуживание |
| `logs&f=...` | логи: `mihomo`, `update`, `watchdog`, `tasks`, `speed`, `zapret` |

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
    tasks.sh              расписание
    traffic_snapshot.sh   учёт трафика каждые 15 минут
    update.sh / update.py обновление подписки и конвертация
    rules.sh              iptables-правила mihomo
    supervise.sh          супервизор запуска
    backup.sh             бэкап на внутреннюю флешку
    delayhist.sh          история задержки
    notify.sh             уведомления в Telegram
    lighttpd.conf         веб-сервер панели (:8090)
    rules-proxy.yaml      список правил
  init.d/                 автозапуск S96–S99
docs/ARCHITECTURE.md      как устроено
docs/API.md               описание API
```

---

## Безопасность

- Панель слушает LAN на `:8090` **без авторизации** — не выставляйте её в интернет.
- Секреты храните только в `ui.conf` (`chmod 600`).
- Для доступа снаружи используйте VPN или reverse proxy с авторизацией.

---

## Обновление

```sh
cd NetRules && git pull
cp router/www/index.html /opt/etc/mihomo/www/
cp router/www/cgi-bin/api.cgi /opt/etc/mihomo/www/cgi-bin/
/opt/etc/init.d/S98mihomo-ui restart
```

---

## Поддержать автора

Проект бесплатный. Если пригодился — поставьте ⭐ на GitHub, это лучшая благодарность.
Реквизиты для донат-сервисов добавляются в `.github/FUNDING.yml`.

---

## Лицензия

[MIT](LICENSE) © 2026 **Eugene Ermakov (Ermstudio)**.
Используйте, изменяйте и распространяйте свободно, сохраняя упоминание автора — см. [NOTICE](NOTICE).
