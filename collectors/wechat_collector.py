"""
微信公众号采集器 — Playwright 渲染搜狗微信搜索

通过搜狗微信搜索自动检索 AI 相关关键词，提取标题和摘要。

搜狗有 IP 级反爬：同一 IP 连续请求会触发图片验证码。
缓解措施：代理支持（WECHAT_PROXY 环境变量）+ 长间隔随机延迟。
本机 IP 若被标记，需换 IP（GitHub Actions / 代理）才能验证。
"""

import os
import time
import random
from urllib.parse import quote
from datetime import datetime
from config import get_source_credibility

# 搜索关键词（通用 AI 主题，覆盖所有关注领域）
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
# 每次搜索间隔（秒），降低触发反爬概率
SEARCH_DELAY_MIN = 8
SEARCH_DELAY_MAX = 15

# 代理配置（可选，用于换 IP 绕过反爬）
WECHAT_PROXY = os.getenv("WECHAT_PROXY", "")


def _launch_browser(p):
    """启动 Playwright 浏览器，支持代理"""
    launch_kwargs = {"headless": True}
    if WECHAT_PROXY:
        launch_kwargs["proxy"] = {"server": WECHAT_PROXY}
    return p.chromium.launch(**launch_kwargs)


def _search_sogou(query, browser):
    """Playwright 渲染搜狗搜索页面，返回文章列表"""
    results = []
    try:
        page = browser.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})
        url = f"https://weixin.sogou.com/weixin?type=2&query={quote(query)}"
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # 搜狗可能拦截，检查是否跳转 antispider
        if "antispider" in page.url:
            page.close()
            return results

        items = page.query_selector_all(".news-box .news-list li")
        for item in items[:SEARCH_TAKE]:
            title_el = item.query_selector(".txt-box h3 a")
            if not title_el:
                continue
            title = title_el.inner_text().strip()
            if not title:
                continue
            summary_el = item.query_selector(".txt-box .txt-info")
            source_el = item.query_selector(".txt-box .s-p .account")
            date_el = item.query_selector(".txt-box .s-p .s2")
            results.append({
                "title": title,
                "summary": summary_el.inner_text().strip() if summary_el else "",
                "source": source_el.inner_text().strip() if source_el else "",
                "date": date_el.inner_text().strip() if date_el else "",
            })
        page.close()
    except Exception:
        pass
    return results


def collect_wechat():
    """Playwright 渲染搜狗微信搜索，自动检索关键词，去重后返回"""
    all_articles = []
    seen_titles = set()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return all_articles

    tier, weight = get_source_credibility("微信公众号")

    try:
        with sync_playwright() as p:
            browser = _launch_browser(p)
            for i, query in enumerate(WECHAT_QUERIES):
                results = _search_sogou(query, browser)
                for r in results:
                    title = r["title"]
                    title_key = title[:40]
                    if title_key in seen_titles:
                        continue
                    seen_titles.add(title_key)

                    source_name = f"微信: {r['source']}" if r["source"] else "微信公众号"
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
                        "source_name": source_name,
                        "source_type": "wechat",
                        "credibility_tier": tier,
                        "credibility_weight": weight,
                    })

                if (i + 1) % 5 == 0:
                    print(f"    已搜索 {i+1}/{len(WECHAT_QUERIES)} ...", flush=True)

                # 长间隔随机延迟，降低反爬触发
                if i < len(WECHAT_QUERIES) - 1:
                    delay = random.uniform(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX)
                    time.sleep(delay)

            browser.close()
    except Exception as e:
        print(f"    ⚠️ 微信采集异常: {e}")

    return all_articles


if __name__ == "__main__":
    articles = collect_wechat()
    print(f"\n共 {len(articles)} 条")
    for a in articles[:10]:
        print(f"  [{a['source_name'][:15]}] {a['title'][:55]}")