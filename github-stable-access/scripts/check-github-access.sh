#!/bin/bash
# GitHub 通达性诊断 —— 打印各条通道的真实结果
# 用法: bash check-github-access.sh
echo "=========================================="
echo " GitHub 通达性诊断  ($(date '+%F %T'))"
echo "=========================================="

# 关键：先清代理变量，否则直连测试会得到假结果
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY

t() {  # t <label> <url>
  code=$(curl -s -m 12 -o /dev/null -w "%{http_code}" "$2" 2>/dev/null)
  printf "%-28s %s\n" "$1" "$code"
}

echo "--- HTTPS / GitHub 官方域 ---"
t "github.com"              "https://github.com"
t "codeload (tarball)"      "https://codeload.github.com/anthropics/skills/tar.gz/refs/heads/main"
t "raw.githubusercontent"   "https://raw.githubusercontent.com/anthropics/skills/main/README.md"

echo ""
echo "--- CDN 镜像（raw 被墙时的替代）---"
t "jsDelivr (file)"         "https://cdn.jsdelivr.net/gh/anthropics/skills@main/README.md"

echo ""
echo "--- GitHub API（看剩余额度）---"
curl -s -m 12 "https://api.github.com/rate_limit" 2>/dev/null \
  | sed -n 's/.*"remaining":[[:space:]]*\([0-9]*\).*/剩余额度: \1 \/ 60（匿名） 次\/小时/p' | head -1 || echo "api.github.com        连不上"

echo ""
echo "--- SSH (端口 22) ---"
out=$(timeout 15 ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -T git@github.com 2>&1 | head -1)
echo "${out:-SSH 无响应}"

echo ""
echo "--- SSH (端口 443 备用) ---"
timeout 15 ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -p 443 -T git@ssh.github.com 2>&1 | head -1

echo ""
echo "=========================================="
echo "判读: 200=通 / 000=不通"
echo "  clone/push 用 SSH;单文件用 jsDelivr;整包用 codeload;API 限额→配 GITHUB_TOKEN"
echo "=========================================="
