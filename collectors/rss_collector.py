"""
RSS 采集器 — 18 个可靠信息源（删除不可达源，补入 8 个高可信度新源）

每条采集自动附带信源等级和可信度权重
"""

import feedparser
import requests
import re
from datetime import datetime, timedelta
from config import COLLECT_DAYS, REQUEST_TIMEOUT, get_source_credibility

# ============================================
# RSS 源列表 (18 个，实测可用 ≥10)
# ============================================
SOURCES = [
    # ===== 国内科技媒体 (T3) =====
    {"name": "量子位", "url": "https://www.qbitai.com/feed"},
    {"name": "少数派", "url": "https://sspai.com/feed"},
    {"name": "极客公园", "url": "https://www.geekpark.net/rss"},
    {"name": "雷锋网", "url": "https://www.leiphone.com/feed"},
    {"name": "InfoQ 中文", "url": "https://www.infoq.cn/feed"},
    {"name": "爱范儿", "url": "https://www.ifanr.com/feed"},

    # ===== 海外 AI 官方博客 (T1) =====
    {"name": "OpenAI Blog", "url": "https://openai.com/blog/rss.xml"},
    {"name": "DeepMind Blog", "url": "https://deepmind.google/blog/rss.xml"},
    {"name": "Hugging Face Blog", "url": "https://huggingface.co/blog/feed.xml"},
    {"name": "NVIDIA AI Blog", "url": "https://blogs.nvidia.com/feed/"},

    # ===== 海外 AI 媒体 (T2) =====
    {"name": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/"},
    {"name": "MarkTechPost", "url": "https://www.marktechpost.com/feed/"},
    {"name": "InfoQ (en)", "url": "https://feed.infoq.com/"},
    {"name": "ZDNet AI", "url": "https://www.zdnet.com/topic/artificial-intelligence/rss.xml"},
    {"name": "Wired AI", "url": "https://www.wired.com/feed/tag/ai/latest/rss"},
    {"name": "The Register AI", "url": "https://www.theregister.com/software/ai_ml/headlines.atom"},
    {"name": "Nature AI", "url": "https://www.nature.com/subjects/computer-science.rss"},

    # ===== AI 工具/产品发现 (T2) =====
    {"name": "Product Hunt", "url": "https://www.producthunt.com/feed"},

    # ===== 学术论文（大幅压量：前沿研究只留最相关的少量，热点论文由 HF 论文榜覆盖）=====
    {"name": "Retail Dive", "url": "https://www.retaildive.com/feeds/news/"},
    {"name": "Modern Retail", "url": "https://www.modernretail.co/feed/"},
    {"name": "MarTech", "url": "https://martech.org/feed/"},

    # ===== 学术论文（大幅压量：前沿研究只留最相关的少量，热点论文由 HF 论文榜覆盖）=====
    {"name": "ArXiv cs.AI", "url": "https://rss.arxiv.org/rss/cs.AI", "limit": 8},
    {"name": "ArXiv cs.CL", "url": "https://rss.arxiv.org/rss/cs.CL", "limit": 5},

    # ===== GitHub 官方 (T1/T2) =====
    {"name": "GitHub Blog", "url": "https://github.blog/feed/"},
    {"name": "GitHub Changelog", "url": "https://github.blog/changelog/feed/"},

    # ===== KOL 周报 (T1) =====
    {"name": "Import AI", "url": "https://importai.substack.com/feed"},
]


def _fetch_feed(url, timeout):
    """带超时的 RSS 抓取"""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=timeout,
            allow_redirects=True,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.ConnectionError:
        return None
    except Exception:
        return None

    return feedparser.parse(resp.content)


def _parse_date(entry):
    for field in ["published_parsed", "updated_parsed"]:
        parsed = getattr(entry, field, None)
        if parsed:
            return datetime(*parsed[:6])
    return None


def _is_recent(pub_date):
    if pub_date is None:
        return True
    return pub_date >= datetime.now() - timedelta(days=COLLECT_DAYS)


def _clean_summary(text):
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:300]


def collect_rss():
    """采集所有 RSS 源，自动附带可信度信息"""
    all_articles = []

    for source in SOURCES:
        name = source["name"]
        url = source["url"]
        limit = source.get("limit", 0)
        tier, weight = get_source_credibility(name)

        try:
            print(f"  📡 [{name}] (T{tier[-1]}) ...", flush=True)
            feed = _fetch_feed(url, timeout=REQUEST_TIMEOUT)

            if feed is None:
                print(f"  ⚠️  [{name}] 网络不可达")
                continue
            if not feed.entries:
                print(f"  ⚠️  [{name}] 无内容")
                continue

            count = 0
            for entry in feed.entries:
                pub_date = _parse_date(entry)
                if not _is_recent(pub_date):
                    continue

                article = {
                    "title": getattr(entry, "title", "无标题"),
                    "url": getattr(entry, "link", ""),
                    "summary": _clean_summary(getattr(entry, "summary", "")),
                    "published": pub_date.strftime("%Y-%m-%d %H:%M") if pub_date else "",
                    "source_name": name,
                    "source_type": "rss",
                    "credibility_tier": tier,
                    "credibility_weight": weight,
                }
                all_articles.append(article)
                count += 1

                if limit and count >= limit:
                    break

            print(f"  ✅ [{name}] {count} 篇")

        except Exception as e:
            print(f"  ❌ [{name}] {e}")

    return all_articles


if __name__ == "__main__":
    articles = collect_rss()
    print(f"\n共 {len(articles)} 篇")
    from collections import Counter
    src = Counter(a["source_name"] for a in articles)
    for k, v in src.most_common():
        print(f"  {k}: {v}篇")
