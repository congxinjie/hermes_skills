---
name: linux-headless-display
description: Use for headless Linux desktop and monitor hotplug fixes.
version: 1.0.0
author: hermes-curator
license: CC-BY-4.0
metadata:
  hermes:
    tags: [sysadmin, gnome, display, hotplug, headless, remote-desktop]
    related_skills: [linux-system-diagnostics]
---

# Linux Headless Desktop & Display Hotplug

Covers: verifying a desktop survives monitor unplug, simulating unplug, diagnosing GNOME Shell hotplug crashes (top bar/dock disappear), GPU power management in headless state, and remote desktop (VNC/RDP/ToDesk) prerequisites. Proven on Ubuntu 20.04 GNOME 3.36 X11 + Intel iGPU.

## When to use
- User asks "can I unplug the HDMI / run headless?"
- After replugging a monitor, top bar/dock are gone or the desktop looks broken
- Verifying a remote-desktop agent (ToDesk etc.) works without a display
- Checking GPU power state on a desktop box

## 1. Inventory display state
```bash
lspci | grep -iE "vga|display|3d"          # GPU
for c in /sys/class/drm/card0-*/; do echo "$(basename $c): $(cat $c/status)"; done
xrandr --listmonitors; xrandr | grep -E " connected| disconnected"
```
KEY distinction: physical unplug flips sysfs status to `disconnected`. `xrandr --output X --off` does NOT change sysfs status (cable still present) — it only blanks the output. Watchdogs that poll sysfs status will NOT fire on `xrandr --off`.

## 2. Verify headless survival (simulated unplug)
1. `xrandr --output <OUT> --off` (screen goes dark; fully reversible)
2. Wait ~5s, then verify: `pgrep -a gnome-shell`, `pgrep -a Xorg`, and the remote agent (ToDesk: `pgrep -af ToDesk`)
3. Check agent logs for capture/encode errors (ToDesk: `/var/log/todesk/service*.log`; `read bus value from reg err` is harmless EDID/I2C noise after unplug — do not chase it)
4. Restore: `xrandr --output <OUT> --auto`

Real headless state: `xrandr --listmonitors` shows `Monitors: 0`; X session + gnome-shell + remote agents stay alive. iGPU auto-drops to lowest frequency — verify with `cat /sys/class/drm/card0/gt_act_freq_mhz` (e.g. 350 MHz floor vs 1100 MHz max).

## 3. GNOME 3.36 hotplug bug (top bar + dock vanish)
Symptom: after unplugging the only monitor and replugging, top bar and dock are missing — not hidden, never rendered. The shell may have crashed and auto-restarted meanwhile (PID change visible via `ps -o pid,lstart -p $(pgrep -o gnome-shell)`).

Journal tells the story:
```bash
journalctl --since "2 hours ago" | grep -iE "gnome-shell.*(crash|segfault|error|fatal)" | tail
# smoking gun: Error adding children to desktop: desktopGrid is undefined
```
Cause: shell started while zero monitors were connected; on replug, mutter fails to rebuild the desktop grid (GNOME ≤3.36 bug; fixed in GNOME 42+/Ubuntu 22.04+).

Fix — restart gnome-shell so it initializes with the monitor present:
- `Alt+F2` → `r` (interactive), or
- `dbus-send --session --dest=org.gnome.Shell --type=method_call /org/gnome/Shell org.gnome.Shell.Eval string:'global.reexec_self()'`, or
- `kill -TERM $(pgrep -o gnome-shell)` (GDM respawns it automatically — verified: PID 1259→1324)

Prevention: watchdog polling DRM sysfs status; on transition all-disconnected → connected, restart the shell. See `scripts/monitor-replug-watchdog.sh` + `templates/monitor-watchdog.service` (install as systemd user service, enable). Root fix: upgrade to GNOME 42+.

## 4. Remote desktop on the headless box
- **ToDesk** (relay-based, survives unplug; this user's primary): works with 0 monitors — captures the X session framebuffer. Verify processes + `/var/log/todesk/` logs. Linux build has NO power-saving/black-screen option (Windows-only feature) — not needed anyway, iGPU idles itself.
- **VNC**: vino (GNOME built-in, preinstalled on Ubuntu 20.04, port 5900) or `x11vnc -display :0 -auth guess` (more stable headless). Shares the CURRENT session; unencrypted by default.
- **RDP**: xrdp + xorgxrdp (port 3389, encrypted, native mstsc client) but opens a NEW session, not the current desktop; watch display-number conflicts with GDM.
- Network caveats: campus WiFi client isolation blocks WiFi↔WiFi; ethernet (eno2) bypasses it; no public IPv4 → cross-network needs IPv6 or a relay tool like ToDesk.

## Pitfalls
- If a headless→replug cycle is followed by a REBOOT, GDM can fail to start and the box sticks at the Ubuntu logo (Plymouth never exits). Recovery is tty + `sudo systemctl restart gdm` — see the "Boot stuck at Ubuntu logo" section in `linux-system-diagnostics` (also covers why force-power-off makes it worse).
- Bash: define functions BEFORE calling them — the watchdog's initial-state check failed when placed above the `any_connected()` definition.
- Watchdog initial state must be computed from CURRENT sysfs state (`if any_connected; then prev=1; else prev=0; fi`), never assumed — otherwise a replug at boot is missed.
- `gnome-screenshot` falls back to X11 capture when the shell UI is broken ("Unable to use GNOME Shell's builtin screenshot interface") — still produces valid screenshots headless.
- Video capture devices appear as `/dev/video*` + `lsusb` entries; no /dev/video* means not enumerated (loose USB, underpowered — try rear-panel USB 3.0, or dead). Check `dmesg | grep -i usb` tail for hotplug events.
- i915 power sanity: `/sys/class/drm/card0/power/control` should be `auto`; CPU governor `powersave` is the normal idle state.
