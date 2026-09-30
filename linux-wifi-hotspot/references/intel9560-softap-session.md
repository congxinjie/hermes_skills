# Intel 9560 softAP session (2026-08, Ubuntu 20.04.6, NJUST campus)

Machine: USER-PC (kernel 5.15.0-139-generic), wifi Intel Wireless-AC
9560 (iwlwifi), ethernet Intel I219-V (eno2, unused). Hostname
USER-PC-MKM21CZG4.

## Hardware facts
- `iw list` valid interface combinations:
  `#{ managed } <= 1, #{ AP, P2P-client, P2P-GO } <= 1, #{ P2P-device } <= 1,
  total <= 3, #channels <= 2` — one STA + one AP concurrent is legal.
- NJUST uplink: 5 GHz channel 56 (5280 MHz), 20 MHz width → AP must use
  hw_mode=a channel=56.
- Virtual vif gets a distinct MAC suffix (wlo1 ...:b4 → ap0 ...:b6).

## Confirmed failure #1: NM hotspot drops the uplink
`nmcli dev wifi hotspot ifname wlo1 ssid X password Y` on the same interface:
- device list flips wlo1 to "已连接 Hotspot"; NJUST STA connection gone;
  machine loses internet (hotspot has no upstream).
- Restore: `nmcli connection down Hotspot` (or GUI toggle off) → NM
  reconnects NJUST automatically.

## Confirmed failure #2: NM cannot use the iw-created AP vif
- `sudo iw dev wlo1 interface add ap0 type __ap` → ap0 exists and appears in
  `nmcli device status` as wifi, but `nmcli device show ap0` →
  `GENERAL.STATE: 20 (不可用)`.
- journalctl -u NetworkManager shows, ~5 times:
  `sup-iface[0x...,ap0]: error adding interface: wpa_supplicant couldn't grab
  this interface.`
  then `device (ap0): supplicant interface keeps failing, giving up`.
- `nmcli connection up <ap-profile>` fails:
  `No suitable device found for this connection (device eno2 not available
  because profile is not compatible with device (mismatching interface name))`
  — message mentions eno2 only; real cause is ap0 unavailable.
- `iw dev ap0 info` may report `type managed` until an AP daemon (hostapd)
  sets the iftype via NL80211_SET_INTERFACE on start — don't trust it pre-run.
- Workaround used: `nmcli device set ap0 managed no` + delete NM wifi
  profiles bound to ap0; run hostapd directly.

## Resolution (verified later the same session)
1. **hostapd 5GHz attempts failed for two stacked reasons:**
   - `iw list` Band 2 showed ALL 5GHz channels `(no IR)` under the current reg
     state (`iw reg get` printed odd `country CN: DFS-FCC` / `DFS-UNSET`
     blocks); hostapd: `Configured channel (56) not found from the channel
     list of current mode (2) IEEE 802.11a` / `Hardware does not support
     configured channel`.
   - After adding `ieee80211d=1` + `ieee80211h=1`, hostapd started CAC then
     died: `DFS-CAC-START freq=5280 chan=56 sec_chan=0, width=0 ... cac_time=60s`
     → `DFS start_dfs_cac() failed, -1` → `Interface initialization failed`.
     iwlwifi has no hostapd-driven (userspace) radar detection.
2. **Working solution — move everything to 2.4GHz:**
   - `nmcli connection modify NJUST 802-11-wireless.band bg` + `nmcli
     connection up NJUST` → STA landed on 2.4G ch 1 (was 5G ch56). NJUST 2.4G
     BSSs exist on ch 1/6/11; the landing channel varies by signal strength.
   - hostapd.conf → hw_mode=g, channel auto-synced:
     `CH=$(iw dev wlo1 info | awk '/channel/{print $2}'); sed -i
     "s/^channel=.*/channel=$CH/" hostapd.conf`
   - `sudo hostapd -B ...` → instant `AP-ENABLED` (no CAC on 2.4G). dnsmasq
     up (`ss -ulnp` → ap0:67), `ip_forward=1`, `iptables -t nat -A
     POSTROUTING -o wlo1 -j MASQUERADE` confirmed (rule present via
     `iptables -t nat -S POSTROUTING`).
3. **Persistence:** systemd unit + prepare.sh/cleanup.sh + NM keyfile drop-in
   (see templates/ and scripts/ of this skill; runtime copies live at
   /home/USER/hotspot/). SSID wifi-hotspot.
4. **Note:** `ip link set ap0 up` after `iw interface add` can return
   `RTNETLINK answers: Device or resource busy`; hostapd brings the interface
   up itself — never force it manually.

## Bandwidth context (measured, 2026-08)
- TUNA mirror: IPv4 7.27 MB/s (~58 Mbps), IPv6 8.47 MB/s (~68 Mbps) — campus
  ceiling. IPv6 slightly faster.
- Tencent CDN (qqdl.gtimg.cn): ~3.17 MB/s (~25 Mbps) — CDN per-connection
  cap, NOT the campus limit (don't misread single-CDN numbers as the network
  ceiling).
- Cloudflare speed.cloudflare.com direct: blocked (GFW) — expected.
- mirrors.ustc.edu.cn: 403 on HEAD/range probes (~18 KB error body); TUNA
  serves fine; directory listings reveal real filenames.
