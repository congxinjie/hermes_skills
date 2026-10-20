---
name: linux-headless-display
description: Use for headless Linux desktop and monitor hotplug fixes.
version: 1.1.0
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

⚠️ **DANGER — do NOT auto-restart gnome-shell when `desktop-icons@csoriano` is installed.**

On Ubuntu 20.04 the packaged desktop-icons is the **3.34** extension running on GNOME **3.36.9** (`metadata.json: "shell-version": ["3.34.0"]`, package `20.04.0-3~ubuntu20.04.6`). On shell reexec it throws `JS ERROR: Argument 'instance' (type interface) may not be null` at `desktopGrid.js:209` (`_onDestroy`), which **kills the whole session**: screen loses signal, `polkitd: Unregistered Authentication Agent for unix-session:N (disconnected from bus)`, and remote agents die (`ToDesk: Fatal IO error 11 on X server :0`). GDM's replacement X session then fails with `No outputs definitely connected` + `drmSetMaster failed: Permission denied`. Only a hard power-cycle recovers.

Check before touching the shell:
```bash
gnome-extensions list --enabled | grep desktop-icons
grep -A1 shell-version /usr/share/gnome-shell/extensions/desktop-icons@csoriano/metadata.json
gnome-shell --version
```

**Preferred fix (v2, safe): re-enable the output with xrandr — never restart the shell.**
```bash
xrandr --query | grep -E "^HDMI|^DP"          # find the connected output
xrandr --output HDMI-1 --auto --primary
```
`scripts/monitor-replug-watchdog.sh` (v2) does exactly this on the all-disconnected → connected transition: it polls `/sys/class/drm/card0-*/status` and calls `xrandr --auto`, and never touches gnome-shell.

**Fallbacks, in increasing risk:** reload just the extension (`gnome-extensions disable/enable desktop-icons@csoriano`) → disable the extension entirely → manual `Alt+F2` → `r` (user present) → `kill -TERM $(pgrep -o gnome-shell)` ONLY if desktop-icons is not installed. Root fix: GNOME 42+ or replace desktop-icons with `nemo-desktop`.

## 4. Remote desktop on the headless box
- **ToDesk** (relay-based, survives unplug; this user's primary): works with 0 monitors — captures the X session framebuffer. Verify processes + `/var/log/todesk/` logs. Linux build has NO power-saving/black-screen option (Windows-only feature) — not needed anyway, iGPU idles itself.
- **VNC**: vino (GNOME built-in, preinstalled on Ubuntu 20.04, port 5900) or `x11vnc -display :0 -auth guess` (more stable headless). Shares the CURRENT session; unencrypted by default.
- **RDP**: xrdp + xorgxrdp (port 3389, encrypted, native mstsc client) but opens a NEW session, not the current desktop; watch display-number conflicts with GDM.
- Network caveats: campus WiFi client isolation blocks WiFi↔WiFi; ethernet (eno2) bypasses it; no public IPv4 → cross-network needs IPv6 or a relay tool like ToDesk.

## Pitfalls
- **NEVER automate a gnome-shell restart without checking extension/shell version compatibility.** A 3.34 `desktop-icons` on shell 3.36 turns `global.reexec_self()` into a session-killer (see §3): no signal, remote desktop dead, and the box needs a hard power-off. Compare `metadata.json: shell-version` against `gnome-shell --version` first.
- After that crash GDM reports `drmSetMaster failed: Permission denied` because a stale X still owns the GPU — a `systemctl restart gdm` from tty (sometimes twice) clears it.
- If a headless→replug cycle is followed by a REBOOT, GDM can fail to start and the box sticks at the Ubuntu logo (Plymouth never exits). Recovery is tty + `sudo systemctl restart gdm` — see the "Boot stuck at Ubuntu logo" section in `linux-system-diagnostics` (also covers why force-power-off makes it worse).
- Bash: define functions BEFORE calling them — the watchdog's initial-state check failed when placed above the `any_connected()` definition.
- Watchdog initial state must be computed from CURRENT sysfs state (`if any_connected; then prev=1; else prev=0; fi`), never assumed — otherwise a replug at boot is missed.
- `gnome-screenshot` falls back to X11 capture when the shell UI is broken ("Unable to use GNOME Shell's builtin screenshot interface") — still produces valid screenshots headless.
- Video capture devices appear as `/dev/video*` + `lsusb` entries; no /dev/video* means not enumerated (loose USB, underpowered — try rear-panel USB 3.0, or dead). Check `dmesg | grep -i usb` tail for hotplug events.
- i915 power sanity: `/sys/class/drm/card0/power/control` should be `auto`; CPU governor `powersave` is the normal idle state.
