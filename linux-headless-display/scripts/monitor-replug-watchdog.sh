#!/bin/bash
# monitor-replug-watchdog.sh  (v2 · xrandr 安全版)
#
# 背景：v1 在显示器热插拔后调用 global.reexec_self() 重启 gnome-shell。
#       但本机 desktop-icons@csoriano 是 3.34 版扩展、跑在 GNOME 3.36.9 上，
#       shell reexec 时会在 desktopGrid.js:209 抛
#       "Argument 'instance' may not be null"，把整个会话带崩
#       （表现为：接显示器无信号 + ToDesk 掉线）。
#
# v2 原则：只做「重新点亮输出」，绝不重启、不杀 gnome-shell。
#
# 日志：~/.local/state/monitor-watchdog.log  +  journalctl -t monitor-watchdog

DRM_GLOB="/sys/class/drm/card0-*/status"
LOG_DIR="$HOME/.local/state"
LOG="$LOG_DIR/monitor-watchdog.log"
mkdir -p "$LOG_DIR"

log() {
    logger -t monitor-watchdog "$1" 2>/dev/null
    echo "$(date '+%F %T') $1" >> "$LOG"
}

# 统计当前"connected"的输出数量
dr_count() {
    local n=0 f
    for f in $DRM_GLOB; do
        [ "$(cat "$f" 2>/dev/null)" = "connected" ] && n=$((n+1))
    done
    echo "$n"
}

# sysfs 名 -> xrandr 名：  card0-HDMI-A-1 -> HDMI-1 ; card0-DP-1 -> DP-1
xname() {
    local b
    b=$(basename "$(dirname "$1")")
    b=${b#card0-}
    b=${b/HDMI-A-/HDMI-}
    echo "$b"
}

# 对已连接但未启用的输出执行 xrandr --auto
recover() {
    export DISPLAY="${DISPLAY:-:0}"
    export XAUTHORITY="${XAUTHORITY:-/run/user/$(id -u)/gdm/Xauthority}"

    local f name did=0
    for f in $DRM_GLOB; do
        [ "$(cat "$f" 2>/dev/null)" = "connected" ] || continue
        name=$(xname "$f")

        # 已经点亮（connected 且带分辨率）就跳过
        if xrandr --query 2>/dev/null | grep -qE "^${name} connected( primary)? +[0-9]+x[0-9]+"; then
            continue
        fi

        log "尝试点亮 ${name} …"
        if xrandr --output "$name" --auto --primary >>"$LOG" 2>&1; then
            log "${name} 点亮成功 ✅"
            did=1
        else
            log "${name} 点亮失败 ✘（可尝试重新插拔或手动 xrandr）"
        fi
    done

    [ "$did" -eq 0 ] && log "无需点亮（系统已自动生效）"
    # 注意：这里绝不重启 gnome-shell
}

prev=$(dr_count)
log "看门狗 v2 启动（xrandr 安全模式，轮询 3s），当前已连接输出数=$prev"

while true; do
    now=$(dr_count)
    if [ "$now" -gt 0 ] && [ "$prev" -eq 0 ]; then
        log "检测到显示器接入（0 → $now），用 xrandr 恢复（不重启 shell）"
        sleep 2
        recover
        sleep 5
    fi
    prev=$now
    sleep 3
done
