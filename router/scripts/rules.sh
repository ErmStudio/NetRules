#!/bin/sh
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
MARK=0x40000000
REDIR_PORT=7892
LAN=192.168.1.0/24
LOG=/opt/var/log/mihomo-watchdog.log

apply() {
  iptables -t mangle -N MH_MARK 2>/dev/null
  iptables -t mangle -F MH_MARK
  iptables -t mangle -A MH_MARK -d 192.168.0.0/16 -j RETURN
  iptables -t mangle -A MH_MARK -d 10.0.0.0/8 -j RETURN
  iptables -t mangle -A MH_MARK -d 172.16.0.0/12 -j RETURN
  iptables -t mangle -A MH_MARK -s $LAN -p tcp -m multiport --dports 80,443 -j MARK --set-mark $MARK
  iptables -t mangle -C PREROUTING -j MH_MARK 2>/dev/null || iptables -t mangle -I PREROUTING 1 -j MH_MARK

  iptables -t nat -N MH_REDIR 2>/dev/null
  iptables -t nat -F MH_REDIR
  iptables -t nat -A MH_REDIR -d 192.168.0.0/16 -j RETURN
  iptables -t nat -A MH_REDIR -d 10.0.0.0/8 -j RETURN
  iptables -t nat -A MH_REDIR -d 172.16.0.0/12 -j RETURN
  iptables -t nat -A MH_REDIR -s $LAN -p tcp -m multiport --dports 80,443 -j REDIRECT --to-ports $REDIR_PORT
  iptables -t nat -C PREROUTING -j MH_REDIR 2>/dev/null || iptables -t nat -I PREROUTING 1 -j MH_REDIR

  # IPv6 в интернет у провайдера нет, но устройства получают ULA и виснут в таймаутах.
  # Отвечаем отказом, чтобы клиент сразу шёл по IPv4.
  if [ -x /opt/sbin/ip6tables ]; then
    /opt/sbin/ip6tables -C FORWARD -s fd00::/8 -j REJECT 2>/dev/null || /opt/sbin/ip6tables -I FORWARD 1 -s fd00::/8 -j REJECT
  fi
}

clear() {
  iptables -t mangle -D PREROUTING -j MH_MARK 2>/dev/null
  iptables -t mangle -F MH_MARK 2>/dev/null
  iptables -t mangle -X MH_MARK 2>/dev/null
  iptables -t nat -D PREROUTING -j MH_REDIR 2>/dev/null
  iptables -t nat -F MH_REDIR 2>/dev/null
  iptables -t nat -X MH_REDIR 2>/dev/null
  if [ -x /opt/sbin/ip6tables ]; then
    /opt/sbin/ip6tables -D FORWARD -s fd00::/8 -j REJECT 2>/dev/null
  fi
}

case "$1" in
  apply) apply ;;
  clear) clear ;;
  *) echo "Usage: $0 {apply|clear}" ;;
esac