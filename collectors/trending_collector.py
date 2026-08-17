"""
榜单采集器 — 直接接入信源内部的热度排序结果

背景：普通 RSS 是「时间流」，长尾内容多、信号密度低。
本模块只采集信源内部已有「榜单/热门」组织的优质内容：

  1. Hacker News 热门 — 社区投票 (score) 排序的科技新闻，AI 关键词过滤
  2. HuggingFace 每日论文 — 按 upvotes 排序的 50 篇热点论文
  3. HuggingFace 趋势模型 — 按 trendingScore 排序的热门模型
  4. 极客公园 本周热门 — 编辑精选的 AI/科技/商业热门文章
  5. 掘金 热榜 — 开发者社区热度排序，AI 关键词过滤

每条自动附带信源可信度与热度信号（写入 summary，供 AI 评分参考）。
"""

import re
import requests
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import REQUEST_TIMEOUT, get_source_credibility

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}

# ============================================
# 1. Hacker News 热门
# ============================================
HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
HN_TOP_N = 40        # 从 top 40 里筛 AI 相关
HN_TAKE = 15         # 最多取 15 条

# AI 相关关键词
# 短词用词边界匹配，避免 "available" 误命中 "ai"、"Model F/XT" 误命中 "model"
_AI_WORD_KEYWORDS = [
    r"\bai\b", r"\bllm\b", r"\bgpt\b", r"\bagent\b", r"\brag\b",
    r"\bneural\b", r"\btransformer\b", r"\bdiffusion\b", r"\bmultimodal\b",
    r"\bcopilot\b", r"\bgpu\b", r"\brobot\b", r"\bautonomous\b",
    r"\breasoning\b", r"\binference\b", r"\bembedding\b", r"\bchatbot\b",
    r"\bmachine learning\b", r"\bfine-tun\w*\b",
]
# 品牌/专有名词（无歧义，子串匹配）
_AI_BRAND_KEYWORDS = [
    "openai", "anthropic", "deepseek", "claude", "gemini", "llama",
    "mistral", "nvidia", "huggingface", "chatgpt", "codex", "stable diffusion",
]
# 中文关键词（子串匹配）
_AI_CN_KEYWORDS = ["人工智能", "大模型", "智能体", "模型", "机器学习", "智能"]


def _hn_is_ai(title):
    t = title.lower()
    if any(re.search(kw, t) for kw in _AI_WORD_KEYWORDS):
        return True
    if any(kw in t for kw in _AI_BRAND_KEYWORDS):
        return True
    if any(kw in title for kw in _AI_CN_KEYWORDS):
        return True
    return False


