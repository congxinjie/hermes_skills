---
name: linux-wifi-hotspot
description: "Use when making a Linux box a WiFi hotspot/softAP."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [wifi, hotspot, softap, hostapd, dnsmasq, nmcli, networking]
    related_skills: [linux-vendor-package-install]
---

# Linux WiFi Hotspot / SoftAP

Turn a Linux desktop/laptop into a WiFi access point (hotspot / software router)
while keeping its own internet uplink — especially when the uplink comes from
the SAME wifi card (no ethernet cable).

VERIFIED end-to-end on Ubuntu 20.04 + Intel 9560 (2026-08): hostapd
`AP-ENABLED`, DHCP leases issued, NAT working. The two 5GHz blockers and the
2.4GHz bypass are documented below — read them BEFORE attempting 5GHz.

## When to use
- User asks to make the machine a hotspot, AP, or router
- Sharing the machine's internet with phone/tablet/other laptops
- Uplink is the same single wifi card

## Confirmed pitfalls (Ubuntu 20.04 + NetworkManager + iwlwifi Intel 9560)
1. **NM hotspot kills the STA uplink.** `nmcli dev wifi hotspot ifname wlo1 ...`
   (and GNOME's hotspot toggle) switches the single wifi interface wholesale
   into AP mode: `nmcli device status` shows the card "已连接 Hotspot" instead
   of the campus SSID, the machine loses internet, and the hotspot has nothing
   to NAT. On a single-radio card NM's hotspot and the STA uplink cannot run
   concurrently on the same interface. Restore: bring the hotspot connection
   down; NM reconnects the original SSID automatically.
2. **NM cannot use an iw-created virtual AP interface.** Creating
   `sudo iw dev wlo1 interface add ap0 type __ap` enables STA+AP concurrency
   (check `iw list` → "valid interface combinations", e.g.
   `#{ managed } <= 1, #{ AP } <= 1` — exactly the supported combo on Intel
   9560), BUT NetworkManager marks ap0 unavailable: its wpa_supplicant fails
   with `sup-iface[...]: error adding interface: wpa_supplicant couldn't grab
   this interface.` (retries ~5x, then "supplicant interface keeps failing,
   giving up"); `nmcli device show ap0` → `GENERAL.STATE: 20 (unavailable)`;
   `nmcli connection up` then fails with the misleading
   `No suitable device found for this connection (device eno2 not available
   because profile is not compatible with device (mismatching interface name))`
   — the real cause is ap0 being unavailable, not eno2.

## Working approach: hostapd + dnsmasq + iptables (bypass NM for the AP)
Verified recipe; order matters.

1. **Check capability:** `iw list | grep -A6 "valid interface combinations"` —
   must allow 1 managed + 1 AP simultaneously.
2. **Create virtual AP iface:** `sudo iw dev wlo1 interface add ap0 type __ap`
   (virtual iface gets a distinct MAC suffix).
3. **Keep NM off ap0:** `nmcli device set ap0 managed no` AND delete any NM
   wifi profiles bound to ap0 (`nmcli connection delete <name>`) — otherwise
   NM keeps retrying to grab it. Persist across reboots with a keyfile
   drop-in `/etc/NetworkManager/conf.d/99-unmanaged-ap0.conf`:
   ```
   [keyfile]
   unmanaged-devices=interface-name:ap0
   ```
4. **IP:** `sudo ip addr add 10.42.0.1/24 dev ap0`. Do NOT manually
   `ip link set ap0 up` — freshly created vifs can return `RTNETLINK answers:
   Device or resource busy` (iw may report `type managed` pre-run); hostapd
   sets the iftype and brings the interface up itself.
5. **Forward + NAT:** `sudo sysctl -w net.ipv4.ip_forward=1`;
   `sudo iptables -t nat -A POSTROUTING -o wlo1 -j MASQUERADE`
   (`-o` = the uplink STA interface). In scripts, guard with `iptables -t nat
   -C POSTROUTING -o wlo1 -j MASQUERADE` before `-A` (idempotency).
6. **hostapd:** config from templates/hostapd.conf; run
   `sudo hostapd -B <conf>`. AP channel MUST equal the STA's channel (same
   radio) — sync it automatically instead of hardcoding:
   ```
   CH=$(iw dev wlo1 info | awk '/channel/{print $2}')
   sed -i "s/^channel=.*/channel=$CH/" <conf>
   ```
   Set hw_mode to the STA's band. On iwlwifi under the CN reg domain, 5GHz AP
   is BLOCKED (see next section) — the verified recipe is hw_mode=g on 2.4GHz
   after forcing the STA to band bg (step 3 of next section).
7. **DHCP/DNS:** dnsmasq — Ubuntu 20.04 ships dnsmasq-base (binary
   /usr/sbin/dnsmasq, no init script; run directly). Config from
   templates/dnsmasq.conf; `bind-interfaces` avoids clashing with
   systemd-resolved on 127.0.0.53.
8. **Verify:** `iw dev ap0 info | grep -E "ssid|type|channel"` → `type AP`,
   channel == STA channel; `pgrep -x hostapd; pgrep -x dnsmasq`;
   `ss -ulnp | grep :67` (DHCP); from a client: connects, gets 10.42.0.x,
   DNS resolves, internet works.

## 5GHz blockers (verified on iwlwifi 9560, reg domain CN)
1. **Regulatory `no IR`:** `iw list` Band 2 may show ALL 5GHz channels
   `(no IR)` — receive-only, no beacon TX. hostapd fails:
   `Configured channel (56) not found from the channel list of current mode`
   / `Hardware does not support configured channel`. Diagnose with
   `iw reg get` + the frequency flags BEFORE debugging anything else.
2. **DFS channels are unusable for AP on iwlwifi:** adding `ieee80211d=1` +
   `ieee80211h=1` (hostapd refuses 11h without 11d: `Cannot enable IEEE
   802.11h without IEEE 802.11d enabled`) gets past validation to
   `DFS-CAC-START freq=5280 chan=56 ... cac_time=60s` then
   `start_dfs_cac() failed, -1` → `Interface initialization failed` — the
   driver has no hostapd-driven (userspace) radar detection. Campus APs often
   sit on DFS channels (5GHz 52-64, 100-140), so this bites exactly when you
   need it.
3. **Working bypass — force the STA to 2.4GHz:**
   ```
   nmcli connection modify <conn> 802-11-wireless.band bg
   nmcli connection up <conn>
   ```
   (revert later with `band ""`). AP then runs on 2.4G ch 1/6/11
   (hw_mode=g): instant `AP-ENABLED`, no CAC, unrestricted in CN. The STA's
   landing channel varies (NM picks the strongest 2.4G BSS) — always use the
   channel sync from step 6 above.

## Persistence (systemd)
The virtual vif does not survive reboot. Package the stack as a service:
- `templates/wifi-hotspot.service` — Type=simple, ExecStartPre =
  `scripts/prepare.sh` (idempotent: channel re-sync, vif create, IP, sysctl,
  NAT with `-C` guard), ExecStart = hostapd (foreground), ExecStartPost =
  dnsmasq, ExecStopPost = `scripts/cleanup.sh`.
- Install:
  ```
  sudo cp <skill>/templates/wifi-hotspot.service /etc/systemd/system/
  sudo cp <skill>/99-unmanaged-ap0.conf /etc/NetworkManager/conf.d/
  sudo systemctl daemon-reload
  sudo systemctl enable --now wifi-hotspot
  ```
- Manual control: `sudo systemctl stop|start wifi-hotspot`;
  `systemctl status wifi-hotspot`.

## Teardown
```
sudo pkill -x hostapd
sudo pkill -x dnsmasq
sudo iptables -t nat -D POSTROUTING -o wlo1 -j MASQUERADE
sudo ip link set ap0 down
```
(pkill -x exact-name match — a `-f` pattern can kill your own shell; see
linux-vendor-package-install pitfalls.)

## Constraints / notes
- Single radio: AP shares the STA's channel AND band; total throughput
  roughly halves (one radio, two jobs).
- Campus networks often have multi-device sharing detection (kicks/limits the
  account) — warn the user about the policy before running a shared AP.
- If an ethernet cable is available, prefer it as uplink: the radio then
  serves only the AP side and throughput jumps (also unblocks 5GHz AP if the
  reg domain allows TX).

## Files
- templates/hostapd.conf — known-good 2.4GHz AP config (placeholders for SSID/pass)
- templates/dnsmasq.conf — DHCP/DNS for the AP subnet
- templates/wifi-hotspot.service — systemd unit: prepare → hostapd → dnsmasq → cleanup
- scripts/prepare.sh — idempotent pre-start (channel sync, vif create, IP, sysctl, NAT)
- scripts/cleanup.sh — teardown (kill daemons, drop NAT, delete vif)
- references/intel9560-softap-session.md — session specifics: exact NM log
  lines, NJUST 5GHz ch56, 5GHz blocker transcripts, verified 2.4GHz resolution
