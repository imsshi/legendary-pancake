"""
AI 情报采集 Bot — 主程序

用法:
  python main.py           # 完整运行
  python main.py --test    # 测试（只采集）
"""

import sys
import time
from datetime import datetime

from collectors import collect_all
from processor import process_articles, generate_report
from reporter import send_weekly_report, send_simple_message
from storage import save_articles
from config import load_config


def main():
    print("=" * 55)
    print("🤖  AI 情报采集 Bot v3")
    print(f"⏰  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    if not load_config():
        return

    test_mode = "--test" in sys.argv
    if test_mode:
        print("🧪 测试模式")

    start_time = time.time()

    try:
        # 1. 采集
        articles = collect_all()
        if not articles:
            print("\n⚠️  未采集到内容")
            send_simple_message("⚠️ AI 情报 Bot: 未采集到内容")
            return

        if test_mode:
            print(f"\n共 {len(articles)} 篇，前 8 条:")
            for a in articles[:8]:
                tier = a.get("credibility_tier", "?")
                print(f"  [{a['source_name']}] (T{tier[-1] if tier else '?'}) {a['title'][:60]}")
            return

        # 2. AI 处理
        processed, total_before = process_articles(articles)
        if not processed:
            print("\n⚠️  无高质量文章")
            send_simple_message("⚠️ AI 情报 Bot: 本周无高质量内容")
            return

        # 3. 生成周报
        report = generate_report(processed, total_before)

        # 4. 推送飞书
        success = send_weekly_report(report)

        # 5. 存库（供 DewuClaw @bot 答疑）
        save_articles(processed)

        elapsed = time.time() - start_time
        print(f"\n{'='*55}")
        print(f"🎉 完成！{elapsed:.1f}s")
        if success:
            print("📱 去飞书群查看周报 →")
        print(f"{'='*55}")

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ 出错 ({elapsed:.1f}s): {e}")
        send_simple_message(f"❌ AI 情报 Bot 异常: {e}")
        raise


if __name__ == "__main__":
    main()
