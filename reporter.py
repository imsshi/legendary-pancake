"""
飞书推送模块 — v4 结构化卡片

三字段布局：📎标题 + 💬通俗解读 + 💡应用启示
每个模块标题带范围括号
"""

import requests
from datetime import datetime, timedelta
from config import FEISHU_WEBHOOK, REQUEST_TIMEOUT

CATEGORY_MAP = {
    "🧠 大模型动态（发布/更新/评测）": "🧠",
    "🛠️ AI工具与产品（热议工具/功能更新/开源项目）": "🛠️",
    "💼 AI应用落地（行业案例/实际部署）": "💼",
    "🎙️ KOL洞察（专家观点/趋势判断）": "🎙️",
    "🔬 前沿技术（Agent/工程策略/新架构）": "🔬",
    "📌 其他": "📌",
}


def _strip_scope(cat_name):
    """去掉分类名中的范围括号，用于统计区"""
    for full in CATEGORY_MAP:
        if cat_name.startswith(full.split("（")[0]):
            return full.split("（")[0]
    return cat_name


def _build_item_block(title, url, explain_simple, application, source=""):
    """构建一条信息的三字段块"""
    lines = []
    linked = f"[{title}]({url})" if url else f"**{title}**"
    lines.append(f"📎 {linked}")
    if source:
        lines.append(f"   _来源: {source}_")
    if explain_simple:
        lines.append(f"💬 {explain_simple[:80]}")
    if application and application != "暂无":
        lines.append(f"💡 {application[:80]}")
    return "\n".join(lines)


def build_card(report, date_start, date_end):
    elements = []

    # ===== 🔥 本周必读 =====
    top = report.get("top_picks", [])
    if top:
        lines = ["🔥 **本周必读**\n"]
        for i, item in enumerate(top[:8]):
            lines.append(f"**{i+1}.**")
            lines.append(_build_item_block(
                item.get("title", ""), item.get("url", ""),
                item.get("explain_simple", ""), item.get("application", ""),
                item.get("source", ""),
            ))
            lines.append("")
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}})
        elements.append({"tag": "hr"})

    # ===== 📂 分类详情 =====
    sections = report.get("sections", [])
    for section in sections:
        cat = section.get("category", "📌 其他")
        items = section.get("items", [])
        if not items:
            continue

        sec_lines = [f"**{cat}** ({len(items)}条)\n"]
        for item in items[:8]:
            sec_lines.append(_build_item_block(
                item.get("title", ""), item.get("url", ""),
                item.get("explain_simple", ""), item.get("application", ""),
                item.get("source", ""),
            ))
            sec_lines.append("")
        if len(items) > 8:
            sec_lines.append(f"_…还有 {len(items)-8} 条_")
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(sec_lines)}})

    # ===== 💡 应用启示 =====
    insights = report.get("application_insights", [])
    if insights:
        elements.append({"tag": "hr"})
        lines = ["💡 **应用启示**\n"]
        for i, ins in enumerate(insights[:5]):
            lines.append(f"**{i+1}.** {ins.get('insight', '')}")
            if ins.get("why"):
                lines.append(f"   → {ins['why']}")
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}})

    # ===== 🛠️ 值得关注 =====
    tools = report.get("recommended_tools", [])
    if tools:
        elements.append({"tag": "hr"})
        lines = ["🛠️ **值得关注**\n"]
        for t in tools[:5]:
            name = t.get("name", "")
            desc = t.get("description", "")
            url = t.get("url", "")
            if url:
                lines.append(f"• **[{name}]({url})** — {desc}" if desc else f"• **[{name}]({url})**")
            else:
                lines.append(f"• **{name}** — {desc}" if desc else f"• **{name}**")
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}})

    # ===== 📊 统计 =====
    elements.append({"tag": "hr"})
    stats = report.get("stats", {})
    total = stats.get("total_collected", 0)
    filtered = stats.get("after_filter", 0)
    categories = stats.get("categories", {})
    stats_md = f"📊 采集 **{total}** 条 → 精选 **{filtered}** 条\n"
    if categories:
        parts = []
        for k, v in categories.items():
            emoji = CATEGORY_MAP.get(k, "📌")
            name = _strip_scope(k)
            parts.append(f"{emoji} {name}: {v}条")
        stats_md += " | ".join(parts)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": stats_md}})
    elements.append({"tag": "note", "elements": [{"tag": "plain_text", "content": f"周期: {date_start}~{date_end} | 🤖 AI 情报 Bot"}]})

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"📰 AI 情报周报 | {date_start} ~ {date_end}"},
                "template": "indigo",
            },
            "elements": elements,
        },
    }


def send_weekly_report(report):
    if not FEISHU_WEBHOOK:
        print("❌ FEISHU_WEBHOOK 未配置")
        return False
    today = datetime.now()
    card = build_card(report, (today - timedelta(days=7)).strftime("%m/%d"), today.strftime("%m/%d"))
    try:
        resp = requests.post(FEISHU_WEBHOOK, json=card, headers={"Content-Type": "application/json"}, timeout=REQUEST_TIMEOUT)
        r = resp.json()
        ok = r.get("code") == 0 or r.get("StatusCode") == 0
        print("✅ 周报已发送" if ok else f"❌ {r}")
        return ok
    except Exception as e:
        print(f"❌ {e}")
        return False


def send_simple_message(text):
    if not FEISHU_WEBHOOK:
        return
    try:
        requests.post(FEISHU_WEBHOOK, json={"msg_type": "text", "content": {"text": text}}, timeout=REQUEST_TIMEOUT)
    except Exception:
        pass