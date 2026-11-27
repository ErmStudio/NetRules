#!/opt/bin/python3
# Финальный конфиг Xray: узлы ITX, отфильтрованные по стране выхода и задержке.
import json, os

BASE = "/opt/etc/itx"
SUB = os.path.join(BASE, "sub.json")
META = os.path.join(BASE, "meta.json")
GEO = "/tmp/itx-geo.txt"
OUT_XRAY = os.path.join(BASE, "config.json")
OUT_PROXIES = "/opt/etc/mihomo/itx-proxies.yaml"
OUT_LIST = os.path.join(BASE, "nodes.txt")
PORT0 = 21100
LIMIT = int(os.environ.get("ITX_NODES", "30"))
BLOCKED = {"RU", "BY", "XX", "IR", "KP", "CN", "SY", "CU", "TM", "AF"}

geo = {}
try:
    for line in open(GEO):
        p = line.split()
        if len(p) == 3:
            geo[int(p[0])] = (p[1], float(p[2]))
except FileNotFoundError:
    pass

meta = {x["port"]: x for x in json.load(open(META))}
cands = []
for port, (loc, lat) in geo.items():
    if port not in meta:
        continue
    if loc in BLOCKED or lat >= 3.0:
        continue
    cands.append((lat, port, loc))
cands.sort()
chosen = cands[:LIMIT]
if not chosen:
    raise SystemExit("нет подходящих узлов")

data = json.load(open(SUB))
flat = []
for e in data:
    for o in e.get("outbounds", []):
        if o.get("protocol") in ("vless", "vmess", "trojan"):
            flat.append((e.get("remarks") or "", o))

inbounds, outbounds, routing, proxies, names = [], [], [], [], []
for i, (lat, port, loc) in enumerate(chosen):
    idx = meta[port]["i"]
    remark, ob = flat[idx]
    tag = "itx%d" % i
    ob = dict(ob); ob["tag"] = tag
    inb_port = PORT0 + i + 1
    inbounds.append({"tag": "in%d" % i, "listen": "127.0.0.1", "port": inb_port,
                     "protocol": "socks", "settings": {"auth": "noauth", "udp": False}})
    outbounds.append(ob)
    routing.append({"type": "field", "inboundTag": ["in%d" % i], "outboundTag": tag})
    name = "ITX-%02d %s %.0fms" % (i + 1, loc, lat * 1000)
    proxies.append({"name": name, "type": "socks5", "server": "127.0.0.1",
                    "port": inb_port, "udp": False})
    names.append("%s|%s|%s" % (name, inb_port, (meta[port]["name"] or "")[:40]))

cfg = {"log": {"loglevel": "warning"}, "inbounds": inbounds,
       "outbounds": outbounds, "routing": {"domainStrategy": "AsIs", "rules": routing}}
json.dump(cfg, open(OUT_XRAY, "w"), ensure_ascii=False, indent=1)

with open(OUT_PROXIES, "w") as f:
    f.write("proxies:\n")
    for p in proxies:
        f.write("  - {name: \"%s\", type: socks5, server: 127.0.0.1, port: %d, udp: false}\n"
                % (p["name"], p["port"]))

open(OUT_LIST, "w").write("\n".join(names) + "\n")
print("узлов в модуле:", len(proxies))
for n in names:
    print("  ", n)
