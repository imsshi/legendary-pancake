"""
微信公众号采集器 — 搜狗网页搜索（requests + BeautifulSoup）

通过搜狗网页搜索（www.sogou.com）检索 AI 相关关键词，提取搜索结果中的微信文章。
搜狗网页搜索比微信搜索（weixin.sogou.com）反爬更宽松，requests 即可访问。
"""

import requests
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import quote
from datetime import datetime
from config import get_source_credibility

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

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
SEARCH_DELAY_MIN = 3
SEARCH_DELAY_MAX = 6


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


def collect_wechat():
    """搜狗网页搜索通用 AI 主题，提取微信文章，去重后返回"""
    all_articles = []
    seen_titles = set()

    tier, weight = get_source_credibility("微信公众号")

    for i, query in enumerate(WECHAT_QUERIES):
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

            all_articles.append({
                "title": title,
                "url": "",
                "summary": summary,
                "published": r.get("date", "") or datetime.now().strftime("%Y-%m-%d"),
                "source_name": "微信公众号",
                "source_type": "wechat",
                "credibility_tier": tier,
                "credibility_weight": weight,
            })

        if (i + 1) % 5 == 0:
            print(f"    已搜索 {i+1}/{len(WECHAT_QUERIES)} ...", flush=True)

        # 控制频率
        if i < len(WECHAT_QUERIES) - 1:
            time.sleep(random.uniform(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX))

    return all_articles


if __name__ == "__main__":
    articles = collect_wechat()
    print(f"\n共 {len(articles)} 条")
    for a in articles[:10]:
        print(f"  [{a['source_name']}] {a['title'][:55]}")