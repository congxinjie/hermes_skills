# JS 单页应用（SPA）站点：从 JS bundle 里挖 JSON API

## 症状识别

`curl` 一个页面只拿到 **几百字节**、`<body>` 里只有一个 `<div id="app">` 或
`<div id="root">`，正文全无 —— 这是 **Vue/React 打包的 SPA**，内容靠 JS 异步取。
用文本抽取脚本会得到「提取行数: 1」，**这不是被墙、不是反爬，是没执行 JS**。

```bash
curl -sL "$URL" -o /tmp/p.html -w "size=%{size_download}\n"   # 若 ~700B 且含 /assets/index-*.js
```

## 步骤

```bash
# 1) 找前端 bundle
grep -oE 'src="[^"]+\.js"' /tmp/p.html          # → /assets/index-XXXX.js

# 2) 从 bundle 里挖所有 API 路径（关键一步）
curl -sL "$BASE/assets/index-XXXX.js" -o /tmp/app.js
grep -oE '/api/[a-zA-Z0-9/_{}$.-]+' /tmp/app.js | sort -u
#   会看到形如 /api/projects/${slug}/tree、/api/chapters/${id} 的模板字符串
#   （含 ${} 的就是占位符，换成真实 slug/id 即可）

# 3) 直接打接口拿 JSON
curl -sL "$BASE/api/projects" | python -m json.tool | head -40
curl -sL "$BASE/api/projects/<slug>/tree"          # 目录树
curl -sL "$BASE/api/chapters/<id>"                  # 单章正文
```

正文常在 `data.chapter.content`（**Markdown 原文**），比 DOM 抓取干净得多；
目录树在 `data`（数组或带 `children`）。

## 实测实例：Hiveton 产品 Wiki

产品文档站 `wiki.hiveton.com` 是 SPA，页面只 702 字节。照上面走：

```
grep -oE 'src="[^"]+\.js"'         → /assets/index-CgVxOT-h.js
grep -oE '/api/[^"\x27]+' app.js   → /api/projects、/api/projects/${x}、
                                      /api/projects/${x}/tree、/api/chapters/${id}、
                                      /api/chapters/by-slug/${proj}/${slug}、/api/tags
curl /api/projects                 → 全部产品名 + 一句话定位
curl /api/projects/h5000m/tree     → 10 个文档章节（含 id、slug）
curl /api/chapters/47              → data.chapter.content 是完整 Markdown
```

一次拿到「产品是什么 / 支持哪些 5G 模组 / 安装与刷机流程」——**搜索片段给不了的信息量**。

## 顺带一条研究习惯

问 **硬件/芯片规格**（"X 性能如何""跟 Y 比呢"）时：

1. **优先去厂商官网 / 官方 Wiki / 数据手册**取权威参数（Espressif 产品页、
   FriendlyELEC Wiki、Rockchip、Intel ARK…），**别拿搜索片段当参数**；
2. 官网若是 SPA → 用上面的 API 法；
3. **横向对比表 + 选型建议**是这类问题的期望输出形态（用户要的是"选哪个"）；
4. **查不到的项（如具体主频、跑分）明确写"没查到、不编"** ——
   搜索被限流时宁可给"不确定"，也不要给一个看着合理的数字。
