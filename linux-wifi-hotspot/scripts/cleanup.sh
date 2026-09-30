#!/bin/bash
# Tear down the hotspot (systemd ExecStopPost / manual). Run as root.
# pkill -x exact-name match only — a -f pattern can kill the invoking shell.
STA_IF=wlo1
AP_IF=ap0

pkill -x hostapd 2>/dev/null || true
pkill -x dnsmasq 2>/dev/null || true
iptables -t nat -D POSTROUTING -o $STA_IF -j MASQUERADE 2>/dev/null || true
ip link set $AP_IF down 2>/dev/null || true
iw dev $AP_IF del 2>/dev/null || true