def _fetch_hn_item(item_id):
    try:
        resp = requests.get(HN_ITEM_URL.format(item_id), headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


def _collect_hacker_news():
    """采集 Hacker News 热门，按 score 排序，AI 关键词过滤"""
    articles = []
    try:
        resp = requests.get(HN_TOP_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        ids = resp.json()[:HN_TOP_N]
    except Exception as e:
        print(f"    ❌ Hacker News 热门接口失败: {e}")
        return articles

    # 并行抓取每个 story 详情
    items = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(_fetch_hn_item, i): i for i in ids}
        for fut in as_completed(futures):
            item = fut.result()
            if item and item.get("type") == "story" and item.get("title") and item.get("url"):
                items.append(item)

    # AI 关键词过滤 + 按 score 排序
    items = [it for it in items if _hn_is_ai(it["title"])]
    items.sort(key=lambda x: x.get("score", 0), reverse=True)

    tier, weight = get_source_credibility("Hacker News")
    for it in items[:HN_TAKE]:
        score = it.get("score", 0)
        comments = it.get("descendants", 0)
        ts = it.get("time", 0)
        pub = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if ts else ""
        articles.append({
            "title": it["title"],
            "url": it["url"],
            "summary": f"[HN {score}分 / {comments}评论] {it.get('title', '')}",
            "published": pub,
            "source_name": "Hacker News",
            "source_type": "trending",
            "credibility_tier": tier,
            "credibility_weight": weight,
        })
    return articles


# ============================================
# 2. HuggingFace 每日论文（按 upvotes 排序）
# ============================================
HF_PAPERS_URL = "https://huggingface.co/api/daily_papers"
HF_PAPERS_TAKE = 20


def _collect_hf_papers():
    articles = []
    try:
        resp = requests.get(HF_PAPERS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        papers = resp.json()
    except Exception as e:
        print(f"    ❌ HuggingFace 论文榜接口失败: {e}")
        return articles

    tier, weight = get_source_credibility("HuggingFace Papers")
    for p in papers[:HF_PAPERS_TAKE]:
        paper = p.get("paper", {})
        upvotes = paper.get("upvotes", 0)
        title = paper.get("title", "") or p.get("title", "")
        summary = paper.get("summary", "") or p.get("summary", "")
        paper_id = paper.get("id", "")
        pub = paper.get("publishedAt", "") or p.get("publishedAt", "")
        if pub:
            pub = pub[:10]
        articles.append({
            "title": title,
            "url": f"https://huggingface.co/papers/{paper_id}" if paper_id else f"https://huggingface.co/papers",
            "summary": f"[HF 论文榜 {upvotes}赞] {summary[:200]}",
            "published": pub,
            "source_name": "HuggingFace Papers",
            "source_type": "trending",
            "credibility_tier": tier,
            "credibility_weight": weight,
        })
    return articles


# ============================================
# 3. HuggingFace 趋势模型（按 trendingScore 排序）
# ============================================
HF_MODELS_URL = "https://huggingface.co/api/models?sort=trendingScore&direction=-1&limit=15"
HF_MODELS_TAKE = 10


def _collect_hf_models():
    articles = []
    try:
        resp = requests.get(HF_MODELS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        models = resp.json()
    except Exception as e:
        print(f"    ❌ HuggingFace 趋势模型接口失败: {e}")
        return articles

    tier, weight = get_source_credibility("HuggingFace Models")
    for m in models[:HF_MODELS_TAKE]:
        model_id = m.get("id", "")
        likes = m.get("likes", 0)
        trending = m.get("trendingScore", 0)
        articles.append({
            "title": model_id,
            "url": f"https://huggingface.co/{model_id}" if model_id else "https://huggingface.co/models",
            "summary": f"[HF 趋势模型 {likes}赞 / 热度{trending}] 近期热门的开源模型",
            "published": datetime.now().strftime("%Y-%m-%d"),
            "source_name": "HuggingFace Models",
            "source_type": "trending",
            "credibility_tier": tier,
            "credibility_weight": weight,
        })
    return articles


# ============================================
# 4. 极客公园 本周热门（编辑精选）
# ============================================
GEEKPARK_HOT_URL = "https://mainssl.geekpark.net/api/v1/posts/hot_in_week?per=10"


def _collect_geekpark_hot():
    articles = []
    try:
        resp = requests.get(GEEKPARK_HOT_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        posts = data.get("posts", [])
    except Exception as e:
        print(f"    ❌ 极客公园 热门接口失败: {e}")
        return articles

    tier, weight = get_source_credibility("极客公园 热门")
    for p in posts:
        title = p.get("title", "")
        post_id = p.get("id", "")
        abstract = p.get("abstract", "") or ""
        pub = p.get("published_at", "")[:10] if p.get("published_at") else ""
        articles.append({
            "title": title,
            "url": f"https://www.geekpark.net/news/{post_id}" if post_id else "",
            "summary": f"[极客公园 本周热门] {abstract[:200]}",
            "published": pub,
            "source_name": "极客公园 热门",
            "source_type": "trending",
            "credibility_tier": tier,
            "credibility_weight": weight,
        })
    return articles


# ============================================
# 5. 掘金 热榜（社区热度排序，AI 关键词过滤）
# ============================================
JUEJIN_HOT_URL = "https://api.juejin.cn/content_api/v1/content/article_rank?category_id=6809637769959178254&type=hot"


def _collect_juejin_hot():
    articles = []
    try:
        resp = requests.get(JUEJIN_HOT_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", []) or []
    except Exception as e:
        print(f"    ❌ 掘金 热榜接口失败: {e}")
        return articles

    tier, weight = get_source_credibility("掘金 热榜")
    for it in items:
        content = it.get("content", {})
        title = content.get("title", "")
        if not title:
            continue
        # AI 关键词过滤（复用 HN 的过滤逻辑，同时也加中文关键词）
        if not _hn_is_ai(title):
            # 掘金标题可能含具体技术名词，额外放宽一些
            extra = ["qlora", "lora", "rlhf", "sd", "sdxl", "bert", "langchain", "cursor", "comfyui", "自动化"]
            if not any(kw in title.lower() for kw in extra):
                continue

        cnt = it.get("content_counter", {})
        hot_rank = cnt.get("hot_rank", 0)
        view = cnt.get("view", 0)
        post_id = it.get("content_id", "")
        brief = (content.get("brief_content", "") or "")[:150]
        pub = datetime.fromtimestamp(int(content.get("ctime", "0")), tz=timezone.utc).strftime("%Y-%m-%d") if content.get("ctime") else ""
        articles.append({
            "title": title,
            "url": f"https://juejin.cn/post/{post_id}" if post_id else "",
            "summary": f"[掘金热榜 热度{hot_rank} / {view}阅读] {brief}",
            "published": pub,
            "source_name": "掘金 热榜",
            "source_type": "trending",
            "credibility_tier": tier,
            "credibility_weight": weight,
        })
    return articles


# ============================================
# 6. 36氪 热榜（Playwright 渲染，编辑精选热门）
# ============================================
KR36_HOT_URL = "https://36kr.com/hot-list/catalog"
KR36_TAKE = 15


def _collect_36kr_hot():
    articles = []
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return articles

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_viewport_size({"width": 1920, "height": 1080})
            page.goto(KR36_HOT_URL, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            # 提取文章链接：a 标签 href 含 /p/ 且文本较长
            links = page.eval_on_selector_all("a", """els => els.filter(e => {
                const t = e.innerText.trim();
                const h = e.href || "";
                return t.length > 10 && h.includes("/p/") && !t.includes("@") && !t.includes("http");
            }).map(e => ({t: e.innerText.trim(), h: e.href}))""")

            browser.close()

        tier, weight = get_source_credibility("36氪 热榜")
        seen = set()
        for link in links:
            title = link["t"]
            if title in seen:
                continue
            seen.add(title)
            articles.append({
                "title": title[:120],
                "url": link["h"],
                "summary": f"[36氪热榜] {title[:200]}",
                "published": datetime.now().strftime("%Y-%m-%d"),
                "source_name": "36氪 热榜",
                "source_type": "trending",
                "credibility_tier": tier,
                "credibility_weight": weight,
            })
            if len(articles) >= KR36_TAKE:
                break
    except Exception as e:
        print(f"    ❌ 36氪 热榜: {e}")

    return articles


def collect_trending():
    """采集所有榜单源，返回高热度优质文章"""
    all_articles = []

    print("  🔥 [Hacker News 热门] 采集中...", flush=True)
    hn = _collect_hacker_news()
    all_articles.extend(hn)
    print(f"    ✅ {len(hn)} 条 AI 相关热帖")

    print("  🔥 [HuggingFace 论文榜] 采集中...", flush=True)
    papers = _collect_hf_papers()
    all_articles.extend(papers)
    print(f"    ✅ {len(papers)} 篇热点论文")

    print("  🔥 [HuggingFace 趋势模型] 采集中...", flush=True)
    models = _collect_hf_models()
    all_articles.extend(models)
    print(f"    ✅ {len(models)} 个热门模型")

    print("  🔥 [极客公园 本周热门] 采集中...", flush=True)
    geekpark = _collect_geekpark_hot()
    all_articles.extend(geekpark)
    print(f"    ✅ {len(geekpark)} 条编辑精选")

    print("  🔥 [掘金 热榜] 采集中...", flush=True)
    juejin = _collect_juejin_hot()
    all_articles.extend(juejin)
    print(f"    ✅ {len(juejin)} 条 AI 相关热帖")

    print("  🔥 [36氪 热榜] 采集中...", flush=True)
    kr36 = _collect_36kr_hot()
    all_articles.extend(kr36)
    print(f"    ✅ {len(kr36)} 条热门文章")

    return all_articles


if __name__ == "__main__":
    articles = collect_trending()
    print(f"\n共 {len(articles)} 条")
    for a in articles[:10]:
        print(f"  [{a['source_name']}] {a['title'][:60]}")
