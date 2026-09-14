"""
微信公众号采集器 — 搜狗网页搜索（requests + BeautifulSoup）

采集策略（白名单优先 + 通用关键词兜底）：
  1. 优质公众号白名单：对每个号搜「公众号名 AI」，召回该号 AI 相关文章
  2. 通用 AI 关键词兜底：覆盖未在名单内的优质内容

搜狗网页搜索（www.sogou.com）比微信搜索反爬宽松，但频率限制严，间隔需 10-15 秒。
"""

import requests
import time
import random
import re
from bs4 import BeautifulSoup
from urllib.parse import quote
from datetime import datetime
from config import get_source_credibility

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# ============================================
# 优质公众号白名单（优先监控，召回其 AI 相关文章）
# 用户可在此增删
# ============================================
QUALITY_ACCOUNTS = [
    "DataWhale",
    "AI前线",
]

# 通用 AI 关键词（兜底，覆盖非白名单优质内容）
WECHAT_QUERIES = [
    "AI 产品经理",
    "AI 导购",
    "AI 电商",
    "AI 评测",
    "AI 应用案例",
    "AI Agent",
    "AI 智能体",
    "AI 大模型",
    "AI 工具",
    "AI 行业趋势",
]

SEARCH_TAKE = 5
SEARCH_DELAY_MIN = 10
SEARCH_DELAY_MAX = 15


def _search_sogou_web(query):
    """搜狗网页搜索，提取微信文章链接"""
    results = []
    url = f"https://www.sogou.com/web?query={quote(query)}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200 or "antispider" in resp.url:
        return results

    soup = BeautifulSoup(resp.text, "lxml")
    # 找所有包含微信链接的 a 标签
    seen = set()
    for a in soup.select('a[href*="mp.weixin.qq.com"]'):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or len(title) < 5:
            continue
        # 去重
        key = title[:40]
        if key in seen:
            continue
        seen.add(key)

        # 尝试找摘要（父级元素中的描述文本）
        parent = a.find_parent("div") or a.find_parent("p")
        summary = ""
        if parent:
            summary_el = parent.find("p") or parent.find("span")
            if summary_el:
                summary = summary_el.get_text(strip=True)[:200]

        results.append({
            "title": title,
            "url": href,
            "summary": summary,
            "source": "微信公众号",
            "date": "",
        })

        if len(results) >= SEARCH_TAKE:
            break

    # 清洗标题：去掉"公众号http://..."等杂质
    cleaned = []
    for r in results:
        title = r["title"]
        # 去掉 URL 前缀
        import re
        title = re.sub(r'https?://\S+', '', title)
        title = re.sub(r'公众号\s*', '', title)
        title = title.strip()
        if title and len(title) > 5:
            r["title"] = title
            cleaned.append(r)
    return cleaned


def _collect_one(query, seen_titles, tier, weight, source_prefix):
    """按单个搜索词采集，返回文章列表"""
    articles = []
    try:
        results = _search_sogou_web(query)
    except Exception:
        results = []

    for r in results:
        title = r["title"]
        title_key = title[:40]
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        summary = r["summary"]
        if summary and len(summary) > 10:
            summary = f"[微信搜索: {query}] {summary[:200]}"
        else:
            summary = f"[微信搜索: {query}] {title}"

        article_url = r.get("url", "") or ""
        if article_url.startswith("/"):
            article_url = "https://weixin.sogou.com" + article_url
        if not article_url:
            article_url = f"wechat://{title[:40]}"

        articles.append({
            "title": title,
            "url": article_url,
            "summary": summary,
            "published": r.get("date", "") or datetime.now().strftime("%Y-%m-%d"),
            "source_name": source_prefix,
            "source_type": "wechat",
            "credibility_tier": tier,
            "credibility_weight": weight,
        })

    time.sleep(random.uniform(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX))
    return articles


def collect_wechat():
    """白名单公众号优先 + 通用关键词兜底，去重后返回"""
    seen_titles = set()
    tier, weight = get_source_credibility("微信公众号")
    all_articles = []

    # 1. 优先搜优质公众号（召回其 AI 相关文章）
    print("  📱 [优质公众号] 采集中...", flush=True)
    for name in QUALITY_ACCOUNTS:
        articles = _collect_one(f"{name} AI", seen_titles, tier, weight, f"微信: {name}")
        all_articles.extend(articles)
    print(f"    ✅ 优质公众号 {len(QUALITY_ACCOUNTS)} 个号已搜")

    # 2. 通用 AI 关键词兜底
    print("  📱 [通用关键词] 采集中...", flush=True)
    for i, query in enumerate(WECHAT_QUERIES):
        articles = _collect_one(query, seen_titles, tier, weight, "微信公众号")
        all_articles.extend(articles)
        if (i + 1) % 5 == 0:
            print(f"    {i+1}/{len(WECHAT_QUERIES)} ...", flush=True)
    print(f"    ✅ 通用关键词完成")

    return all_articles


if __name__ == "__main__":
    articles = collect_wechat()
    print(f"\n共 {len(articles)} 条")
    for a in articles[:10]:
        print(f"  [{a['source_name']}] {a['title'][:55]}")