"""
Twitter/X 采集器 — v4: API 优先方案

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
    """方案B: Playwright 兜底"""
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
            page.goto(f"https://twitter.com/{username}", timeout=30000)
            page.wait_for_selector('article[data-testid="tweet"]', timeout=15000)
            for _ in range(2):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)
            tweet_els = page.query_selector_all('article[data-testid="tweet"]')
            for el in tweet_els[:15]:
                try:
                    text_el = el.query_selector('div[data-testid="tweetText"]')
                    text = text_el.inner_text() if text_el else ""
                    if not text.strip() or text.strip().startswith("@"):
                        continue
                    time_el = el.query_selector("time")
                    created_at = time_el.get_attribute("datetime") if time_el else ""
                    link_el = el.query_selector('a[href*="/status/"]')
                    link = f"https://twitter.com{link_el.get_attribute('href')}" if link_el else ""
                    tweets.append({
                        "title": text.strip()[:120], "text": text.strip(),
                        "url": link, "created_at": created_at,
                        "source_name": f"Twitter @{username}", "source_type": "twitter",
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