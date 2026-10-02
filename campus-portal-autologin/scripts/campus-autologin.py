#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NJUST 校园网(锐捷 ePortal) 自动重登
- 每隔一段时间检测是否掉线；掉线则调用 /api/portal/v1/login 重新认证
- 账号密码从 ~/.config/campus-login.conf 读取（USERNAME=... / PASSWORD=...）
- 掉线时校园 DNS 常解析不了域名 → 自动回退用 portal IP(202.119.80.115)
- 日志: ~/.campus-autologin.log
"""
import os, sys, json, time, socket, urllib.request, urllib.error

CONF = os.path.expanduser("~/.config/campus-login.conf")
LOG  = os.path.expanduser("~/.campus-autologin.log")

PORTAL_HOST = "m.njust.edu.cn"
PORTAL_IP   = "202.119.80.115"
API_HOST = "http://%s/api/portal/v1/login" % PORTAL_HOST
API_IP   = "http://%s/api/portal/v1/login" % PORTAL_IP
PROBE = "http://www.baidu.com"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

# 不用系统代理（Clash），校园网认证必须直连
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def read_conf():
    if not os.path.exists(CONF):
        log("缺少配置文件 %s" % CONF)
        sys.exit(2)
    d = {}
    for line in open(CONF, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        d[k.strip()] = v.strip().strip('"').strip("'")
    return d.get("USERNAME"), d.get("PASSWORD")


def online():
    """在线返回 True；被重定向到 portal / 请求失败返回 False"""
    try:
        req = urllib.request.Request(PROBE, headers={"User-Agent": UA})
        r = OPENER.open(req, timeout=6)
        code, final = r.getcode(), r.geturl()
        r.read(64)
        return code == 200 and PORTAL_HOST not in final and PORTAL_IP not in final
    except Exception:
        return False


def _post(url, body, use_host_header):
    headers = {"Content-Type": "application/json", "User-Agent": UA}
    if use_host_header:
        headers["Host"] = PORTAL_HOST
    req = urllib.request.Request(url, data=body, headers=headers)
    return OPENER.open(req, timeout=10).read().decode("utf-8", "ignore")


def login(user, pwd):
    body = json.dumps({"domain": "default", "username": user, "password": pwd}).encode()
    last = "(未执行)"
    # 每轮：先试域名，再试 IP；共 3 轮
    for attempt in range(1, 4):
        for label, url, wh in (("域名", API_HOST, False), ("IP", API_IP, True)):
            try:
                resp = _post(url, body, wh)
            except Exception as e:
                last = "%s 请求异常 %r" % (label, e)
                continue
            try:
                j = json.loads(resp)
            except Exception:
                last = "%s 响应无法解析: %s" % (label, resp[:120])
                continue
            code = j.get("reply_code")
            if code == 0:
                log("登录成功 ✔ [%s]" % label)
                return True
            last = "%s reply_code=%s msg=%s" % (
                label, code, str(j.get("reply_msg") or j.get("msg") or "")[:100])
        time.sleep(3)
    log("登录失败: " + last)
    return False


def main():
    user, pwd = read_conf()
    if not user or not pwd:
        log("配置文件缺少 USERNAME/PASSWORD")
        sys.exit(2)
    if online():
        if "--verbose" in sys.argv:
            log("在线，无需操作")
        return
    # DNS 是否可用（仅记录，便于诊断）
    try:
        socket.gethostbyname(PORTAL_HOST)
        dns = "ok"
    except Exception:
        dns = "fail"
    log("检测到未认证，尝试自动登录… (DNS:%s)" % dns)
    if login(user, pwd):
        # 登录成功≠立刻能上网：认证生效可能有延迟，多等几轮再复检，避免误报
        waits, elapsed = [2, 5, 8, 12], 0
        for n, w in enumerate(waits, 1):
            time.sleep(w)
            elapsed += w
            if online():
                log("复检: 已恢复在线 ✔ (第%d次复检, 累计%ds)" % (n, elapsed))
                return
        log("复检: 仍不在线 ✘ (已复检%d次/累计%ds)" % (len(waits), elapsed))


if __name__ == "__main__":
    main()
