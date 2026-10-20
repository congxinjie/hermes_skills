#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中文网络搜索 —— 多引擎兜底（百度 → Bing → 搜狗 → 360）。

背景：抓多了百度会转验证码（302 → wappass.baidu.com/static/captcha/…，
页面只剩 ~1.4KB）。这是风控不是断网，重试只会加深封禁 —— 直接换引擎。

用法:
    python3 search-cn.py "关键词"
    python3 search-cn.py "关键词" bing        # 指定引擎
    python3 search-cn.py "关键词" 5           # 只显示前 5 条

提示：Bing 中文站对泛化中文查询有"购物/官网偏置"，拿不到你要的东西时
      把关键词写具体、或直接换英文（如 shadPS4 PS5 emulation）。
"""
import sys, re, html, urllib.request, urllib.parse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 直连，绕系统代理


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "zh-CN,zh"})
    r = OPENER.open(req, timeout=timeout)
    return r.getcode(), r.read(), r.geturl()


def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def parse_bing(raw):
    out = []
    for b in re.findall(r'<li class="b_algo".*?</li>', raw, re.S):
        m = re.search(r'<h2>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if not m:
            continue
        cap = re.search(r'<p[^>]*>(.*?)</p>', b, re.S)
        out.append((strip(m.group(2)), m.group(1), strip(cap.group(1)) if cap else ""))
    return out


def parse_baidu(raw):
    out = []
    for href, t in re.findall(r'<h3[^>]*class="[^"]*t[^"]*"[^>]*>\s*'
                              r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', raw, re.S):
        out.append((strip(t), href, ""))
    return out


def parse_generic(raw):
    """搜狗 / 360 通用兜底：抓 <a> 里的标题。"""
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', raw, re.S):
        t = strip(m.group(2))
        if len(t) < 8 or t in seen:
            continue
        seen.add(t)
        out.append((t, m.group(1), ""))
    return out


ENGINES = {
    "baidu": ("https://www.baidu.com/s?wd={q}&rn=20", parse_baidu),
    "bing":  ("https://cn.bing.com/search?q={q}&setlang=zh-CN", parse_bing),
    "sogou": ("https://www.sogou.com/web?query={q}", parse_generic),
    "360":   ("https://www.so.com/s?q={q}", parse_generic),
}


def search(q, engine):
    tpl, parser = ENGINES[engine]
    url = tpl.format(q=urllib.parse.quote(q))
    code, body, final = fetch(url)
    # 百度风控：302 到 wappass 验证码
    if "wappass.baidu.com" in (final or "") or b"captcha" in body[:2000]:
        return None, "百度风控(验证码)"
    raw = body.decode("utf-8", "ignore")
    res = parser(raw)
    if not res:
        return None, "页面长度 %d，未解析出结果" % len(raw)
    return res, None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    q = sys.argv[1]
    order = [sys.argv[2]] if len(sys.argv) > 2 and sys.argv[2] in ENGINES \
        else ["baidu", "bing", "sogou", "360"]
    limit = 12
    for a in sys.argv[2:]:
        if a.isdigit():
            limit = int(a)

    for eng in order:
        try:
            res, err = search(q, eng)
        except Exception as e:
            res, err = None, "异常 %r" % e
        if not res:
            print("[%s] 失败：%s" % (eng, err))
            continue
        print("=" * 60)
        print("[%s] 查询: %s   共 %d 条" % (eng, q, len(res)))
        for i, (title, href, desc) in enumerate(res[:limit], 1):
            print("\n%2d. %s" % (i, title))
            print("    %s" % href[:150])
            if desc:
                print("    %s" % desc[:200])
        return
    print("所有引擎都失败了 —— 检查网络，或换关键词/换机器")


if __name__ == "__main__":
    main()
