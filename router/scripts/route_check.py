#!/opt/bin/python3
# Куда реально уйдёт запрос: мини-матчер правил mihomo без единого сетевого запроса.
# Читает rules: из config.yaml и локальные файлы rule-providers, применяет их по порядку.
# Запуск: route_check.py [host=example.com]
# Вывод: JSON {"ok":true,"hosts":[{"host","policy","rule","expect","ok"}]}
import json, os, re, sys

BASE = "/opt/etc/mihomo"


def unquote(s):
    """urllib на роутере нет — свой минимальный декодер."""
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "%" and i + 2 < len(s):
            try:
                out.append(chr(int(s[i + 1:i + 3], 16)))
                i += 3
                continue
            except ValueError:
                pass
        if c == "+":
            out.append(" ")
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


PROVIDERS = {
    "ads": "rules-ads.yaml",
    "itx-rules": "rules-itx.yaml",
    "proxy-sites": "rules-proxy.yaml",
}

# Что проверяем по умолчанию и что считается правильным.
# gemini — должен идти через прокси (GEMINI/PROXY); direct — обязан идти напрямую.
CHECKS = [
    ("gemini.google.com", "gemini"),
    ("geminiweb-pa.clients6.google.com", "gemini"),
    ("robinfrontend-pa.googleapis.com", "gemini"),
    ("pubsub.googleapis.com", "gemini"),
    ("content-push.googleapis.com", "gemini"),
    ("aistudio.google.com", "gemini"),
    ("notebooklm.google.com", "gemini"),
    ("generativelanguage.googleapis.com", "gemini"),
    ("accounts.google.com", "gemini"),
    ("ogs.google.com", "gemini"),
    ("apis.google.com", "gemini"),
    ("consent.google.com", "gemini"),
    ("scone-pa.clients6.google.com", "gemini"),
    ("lh3.googleusercontent.com", "gemini"),
    ("dns.google", "direct"),
    ("cloudflare-dns.com", "direct"),
    ("mtalk.google.com", "direct"),
    ("fcm.googleapis.com", "direct"),
    ("www.gstatic.com", "direct"),
]


def rules_from_config():
    out, in_rules = [], False
    try:
        for line in open(os.path.join(BASE, "config.yaml"), encoding="utf-8"):
            if re.match(r"^rules:\s*$", line):
                in_rules = True
                continue
            if in_rules:
                m = re.match(r"^\s+-\s+(\S+)\s*$", line)
                if m:
                    out.append(m.group(1))
                elif line.strip() and not line.startswith(" "):
                    break
    except Exception:
        pass
    return out


_cache = {}


def provider_payload(name):
    if name in _cache:
        return _cache[name]
    path = PROVIDERS.get(name)
    items = []
    if path:
        try:
            started = False
            for line in open(os.path.join(BASE, path), encoding="utf-8"):
                if line.strip() == "payload:":
                    started = True
                    continue
                if started:
                    s = line.strip()
                    if s.startswith("- "):
                        items.append(s[2:].strip())
                    elif s and not s.startswith("#"):
                        break
        except Exception:
            pass
    _cache[name] = items
    return items


def match_one(rule, host):
    parts = rule.split(",")
    kind = parts[0].strip().upper()
    val = parts[1].strip() if len(parts) > 1 else ""
    if kind == "DOMAIN":
        return host == val
    if kind == "DOMAIN-SUFFIX":
        return host == val or host.endswith("." + val)
    if kind == "DOMAIN-KEYWORD":
        return val in host
    return False


def resolve(host):
    host = host.lower().strip(".")
    for rule in rules_from_config():
        parts = rule.split(",")
        kind = parts[0].strip().upper()
        if kind == "MATCH":
            return "DIRECT", "MATCH", ""
        if kind == "RULE-SET":
            name = parts[1].strip()
            target = parts[2].strip() if len(parts) > 2 else ""
            for item in provider_payload(name):
                if match_one(item, host):
                    return target, "RULE-SET " + name, target
            continue
        if kind in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"):
            if match_one(rule, host):
                target = parts[2].strip() if len(parts) > 2 else "DIRECT"
                return target, rule, target
    return "DIRECT", "no rule", ""


def main():
    extra = []
    for a in sys.argv[1:]:
        for kv in a.split("&"):
            if kv.startswith("host="):
                h = unquote(kv[5:])
                if h:
                    extra.append((h, "gemini"))
    checks = CHECKS + extra
    out = []
    for host, expect in checks:
        policy, rule, group = resolve(host)
        ok = (policy != "DIRECT") if expect == "gemini" else (policy == "DIRECT")
        out.append({"host": host, "policy": policy, "rule": rule,
                    "group": group, "expect": expect, "ok": bool(ok)})
    print(json.dumps({"ok": True, "hosts": out}, ensure_ascii=False))


if __name__ == "__main__":
    main()
