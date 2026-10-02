# Hermes Skills

A small collection of [Hermes Agent](https://hermes-agent.nousresearch.com/) skills, distilled from real‑world use on Ubuntu 20.04 (GNOME 3.36, X11, Intel iGPU).

Each folder is a self‑contained skill: `SKILL.md` plus optional `scripts/` and `templates/`.

## Skills

### 1. `chinese-web-image-sourcing`

**Use when you need real, traceable image material for Chinese deliverables** (defence decks, competition entries, reports) — and generating fake photos is not acceptable.

Covers the whole pipeline for the Chinese web:

- Baidu image/article search (Bing/Google are usually blocked)
- Resolving Baidu `/link?url=…` redirects to real URLs
- Extracting in‑article images (WeChat `mmbiz.qpic.cn` needs a `Referer`)
- The `html.unescape()` trap — `&amp;` in image URLs silently yields 0‑byte downloads
- Batch downloading with `curl` loops, md5 dedup, noise filtering (logos / QR codes)
- Building numbered contact sheets so a human can pick, plus a provenance report

**Iron rule:** never fabricate photos; only real public images, always with source attribution.

### 2. `linux-headless-display`

**Use for headless Linux desktops and monitor‑hotplug fixes.**

- Inventorying display state via DRM sysfs vs `xrandr`
- Simulating an unplug and verifying the desktop survives it
- Diagnosing the **GNOME ≤3.36 hot‑plug bug** (top bar / dock vanish after replug; `desktopGrid is undefined`)
- Restarting `gnome-shell` safely, and a **watchdog** that auto‑recovers on replug
  (`scripts/monitor-replug-watchdog.sh` + `templates/monitor-watchdog.service`)
- Remote‑desktop agent prerequisites (ToDesk / VNC / RDP) on a headless box
- GPU power state and other pitfalls

### 3. `github-stable-access`

**Use when GitHub is blocked, flaky, or rate‑limited** (common on Chinese campus / corporate networks).

- A channel‑by‑channel diagnosis matrix: SSH :22, HTTPS, `raw.githubusercontent.com`, jsDelivr, codeload, and the REST API
- The reliable paths: **SSH for git**, **jsDelivr for single raw files**, **codeload tarballs for whole repos**
- Setting up an ed25519 key and verifying with `ssh -T git@github.com`
- Raising the anonymous API limit (60/h) with a token
- Installing a hub skill from a tarball when the API is rate‑limited
- Pitfalls: proxy env vars poisoning direct‑connect tests, `no_proxy` covering only LAN ranges, and confusing "raw is blocked" with "the API is rate‑limited"

`scripts/check-github-access.sh` runs the whole matrix in one command.

### 4. `linux-wifi-hotspot`

**Use when turning a Linux box into a WiFi hotspot / softAP** while keeping its own uplink.

- The full `hostapd` + `dnsmasq` + `ap0` recipe
- Why NetworkManager can't manage `ap0`, and the `nmcli device set ap0 managed no` workaround (runtime‑only — must be redone each boot)
- Intel 9560 specifics: 2.4 GHz‑only AP, no‑IR/DFS channels, AP channel must match the client interface
- A systemd unit plus `prepare.sh` / `cleanup.sh`
- `references/intel9560-softap-session.md` documents a real debugging session

### 5. `campus-portal-autologin`

**Use when a campus portal keeps demanding re‑login** (Ruijie ePortal / Dr.COM style captive portals).

- Identifying the portal from the redirect URL (`wlanacname` / `wlanacip` ⇒ Ruijie ePortal)
- Finding the real login endpoint inside the portal's JS (`/api/portal/v1/login`)
- A small Python daemon + systemd timer that re‑authenticates every 2 minutes
- **The #1 pitfall: when the network drops, DNS often drops with it** — so the script must fall back to the portal's IP, or it never even sends the request
- Disabling WiFi power‑save (a common cause of *random* drops) and multi‑round re‑checking so a slow auth doesn't look like a failure

Ships as a working example against the NJUST portal.

## Install

Copy a skill folder into your Hermes skills directory:

```bash
cp -r chinese-web-image-sourcing ~/.hermes/skills/research/
cp -r linux-headless-display     ~/.hermes/skills/sysadmin/
cp -r github-stable-access       ~/.hermes/skills/github/
cp -r linux-wifi-hotspot         ~/.hermes/skills/sysadmin/
cp -r campus-portal-autologin    ~/.hermes/skills/sysadmin/
```

Hermes discovers `SKILL.md` files automatically. For the watchdog, install the unit as a systemd user service and enable it.

## Licence

Each skill keeps its own licence (see the `license:` field in its `SKILL.md`):
`chinese-web-image-sourcing` → MIT, `linux-headless-display` → CC‑BY‑4.0, `github-stable-access` → MIT, `linux-wifi-hotspot` → MIT, `campus-portal-autologin` → MIT.
