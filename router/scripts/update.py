#!/opt/bin/python3
import json, sys, os, re
BASE = "/opt/etc/mihomo"

def q(v):
    s = str(v).replace('\\', '\\\\').replace('"', '\\"')
    return '"' + s + '"'

def load_proxies(path):
    data = json.load(open(path, encoding="utf-8"))
    ob = data[0].get("outbounds", []) if isinstance(data, list) else data.get("outbounds", [])
    out = []
    for o in ob:
        p = o.get("protocol")
        ss = o.get("streamSettings") or {}
        net = ss.get("network") or "tcp"
        if p not in ("vless", "trojan"):
            continue
        if net not in ("tcp", "grpc", "ws"):
            continue
        tag = o.get("tag") or "node"
        rs = ss.get("realitySettings") or {}
        ts = ss.get("tlsSettings") or {}
        sni = rs.get("serverName") or ts.get("serverName")
        fp = rs.get("fingerprint") or ts.get("fingerprint") or "chrome"
        d = {"name": tag}
        if p == "vless":
            v = o["settings"]["vnext"][0]
            u = v["users"][0]
            d.update(type="vless", server=v["address"], port=int(v["port"]),
                     uuid=u["id"], udp=True)
            if u.get("flow"):
                d["flow"] = u["flow"]
        else:
            s = o["settings"]["servers"][0]
            d.update(type="trojan", server=s["address"], port=int(s["port"]),
                     password=s["password"], udp=True)
        d["tls"] = True
        if sni:
            d["servername"] = sni
        if fp:
            d["client-fingerprint"] = fp
        if ss.get("security") == "reality":
            ro = {"public-key": rs.get("publicKey") or ""}
            if rs.get("shortId"):
                ro["short-id"] = rs["shortId"]
            d["reality-opts"] = ro
        if net == "grpc":
            d["network"] = "grpc"
            gs = ss.get("grpcSettings") or {}
            d["grpc-opts"] = {"grpc-service-name": gs.get("serviceName") or ""}
        elif net == "ws":
            d["network"] = "ws"
            ws = ss.get("wsSettings") or {}
            wo = {"path": ws.get("path") or "/"}
            h = (ws.get("headers") or {}).get("Host")
            if h:
                wo["headers"] = {"Host": h}
            d["ws-opts"] = wo
        out.append(d)
    return out

def emit(px):
    L = []
    for d in px:
        L.append("  - name: " + q(d["name"]))
        L.append("    type: " + d["type"])
        L.append("    server: " + q(d["server"]))
        L.append("    port: %d" % d["port"])
        if d["type"] == "vless":
            L.append("    uuid: " + q(d["uuid"]))
            if d.get("flow"):
                L.append("    flow: " + d["flow"])
        else:
            L.append("    password: " + q(d["password"]))
        L.append("    udp: true")
        L.append("    tls: true")
        if d.get("servername"):
            L.append("    servername: " + q(d["servername"]))
        if d.get("client-fingerprint"):
            L.append("    client-fingerprint: " + d["client-fingerprint"])
        ro = d.get("reality-opts")
        if ro:
            L.append("    reality-opts:")
            L.append("      public-key: " + q(ro.get("public-key", "")))
            if ro.get("short-id"):
                L.append("      short-id: " + q(ro["short-id"]))
        if d.get("network") == "grpc":
            L.append("    network: grpc")
            L.append("    grpc-opts:")
            L.append("      grpc-service-name: " + q(d["grpc-opts"].get("grpc-service-name", "")))
        elif d.get("network") == "ws":
            L.append("    network: ws")
            L.append("    ws-opts:")
            L.append("      path: " + q(d["ws-opts"].get("path", "/")))
            h = d["ws-opts"].get("headers")
            if h:
                L.append("      headers:")
                L.append("        Host: " + q(h["Host"]))
    return "\n".join(L)

ISO = {
    "PL": "Польша", "DE": "Германия", "FI": "Финляндия", "IT": "Италия",
    "NL": "Нидерланды", "MD": "Молдова", "SE": "Швеция", "EE": "Эстония",
    "RU": "Россия", "EU": "Европа", "US": "США", "GB": "Британия",
    "FR": "Франция", "LV": "Латвия", "LT": "Литва", "TR": "Турция",
    "KZ": "Казахстан", "CH": "Швейцария", "AT": "Австрия", "ES": "Испания",
    "CZ": "Чехия", "RO": "Румыния", "BG": "Болгария", "HU": "Венгрия",
    "SG": "Сингапур", "JP": "Япония", "HK": "Гонконг", "CA": "Канада",
}


def country_of(remark):
    if not remark:
        return "?"
    m = re.search("([\U0001F1E6-\U0001F1FF]{2})", remark)
    if m:
        code = "".join(chr(ord(ch) - 0x1F1E6 + ord("A")) for ch in m.group(1))
        name = ISO.get(code, code)
    else:
        name = "?"
    if "LTE" in remark:
        name = name + " LTE"
    return name


def write_countries():
    data = json.load(open(os.path.join(BASE, "sub.json"), encoding="utf-8"))
    m = {}
    for e in data[1:]:
        c = country_of(e.get("remarks") or "")
        for o in e.get("outbounds", []):
            t = o.get("tag")
            if t and o.get("protocol") in ("vless", "trojan") and t not in m:
                m[t] = c
    with open(os.path.join(BASE, "countries.txt"), "w", encoding="utf-8") as f:
        for k in sorted(m):
            f.write("%s|%s\n" % (k, m[k]))
    print("countries=%d" % len(m), file=sys.stderr)

def main():
    px = load_proxies(os.path.join(BASE, "sub.json"))
    if len(px) < 5:
        print("too few nodes: %d" % len(px))
        return 1
    names = [d["name"] for d in px]
    all_flow = "[" + ", ".join(q(n) for n in names) + "]"
    all_lines = "\n".join("      - " + q(n) for n in names)
    tpl = open(os.path.join(BASE, "template.yaml"), encoding="utf-8").read()
    cfg = tpl.replace("#PROXIES#", emit(px)).replace("#ALL#", all_flow).replace("#ALL_PROXY#", all_lines)
    cfg_path = os.path.join(BASE, "config.yaml")
    if os.path.exists(cfg_path):
        os.rename(cfg_path, cfg_path + ".bak")
    open(cfg_path, "w", encoding="utf-8").write(cfg)
    print("ok, nodes=%d" % len(px))
    write_countries()
    return 0

sys.exit(main())