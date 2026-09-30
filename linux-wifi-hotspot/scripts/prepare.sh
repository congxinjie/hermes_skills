#!/bin/bash
# Prepare a WiFi virtual AP interface (idempotent; run as root, e.g. via
# systemd ExecStartPre). Edit the CONFIG block for your machine.
set -e

STA_IF=wlo1          # interface carrying the uplink (must be connected)
AP_IF=ap0            # virtual AP interface name
AP_IP=10.42.0.1/24   # AP subnet (must match templates/dnsmasq.conf)
CONF_DIR=/home/USER/hotspot   # directory holding hostapd.conf

# 1) Sync AP channel to the STA's current channel (same radio = same channel)
CH=$(iw dev $STA_IF info 2>/dev/null | awk '/channel/{print $2}')
if [ -n "$CH" ]; then
  sed -i "s/^channel=.*/channel=$CH/" $CONF_DIR/hostapd.conf
  echo "channel synced: $CH"
fi

# 2) Create the virtual AP interface if missing
if ! ip link show $AP_IF >/dev/null 2>&1; then
  iw dev $STA_IF interface add $AP_IF type __ap
  echo "$AP_IF created"
fi

# 3) Assign IP if missing (interface bring-up is hostapd's job — do NOT
#    `ip link set ap0 up` manually, it can EBUSY on a fresh vif)
if ! ip addr show $AP_IF | grep -q "$AP_IP"; then
  ip addr add $AP_IP dev $AP_IF
fi

# 4) Enable forwarding
sysctl -w net.ipv4.ip_forward=1 >/dev/null

# 5) NAT (idempotent — -C guard prevents duplicate rules on restart)
if ! iptables -t nat -C POSTROUTING -o $STA_IF -j MASQUERADE 2>/dev/null; then
  iptables -t nat -A POSTROUTING -o $STA_IF -j MASQUERADE
  echo "NAT rule added"
fi
