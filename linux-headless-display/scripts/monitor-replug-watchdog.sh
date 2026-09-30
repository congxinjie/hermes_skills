#!/bin/bash
# monitor-replug-watchdog.sh
# 防止 GNOME 3.36 显示器热插拔 bug（顶栏/dock 消失）：
# 检测到 显示器从"全部断开"→"有连接" 时，自动重启 gnome-shell，
# 让 shell 在显示器已连接的状态下重新初始化。
#
# 原理：gnome-shell 在"无显示器"状态启动后，插回显示器时
# desktopGrid 初始化失败（日志报 "desktopGrid is undefined"），
# 导致顶栏和 dock 不渲染。重启 shell 即可修复。
#
# 安装：与 templates/monitor-watchdog.service 配合，
#   chmod +x 本脚本，ExecStart 指向本脚本绝对路径，
#   systemctl --user enable --now monitor-watchdog.service

DRM_PATTERNS="/sys/class/drm/card0-*/status"

log() {
    logger -t monitor-watchdog "$1"
    echo "$(date '+%F %T') $1"
}

any_connected() {
    for f in $DRM_PATTERNS; do
        [ "$(cat "$f" 2>/dev/null)" = "connected" ] && return 0
    done
    return 1
}

restart_gnome_shell() {
    local pid
    pid=$(pgrep -o gnome-shell)
    [ -z "$pid" ] && { log "gnome-shell 不在运行，跳过"; return; }

    # 优先用 GNOME 官方重启 API（等效 Alt+F2 r），失败则 SIGTERM（GDM 自动拉起）
    if dbus-send --session --dest=org.gnome.Shell --type=method_call \
        /org/gnome/Shell org.gnome.Shell.Eval string:'global.reexec_self()' \
        >/dev/null 2>&1; then
        log "已通过 dbus 重启 gnome-shell (pid=$pid)"
    else
        kill -TERM "$pid" 2>/dev/null && log "已 SIGTERM gnome-shell (pid=$pid)，GDM 将自动拉起新实例"
    fi
}

# 初始状态：以当前真实状态为准
# （若此刻无显示器，之后插上时能正确触发；若此刻有显示器则不会误触发）
if any_connected; then
    prev_connected=1
else
    prev_connected=0
fi

log "看门狗启动（轮询间隔 3 秒）"

while true; do
    if any_connected; then
        now_connected=1
    else
        now_connected=0
    fi

    # 状态跃迁：全部断开 → 出现连接
    if [ "$now_connected" -eq 1 ] && [ "$prev_connected" -eq 0 ]; then
        log "检测到显示器重新接入，重启 gnome-shell 以修复桌面组件"
        restart_gnome_shell
        sleep 8   # 等 shell 重启完成再继续监控
    fi

    prev_connected=$now_connected
    sleep 3
done
