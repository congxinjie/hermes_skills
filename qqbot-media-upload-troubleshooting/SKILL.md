---
name: qqbot-media-upload-troubleshooting
description: Use when QQ bot can't send images/files but text works.
version: 1.0.0
author: congxinjie
license: MIT
metadata:
  hermes:
    tags: [qqbot, media, upload, dns, cos, gateway]
    related_skills: [hermes-qqbot-gateway, github-stable-access]
---

# QQ Bot 发不了图/文件 —— 定位与修复

## When to Use / 何时用

- 机器人**发文字正常**，但**图片/文件发不出去**
- 网关日志出现 `Media send failed` / `upload failed` / `Blocked request - DNS resolution failed`
- 用户说"你发的图我收不到"

**注意方向**：出站（bot→用户）失败，**不是**用户发不上来。

## 一分钟定位

```bash
journalctl --user -u hermes-gateway -n 50 --no-pager | grep -iE "upload|media|cos|dns|blocked"
```

| 日志特征 | 含义 | 跳到 |
|---|---|---|
| `Blocked request - DNS resolution failed for qqbot-file-upload-*.cos.accelerate.myqcloud.com` | **DNS 解析缺口**（最常见）| §A |
| `PUT part 1/N failed` + 403/超时 | 上传鉴权/网络 | §B |
| `Media send failed` + 文件过大/格式 | 文件本身问题 | §C |

## §A DNS 解析缺口（最常见）

上传走腾讯 COS：`qqbot-file-upload-<appid>.cos.accelerate.myqcloud.com`。
Hermes 的 SSRF 防护会把**解析失败当成拦截**（报 "Blocked request"），所以看起来像"被墙"，其实只是解析不出来。

### 逐步确认

```bash
D=qqbot-file-upload-1251316161.cos.accelerate.myqcloud.com

getent hosts "$D"                                  # ① 系统DNS：失败?
nslookup "$D" 223.5.5.5 | tail -3                  # ② UDP53：超时?
curl -s -m 10 -o /dev/null -w "%{http_code}\n" -x http://127.0.0.1:7897 "https://$D/"   # ③ 代理：403=通了
curl -s -m 10 --noproxy '*' "https://223.5.5.5/resolve?name=$D&type=A"                 # ④ DoH：能解析
```

**判定**：①失败 + ③通 → **系统 DNS 缺口**，代理能解析。这就是绝大多数情况。

### 修复

**方案 1（零 root，推荐先用）**：让 QQ 适配器走代理

```bash
# 关键：必须删掉整行，不能设 0
grep -v "^QQBOT_DIRECT=" ~/.config/environment.d/proxy.conf > /tmp/e && mv /tmp/e ~/.config/environment.d/proxy.conf
systemctl --user set-environment QQBOT_DIRECT=      # 空值（见坑 1）
hermes gateway restart                              # 必须在自己的终端跑
```

**方案 2（根治，需 root）**：本地 DoH 转发器

`dnscrypt-proxy` / `cloudflared` / `AdGuardHome` 监听 `127.0.0.1:5300`，
再让 resolved 用它（**必须同时处理 per-link DNS，见坑 3**）：

```ini
# /etc/systemd/resolved.conf
[Resolve]
DNS=127.0.0.1:5300
DNSOverTLS=no
```
```bash
nmcli connection modify "<连接名>" ipv4.ignore-auto-dns yes ipv4.dns "127.0.0.1"
```

**方案 3（救急）**：`/etc/hosts` 固定 IP（CDN IP 会轮换，只顶几小时）

```bash
IP=$(curl -s --noproxy '*' "https://223.5.5.5/resolve?name=$D&type=A" | grep -oE '"data":"[0-9.]+"' | head -1 | cut -d'"' -f4)
echo "$IP $D" | sudo tee -a /etc/hosts
```

## §B 上传鉴权/网络

- 确认 `QQBOT_APP_ID` / `QQBOT_APP_SECRET` 有效（能发文字就说明 token 没问题 → 大概率还是 §A）
- 文件过大：QQ 单文件有上限，压缩后再发

## §C 文件本身

- 图片转 JPG/PNG（别发 webp/heic）
- 中文文件名在某些版本会出问题 → 改成 ASCII 名再发

## 坑（务必看）

1. **`QQBOT_DIRECT=0` 是无效的！**
   代码是 `trust_env = not bool(os.getenv("QQBOT_DIRECT"))`，
   `bool("0") == True` → 设成 `"0"` **仍然绕过代理**。
   → 必须**删掉整行**，或 `set-environment QQBOT_DIRECT=`（空值，`bool("")==False`）。

2. **只改 `environment.d/*.conf` 不生效**：运行中的 user manager 缓存着旧值。
   `unset-environment` 对它也无效（会从 environment.d 重新读）。
   → 用 `set-environment VAR=` 覆盖，然后重启网关。

3. **`DNSOverTLS=yes` 会连 per-link 的 DHCP DNS 一起强制 DoT**。
   DHCP 下发的路由器 DNS 通常不支持 DoT → 全部解析失败、整机断网。
   → 必须先 `nmcli ... ipv4.ignore-auto-dns yes`。

4. **DoT(853) 可能"握手成功但查询不通"**。
   `openssl s_client -connect 223.5.5.5:853` 通过 ≠ 能用。
   看 resolved 日志：`Using degraded feature set (UDP) for DNS server ...` = **DoT 建不起来已降级**，此时若 UDP53 也被封就是死路。

5. **这是权衡，不是纯升级**：改成走代理后，**Clash 挂了机器人会整个离线**（不只媒体）。原 `QQBOT_DIRECT=1` 就是为了防这个。DNS 修好后应改回直连。

6. **不能从网关进程内部重启网关**（会 SIGTERM 自己）。必须让用户在**自己的终端**跑 `hermes gateway restart`。

## 验证

```bash
journalctl --user -u hermes-gateway -n 30 --no-pager | grep -iE "upload|media"
# 期望：upload part 1/1 ok / media sent（无 Blocked request）
```
然后让机器人发一张小图（<100KB 的 JPG 最快验证）。
