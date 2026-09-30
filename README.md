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

## Install

Copy a skill folder into your Hermes skills directory:

```bash
cp -r chinese-web-image-sourcing ~/.hermes/skills/research/
cp -r linux-headless-display     ~/.hermes/skills/sysadmin/
```

Hermes discovers `SKILL.md` files automatically. For the watchdog, install the unit as a systemd user service and enable it.

## Licence

Each skill keeps its own licence (see the `license:` field in its `SKILL.md`):
`chinese-web-image-sourcing` → MIT, `linux-headless-display` → CC‑BY‑4.0.
