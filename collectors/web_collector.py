"""
网页采集器 — 爬取没有 RSS 的网站

所有采集自动附带信源可信度信息
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from config import REQUEST_TIMEOUT, get_source_credibility

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

WEB_SOURCES = [
    # 国内
    {"name": "36氪 AI", "url": "https://36kr.com/information/AI/"},
    {"name": "机器之心 AI", "url": "https://www.jiqizhixin.com/"},
    # 海外官方 — 网页采集
    {"name": "Anthropic Blog", "url": "https://www.anthropic.com/research"},
    {"name": "Stability AI Blog", "url": "https://stability.ai/news"},
    # AI 工具发现
    {"name": "GitHub Trending", "url": "https://github.com/trending?since=weekly"},
    {"name": "Product Hunt", "url": "https://www.producthunt.com/"},
]


def _fetch_page(url):
    """获取网页 HTML"""
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return resp.text


def _extract_date(container):
    """尝试从容器中提取时间"""
    time_tag = container.find("time")
    if time_tag and time_tag.get("datetime"):
        return time_tag["datetime"]
    return datetime.now().strftime("%Y-%m-%d")


def _extract_articles(html, source_name, source_url):
    """
    从 HTML 提取文章列表

    修复：source_url 参数用于正确的相对路径拼接
    策略：优先找 article/section 容器 → 兜底找长文本 a 标签
    """
    soup = BeautifulSoup(html, "lxml")
    articles = []
    seen_urls = set()

    # 策略1：找常见内容容器
    for container_tag in ["article", "section", "li", "div"]:
        for container in soup.find_all(container_tag):
            link = container.find("a", href=True)
            title_tag = container.find(["h1", "h2", "h3", "h4"])

            if not link:
                continue

            title = title_tag.get_text(strip=True) if title_tag else link.get_text(strip=True)
            if len(title) < 15:
                continue

            url = link["href"]
            if url.startswith("/"):
                url = urljoin(source_url, url)

            if url in seen_urls:
                continue
            seen_urls.add(url)

            # 尝试提取摘要
            summary_tag = container.find(["p", "span", "div"], class_=lambda c: c and any(
                kw in str(c).lower() for kw in ["desc", "summary", "excerpt", "abstract", "tagline"]
            ))
            summary = summary_tag.get_text(strip=True)[:200] if summary_tag else ""

            articles.append({
                "title": title,
                "url": url,
                "summary": summary,
                "published": _extract_date(container),
                "source_name": source_name,
                "source_type": "web",
            })

            if len(articles) >= 20:
                break

        if articles:
            break

    # 策略2（兜底）：找长文本 a 标签
    if not articles:
        for a_tag in soup.find_all("a", href=True):
            title = a_tag.get_text(strip=True)
            if len(title) < 15:
                continue
            url = a_tag["href"]
            if url.startswith("/"):
                url = urljoin(source_url, url)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            articles.append({
                "title": title,
                "url": url,
                "summary": "",
                "published": datetime.now().strftime("%Y-%m-%d"),
                "source_name": source_name,
                "source_type": "web",
            })
            if len(articles) >= 20:
                break

    return articles


def collect_web():
    """采集所有网页源"""
    all_articles = []

    for source in WEB_SOURCES:
        name = source["name"]
        url = source["url"]
        tier, weight = get_source_credibility(name)
        try:
            print(f"  🌐 [{name}] 采集中...", flush=True)
            html = _fetch_page(url)
            articles = _extract_articles(html, name, url)
            # 注入信源可信度
            for a in articles:
                a["credibility_tier"] = tier
                a["credibility_weight"] = weight
            print(f"  ✅ [{name}] {len(articles)} 篇")
            all_articles.extend(articles)
        except Exception as e:
            print(f"  ❌ [{name}] {e}")

    return all_articles


if __name__ == "__main__":
    articles = collect_web()
    print(f"\n共 {len(articles)} 篇")
    for a in articles[:5]:
        print(f"  [{a['source_name']}] {a['title'][:50]}")
