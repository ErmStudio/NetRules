# Восстановление после поломки диска

Система состоит из двух слоёв, и восстанавливаются они по-разному.

| Слой | Где живёт | Как восстановить |
|---|---|---|
| Код проекта (панель, скрипты, установщик) | GitHub `ErmStudio/NetRules` | скачать заново |
| Настройки и данные (секрет API, ссылка подписки, чёрный список ITX) | USB-диск `/opt` + внутренняя флешка | из бэкапа |

## 1. Что делать сразу после замены/переустановки USB

1. Установить Entware на новый накопитель.
2. Восстановить доступ по SSH (ключ `authorized_keys` есть в бэкапе).
3. Скачать проект:

```sh
cd /tmp
wget -O netrules.tar.gz https://github.com/ErmStudio/NetRules/archive/refs/heads/main.tar.gz
tar xzf netrules.tar.gz
cd NetRules-main/router
```

4. Установить базовую версию:

```sh
sh install.sh
```

5. Вернуть настройки из бэкапа (`/storage/mihomo-backup/<дата>/`):

```sh
BK=/storage/mihomo-backup/20261128
cp -f $BK/ui.conf $BK/sub.url $BK/config.yaml $BK/template.yaml \
      $BK/rules-proxy.yaml $BK/rules-itx.yaml $BK/rules-ads.yaml \
      $BK/countries.txt $BK/device-names.txt /opt/etc/mihomo/
chmod 600 /opt/etc/mihomo/ui.conf
```

> Внутренняя флешка `/storage` переживает смерть USB — там лежит копия `restore-kit`.

## 2. Если была вторая подписка (ITX)

```sh
sh install.sh --itx          # ставит xray-core и init-скрипт
opkg install xray-core
mkdir -p /opt/etc/itx
cp -f $BK/itx/sub.url $BK/itx/blocklist.txt $BK/itx/*.py /opt/etc/itx/
cp -f https://raw.githubusercontent.com/ErmStudio/NetRules/main/router/itx/update.sh /opt/etc/itx/
sh /opt/etc/itx/update.sh    # скачает подписку, проверит страны, соберёт конфиг
```

`sub.json` в бэкап не кладётся намеренно — он большой и всегда скачивается заново по `sub.url`.

## 3. Проверка после восстановления

```sh
/opt/etc/mihomo/rules.sh apply
/opt/bin/wget -qO- 'http://127.0.0.1:8090/cgi-bin/api.cgi?action=status'
/opt/bin/wget -qO- 'http://127.0.0.1:8090/cgi-bin/api.cgi?action=config'
```

Ожидаемо: `mihomo:1`, `vpn:1`, `zapret:1`, при второй подписке `itx:1`, `itx_available:1`.

## 4. Что бэкапится автоматически

Ежедневно в 05:10 в `/storage/mihomo-backup/<дата>/`:

- конфиги: `config.yaml`, `template.yaml`, `rules-proxy.yaml`, `rules-itx.yaml`, `rules-ads.yaml`, `sub.url`, `ui.conf`, `VERSION`, `countries.txt`, `device-names.txt`;
- списки zapret (`nfqws2-lists/`);
- скрипты (`scripts/`), панель (`scripts/www/`), автозапуск (`S95itx`…`S99mihomo`);
- расширение ITX (`itx/`: `sub.url`, `blocklist.txt`, скрипты, готовый `config.json`);
- `authorized_keys` для SSH.

Плюс обновляется `restore-kit` на внутренней флешке.
