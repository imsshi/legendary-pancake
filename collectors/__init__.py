"""
采集器整合模块 — 统一调用所有采集源
"""

from .rss_collector import collect_rss
from .web_collector import collect_web
from .twitter_collector import collect_twitter
from .trending_collector import collect_trending
from .wechat_collector import collect_wechat


def collect_all():
    """
    采集所有来源，返回统一的文章列表

    执行顺序：榜单 → RSS → 网页 → Twitter
    每个采集器独立运行，出错不影响其他

    Returns:
        list[dict]: 统一格式 [{title, url, summary, published, source_name, source_type}]
    """
    all_articles = []

    # 0. 榜单源（热度排序的高信号内容，优先级最高）
    print("\n🔥 ===== 第0步：榜单采集 =====")
    try:
        trending_articles = collect_trending()
        all_articles.extend(trending_articles)
        print(f"🔥 榜单采集完成: {len(trending_articles)} 条高热度内容")
    except Exception as e:
        print(f"❌ 榜单采集失败: {e}")

    # 1. RSS 源（最快，覆盖面广）
    print("\n📡 ===== 第1步：RSS 采集 =====")
    try:
        rss_articles = collect_rss()
        all_articles.extend(rss_articles)
        print(f"📡 RSS 采集完成: {len(rss_articles)} 篇")
    except Exception as e:
        print(f"❌ RSS 采集失败: {e}")

    # 2. 网页爬虫（补充没有 RSS 的网站）
    print("\n🌐 ===== 第2步：网页采集 =====")
    try:
        web_articles = collect_web()
        all_articles.extend(web_articles)
        print(f"🌐 网页采集完成: {len(web_articles)} 篇")
    except Exception as e:
        print(f"❌ 网页采集失败: {e}")

    # 3. Twitter KOL（API 优先，无 API key 时静默跳过）
    print("\n🐦 ===== 第3步：Twitter 采集 =====")
    try:
        twitter_articles = collect_twitter()
        all_articles.extend(twitter_articles)
        print(f"🐦 Twitter 采集完成: {len(twitter_articles)} 篇")
    except Exception as e:
        print(f"🐦 Twitter 采集跳过: {e}")

    # 4. 微信公众号（搜狗搜索通用 AI 主题）
    print("\n📱 ===== 第4步：微信公众号采集 =====")
    try:
        wechat_articles = collect_wechat()
        all_articles.extend(wechat_articles)
        print(f"📱 微信公众号采集完成: {len(wechat_articles)} 条")
    except Exception as e:
        print(f"📱 微信公众号采集跳过: {e}")

    print(f"\n{'='*50}")
    print(f"✅ 全部采集完成，共 {len(all_articles)} 条原始内容")
    print(f"{'='*50}")

    return all_articles