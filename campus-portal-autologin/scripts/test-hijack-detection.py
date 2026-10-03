#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
离线验证：确认自动重登脚本能识破"HTTP 通、HTTPS 被劫持"这一状态。

背景：有些校园网在【未认证】时只劫持 HTTPS（用自签证书拦截），明文 HTTP
仍返回 200。若探针只测 HTTP，脚本会静默认为"在线"，实际已断网数小时。
本脚本用本地自签 HTTPS 服务模拟这种劫持，验证 https_ok() 能正确返回 False。

用法：
    python3 test-hijack-detection.py [/path/to/campus-autologin.py]

依赖：openssl（生成自签证书）。仅在本机 /tmp 操作，不改系统配置、不写日志。
"""
import importlib.util, ssl, threading, http.server, subprocess, os, tempfile, sys, socket

TARGET = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.local/bin/campus-autologin.py")

if not os.path.exists(TARGET):
    print("找不到目标脚本:", TARGET); sys.exit(2)

TMP = tempfile.mkdtemp()
KEY, CRT = os.path.join(TMP, "k.pem"), os.path.join(TMP, "c.pem")

# 1) 自签证书
r = subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", KEY, "-out", CRT, "-days", "1", "-subj", "/CN=localhost"],
                   capture_output=True)
if r.returncode:
    print("openssl 生成证书失败:", r.stderr.decode()[:200]); sys.exit(2)

# 2) 本地自签 HTTPS 服务（选一个空闲端口）
sock = socket.socket(); sock.bind(("127.0.0.1", 0)); PORT = sock.getsockname()[1]; sock.close()

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass

srv = http.server.HTTPServer(("127.0.0.1", PORT), H)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(CRT, KEY)
srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()

# 3) 载入被测脚本
spec = importlib.util.spec_from_file_location("cam", TARGET)
cam = importlib.util.module_from_spec(spec); spec.loader.exec_module(cam)

print("=== 检测函数验证 ===")
a = cam.online()            # 明文 HTTP 探针
b = cam.https_ok()          # 正常 HTTPS
cam.HTTPS_PROBE = "https://127.0.0.1:%d/" % PORT
c = cam.https_ok()          # 自签/劫持 HTTPS
srv.shutdown()

print("online()  http          ->", a, " 期望 True")
print("https_ok() 正常         ->", b, " 期望 True")
print("https_ok() 自签/劫持    ->", c, " 期望 False")
print()
ok = (a and b and not c)
print("分支判定:", "✅ 能判定为『HTTP通但HTTPS被劫持』→ 触发重登" if (a and not c) else "✘ 未识别为劫持")
print("探测可区分正常/劫持:", "✅" if (b and not c) else "✘")
print()
print("总体:", "PASS ✅" if ok else "FAIL ✘")
sys.exit(0 if ok else 1)
