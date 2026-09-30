---
name: github-stable-access
description: Use when GitHub is blocked, flaky, or rate-limited.
version: 1.0.0
author: congxinjie
license: MIT
metadata:
  hermes:
    tags: [github, network, china, proxy, ssh, cdn, tarball]
    related_skills: [github-auth, installing-hermes-skills]
---

# 受限网络下稳定使用 GitHub

## When to Use（何时用）
- `git clone` / `git push` 报 **TLS 握手失败 / timeout / connection reset**；
- `raw.githubusercontent.com` 拉不到文件；
- `hermes skills install` 报 **GitHub API rate limit**；
- 校园网 / 公司网 / 国内网络访问 GitHub 时通时断。

## 先诊断：到底哪条路通？

**核心原则：GitHub 有几条独立通道，各走各的，别把它们混为一谈。**

| 通道 | 常见结果 | 对策 |
|------|---------|------|
| **SSH** `git@github.com:22` | ✅ **通常最稳**（HTTPS 被墙时它常常还通） | git 全部操作走 SSH |
| **HTTPS** `https://github.com` | ❌ 常被 TLS 打断（`gnutls_handshake() failed: TLS connection was non-properly terminated`） | 别指望，改 SSH |
| **raw** `raw.githubusercontent.com` | ❌ 时通时断，多半不通 | 换 jsDelivr / codeload |
| **jsDelivr CDN** `cdn.jsdelivr.net/gh/...` | ✅ 稳（镜像 GitHub，不走 GitHub 域） | 拿**单个文件**的首选 |
| **codeload** `codeload.github.com/.../tar.gz` | ✅ 稳 | 拿**整个仓库** |
| **API** `api.github.com` | ⚠️ 匿名**仅 60 次/小时**，易耗尽 | 配 `GITHUB_TOKEN` |

> ⚠️ **测连通性前必须先清代理**，否则结论是假的：
> ```bash
> unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
> ```
> Clash 等代理会让"直连测试"得到假结果（假"不通"，或走死代理）。注意 `no_proxy` 常只放行 `10.x` 内网段，公网域名一律走代理——代理一挂，全挂。

## 步骤

### 1. 配 SSH（一劳永逸，git 操作首选）
```bash
ssh-keygen -t ed25519 -C "$USER@pc"        # 已有可跳过
cat ~/.ssh/id_ed25519.pub                  # 复制整行
```
→ 打开 **https://github.com/settings/keys** → New SSH key → 粘贴 → Add。

验证：
```bash
ssh -T git@github.com
# 成功: "Hi <username>! You've successfully authenticated, but GitHub does not provide shell access."
# 失败: "Permission denied (publickey)" = 公钥没加上 / 加到了别的账号
```
把 remote 换成 SSH：
```bash
git remote set-url origin git@github.com:<user>/<repo>.git
```

### 2. 拿单个文件 → jsDelivr 镜像
```
https://cdn.jsdelivr.net/gh/<user>/<repo>@<ref>/<path/to/file>
```
列目录（找文件名）：
```
https://data.jsdelivr.com/v1/packages/gh/<user>/<repo>@<ref>?structure=flat
```
> `@<ref>` 可以是 `main`/`master`/tag/commit。

### 3. 拿整个仓库 → codeload tarball
```bash
curl -sL -m 120 "https://codeload.github.com/<user>/<repo>/tar.gz/refs/heads/main" -o repo.tar.gz
tar -xzf repo.tar.gz
```
> 也可用 `https://github.com/<user>/<repo>/archive/refs/heads/main.tar.gz`。

### 4. API 提额 → 配 token
- 生成：https://github.com/settings/tokens（勾 `repo`）
- 用：`export GITHUB_TOKEN=...`（`gh auth login` 亦可）

### 5. `hermes skills install` 撞限额时
hub 安装依赖 GitHub API，限额耗尽会报 `rate limit exceeded`（约 1 小时恢复）。
**绕过**：用 codeload 下整包 → 手动解压到 `~/.hermes/skills/<category>/<name>/`（Hermes 自动识别 `SKILL.md`）。

## Pitfalls（坑）
1. **代理污染诊断**：不 `unset` 代理变量就测，会得到"假不通"或"假通"，浪费大量时间。
2. **SSH 通了 ≠ 有权限**：`ssh -T` 返回 `Hi <user>!` 才算认证成功；`Permission denied (publickey)` 说明公钥没登记。
3. **raw 被墙 与 API 限额是两件事**：一个是被网络拦，一个是 GitHub 计数限制，别混着查。
4. **HTTPS clone 失败 ≠ 仓库不存在**：先 `ssh -T` 确认认证，再怀疑仓库名/权限（`Repository not found` 也可能是**名字拼错**或建在别的账号下）。
5. **jsDelivr 的目录列表 ≠ 实际可服务**：树里列出的文件仍可能 404，拿不到就换 codeload 整包。
6. **`&amp;` 转义**：从 HTML 抓到的图/文件 URL 带 `&amp;`，不 `html.unescape()` 会下载 0 字节。
7. **edge case**：若 SSH 22 端口也被封，试 `ssh.github.com:443`（`~/.ssh/config` 里 `Hostname ssh.github.com` / `Port 443`）。

## 验证
```bash
ssh -T git@github.com                                   # 认证
git ls-remote <repo>                                    # 读仓库
curl -sI https://cdn.jsdelivr.net/gh/<user>/<repo>@main/README.md | head -1   # 200
```
