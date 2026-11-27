import json, sys
src="/opt/etc/itx/sub.json"
out="/opt/etc/itx/config.json"
BASE=21000
data=json.load(open(src))
inbounds=[]; outbounds=[]; routing=[]; meta=[]
i=0
for e in data:
    for o in e.get("outbounds",[]):
        if o.get("protocol") not in ("vless","vmess","trojan"):
            continue
        tag="n%d"%(i)
        o=dict(o); o["tag"]=tag
        port=BASE+i
        inbounds.append({"tag":"in%d"%i,"listen":"127.0.0.1","port":port,
                         "protocol":"socks","settings":{"auth":"noauth","udp":False}})
        outbounds.append(o)
        routing.append({"type":"field","inboundTag":["in%d"%i],"outboundTag":tag})
        v=o.get("settings",{}).get("vnext",[{}])[0]
        meta.append({"i":i,"port":port,"name":(e.get("remarks") or "")[:60],
                     "addr":v.get("address",""),"proto":o.get("protocol")})
        i+=1
cfg={"log":{"loglevel":"warning"},"inbounds":inbounds,"outbounds":outbounds,
     "routing":{"domainStrategy":"AsIs","rules":routing}}
json.dump(cfg,open(out,"w"),ensure_ascii=False,indent=1)
json.dump(meta,open("/opt/etc/itx/meta.json","w"),ensure_ascii=False,indent=1)
print("узлов:", i, "порты:", BASE, "-", BASE+i-1)
