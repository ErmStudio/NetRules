#!/bin/sh
# Блокируем QUIC (UDP 443) к Google: браузеры переходят на TCP и идут через прокси.
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
for net in 142.250.0.0/15 172.217.0.0/16 216.58.192.0/19 64.233.160.0/19 74.125.0.0/16 \
           108.177.0.0/17 209.85.128.0/17 142.251.0.0/16 172.253.0.0/16 142.252.0.0/14 173.194.0.0/16; do
  iptables -C FORWARD -p udp --dport 443 -d "$net" -j REJECT --reject-with icmp-port-unreachable 2>/dev/null || \
    iptables -I FORWARD 1 -p udp --dport 443 -d "$net" -j REJECT --reject-with icmp-port-unreachable 2>/dev/null
done
