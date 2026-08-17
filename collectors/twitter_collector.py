"""
Twitter/X 采集器 — v5: 适配 X.com 新 DOM 结构

用法:
  1. 设置环境变量 RAPIDAPI_KEY 或 TWITTER_API_KEY（第三方 API）
  2. 自动降级: API → Playwright → 跳过

KOL 列表: 17 个产品管理 + AI 领域专家
"""

import os
import time
from datetime import datetime, timedelta
from config import COLLECT_DAYS, RSSHUB_BASE, TWITTER_USERNAME, TWITTER_PASSWORD

KOLS = [
    # 产品管理
    "shreyas", "lennysan", "wes_kao",
    # AI 领军
    "sama", "ylecun", "AndrewYNg", "DrJimFan",
    # AI 工程
    "swyx", "chipro", "_akhaliq",
    # AI 产品/工具
    "minchoi", "heyBarsee", "rowancheung", "rachel_l_woods",
    "saranormous", "alexalbert__", "ai_sources",
]

# 第三方 API 配置
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "twitter-api47.p.rapidapi.com")


def _try_rapidapi(username):
    """方案A: 通过 RapidAPI 第三方接口获取推文"""
    if not RAPIDAPI_KEY:
        return None
    try:
        import requests
        resp = requests.get(
            f"https://{RAPIDAPI_HOST}/v2/user/tweets",
            headers={"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST},
            params={"username": username, "count": 20},
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        tweets_raw = data.get("tweets") or data.get("data") or []
        tweets = []
        cutoff = datetime.now() - timedelta(days=COLLECT_DAYS)
        for t in tweets_raw:
            text = t.get("text", "") or t.get("full_text", "")
            if not text.strip() or text.strip().startswith("@"):
                continue
            created = t.get("created_at", "") or t.get("createdAt", "")
            tweets.append({
                "title": text.strip()[:120], "text": text.strip(),
                "url": f"https://twitter.com/{username}/status/{t.get('id', '')}",
                "created_at": created, "source_name": f"Twitter @{username}",
                "source_type": "twitter",
            })
        return tweets if tweets else None
    except Exception:
        return None


def _try_playwright(username):
    """方案B: Playwright 兜底 — 适配 X.com 新 DOM（meta itemprop 结构）"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    tweets = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_viewport_size({"width": 1920, "height": 1080})
            page.goto(f"https://x.com/{username}", timeout=30000)
            page.wait_for_timeout(3000)  # 等 JS 渲染

            # 滚动加载更多
            for _ in range(2):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)

            # v5: X.com 新结构 — 用 <article> 里的 meta itemprop 提取
            article_els = page.query_selector_all("article")
            cutoff = datetime.now() - timedelta(days=COLLECT_DAYS)

            for article in article_els[:15]:
                try:
                    # 提取 meta 标签
                    meta_text = article.query_selector('meta[itemprop="text"]')
                    text = meta_text.get_attribute("content") if meta_text else ""

                    meta_id = article.query_selector('meta[itemprop="identifier"]')
                    tweet_id = meta_id.get_attribute("content") if meta_id else ""

                    meta_time = article.query_selector('meta[itemprop="dateCreated"]')
                    created_at = meta_time.get_attribute("content") if meta_time else ""

                    meta_url = article.query_selector('meta[itemprop="url"]')
                    url = meta_url.get_attribute("content") if meta_url else ""

                    # 提取作者信息：只取本账号的推文，跳过转推
                    author_section = article.query_selector('[itemprop="author"]')
                    if author_section:
                        author_username = author_section.query_selector('meta[itemprop="alternateName"]')
                        if author_username:
                            author = author_username.get_attribute("content") or ""
                            if author.lower() != username.lower():
                                continue  # 跳过转推/其他人的推文

                    if not text.strip() or text.strip().startswith("@"):
                        continue

                    # 检查时间是否在范围内
                    if created_at:
                        try:
                            pub_date = datetime.fromisoformat(created_at.replace("Z", "+00:00").replace("+00:00", ""))
                            if pub_date.replace(tzinfo=None) < cutoff:
                                continue
                        except (ValueError, TypeError):
                            pass

                    tweets.append({
                        "title": text.strip()[:120],
                        "text": text.strip(),
                        "url": url or f"https://x.com/{username}/status/{tweet_id}",
                        "created_at": created_at,
                        "source_name": f"Twitter @{username}",
                        "source_type": "twitter",
                    })
                except Exception:
                    continue

            browser.close()
    except Exception:
        pass

    return tweets


def collect_twitter():
    """采集 KOL 推文: API 优先 → Playwright 兜底"""
    all_tweets = []
    for i, username in enumerate(KOLS):
        print(f"  🐦 [{i+1}/{len(KOLS)}] @{username} ...", flush=True)

        tweets = _try_rapidapi(username)
        if tweets:
            print(f"    ✅ API → {len(tweets)} 条")
            all_tweets.extend(tweets)
            continue

        tweets = _try_playwright(username)
        if tweets:
            print(f"    ✅ Playwright → {len(tweets)} 条")
            all_tweets.extend(tweets)
            continue

        print(f"    ⚠️  跳过")
    return all_tweets