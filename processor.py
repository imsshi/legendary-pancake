"""
AI 处理模块 — v4: 模块边界清晰化 + 三字段输出 + 差异化条目数

5 个模块，各有明确范围界定：
  🧠 大模型动态（发布/更新/评测）— 模型发布、迭代、评测方法、视频/语音/多模态
  🛠️ AI工具与产品（热议工具/功能更新/开源项目）— 不限新发布，含 GitHub Trending
  💼 AI应用落地（行业案例/实际部署）— 聚焦可量化案例，投融资≤20%篇幅
  🔬 前沿技术（Agent/工程策略/新架构）— 工程可复现，白话解释优先
  🎙️ KOL洞察（专家观点/趋势判断）— 实质观点，不收录转发/闲聊
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from openai import OpenAI
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MIN_SCORE, MAX_WORKERS,
    CROSS_VALIDATION_SIMILARITY, CROSS_VALIDATION_MIN_SOURCES,
    CROSS_VALIDATED_WEIGHT, CREDIBILITY_WEIGHTS, get_source_credibility,
)

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

# ============================================
# 文章处理 Prompt — v4 模块边界清晰化
# ============================================
ARTICLE_PROCESS_PROMPT = """你是 AI 行业情报分析师。读者是互联网公司业务团队。

请分析以下文章，用通俗易懂的方式呈现。

文章标题: {title}
文章摘要: {summary}
来源: {source}（可信度: {credibility}）

1. 分类（按模块边界）：
   - 🧠 大模型动态（发布/更新/评测）：新模型发布须标注核心特点；现有模型迭代须标注新增特性；评测方法与基准；视频/语音/多模态模型
   - 🛠️ AI工具与产品（热议工具/功能更新/开源项目）：不限新发布，近期热议或有功能更新的产品均可；GitHub Trending 项目；少数派等平台推荐
   - 💼 AI应用落地（行业案例/实际部署）：垂直行业 AI 落地案例，优先有具体数据（如点击率提升X%、成本降低Y%）；企业合作/投融资类降分处理，不占主要篇幅
   - 🔬 前沿技术（Agent/工程策略/新架构）：Agent 工程实现技术；新架构/训练方法；先白话解释策略→再展开细节；不收录纯理论论文
   - 🎙️ KOL洞察（专家观点/趋势判断）：专家对行业方向的判断；产品分析方法论；须有实质观点，纯转发/闲聊降分
   - 📌 其他

2. 四维评分（各 1-5）：
   - credibility(可信度) / freshness(时新性) / applicability(应用性) / insight(启发性)
   combined = round(credibility×0.25 + freshness×0.15 + applicability×0.35 + insight×0.25)

3. 「核心特点」：模型类标注核心特点（如"支持视频理解"）；工具类标注核心功能（如"AI生成PPT"）；更新类标注新增了什么（如"新增Agent模式"）。20字以内。不适用写"无"。

4. 「一句话」：大白话概括，30字以内。

5. 「通俗解读」：2-3句通俗解释，80字以内。杜绝术语堆砌。

6. 「应用启示」：对业务/工作的具体启发。有可借鉴的思路或方法就具体说；没有写"暂无"。

7. 关键词 1-3 个，相关工具/项目名（空数组如无）

JSON:
{{"title_cn":"","category":"🧠 大模型动态（发布/更新/评测）","scores":{{"credibility":4,"freshness":3,"applicability":4,"insight":3}},"overall_score":7,"core_feature":"核心特点或新功能","one_liner":"大白话","explain_simple":"通俗解读","application":"应用启示","keywords":[],"related_tools":[]}}

低质内容：overall_score≤3，explain_simple 写"低质内容"。"""

# ============================================
# 周报 Prompt — v4 三字段格式 + 差异化条目数
# ============================================
REPORT_PROMPT = """你是 AI 行业周报编辑。读者是互联网公司业务团队（非技术背景居多）。

用通俗语言编写周报。每条信息输出三字段：标题 + 通俗解读 + 应用启示。

情报列表：
{articles_json}

要求：

1. 「🔥 本周必读」：5~8 条最重要的。每条含 title(标题)、explain_simple(通俗解读)、application(应用启示)、url、source。

2. 「📂 分类详情」：按以下差异化条目数：
   - 🧠 大模型动态（发布/更新/评测）：5~8 条
   - 🛠️ AI工具与产品（热议工具/功能更新/开源项目）：5~8 条
   - 💼 AI应用落地（行业案例/实际部署）：3~5 条（降低占比，优先有数据案例）
   - 🔬 前沿技术（Agent/工程策略/新架构）：3~5 条
   - 🎙️ KOL洞察（专家观点/趋势判断）：3~5 条
   每条含 title、explain_simple、application、url、source。

3. 「💡 应用启示」：3~5 条对业务/工作的具体启发。每条 insight(可以做什么) + why(为什么现在值得关注)。

4. 「🛠️ 值得关注」：AI 工具/项目。name + description + url。

JSON:
{{
  "top_picks": [{{"title":"","explain_simple":"","application":"","url":"","source":""}}],
  "sections": [{{"category":"🧠 大模型动态（发布/更新/评测）","items":[{{"title":"","explain_simple":"","application":"","url":"","source":""}}]}}],
  "application_insights": [{{"insight":"","why":""}}],
  "recommended_tools": [{{"name":"","description":"","url":""}}],
  "stats": {{}}
}}
"""


# ============================================
# 去重 + 交叉验证（保持 v3 逻辑）
# ============================================
def deduplicate(articles):
    seen_urls = set()
    seen_titles = []
    result = []
    for a in articles:
        url = a.get("url", "")
        title = a.get("title", "")
        if not url or not title:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        title_set = set(title)
        is_dup = False
        for st in seen_titles:
            st_set = set(st)
            if not title_set or not st_set:
                continue
            if len(title_set & st_set) / len(title_set | st_set) > 0.8:
                is_dup = True
                break
        if not is_dup:
            seen_titles.append(title)
            result.append(a)
    return result


def cross_validate(articles):
    n = len(articles)
    clusters = []
    for i in range(n):
        found = False
        ti = set(articles[i].get("title", ""))
        if not ti:
            continue
        for cluster_indices, cluster_sources in clusters:
            for j in cluster_indices:
                tj = set(articles[j].get("title", ""))
                if not tj:
                    continue
                sim = len(ti & tj) / len(ti | tj) if (ti | tj) else 0
                if sim > CROSS_VALIDATION_SIMILARITY:
                    cluster_indices.append(i)
                    cluster_sources.add(articles[i].get("source_name", ""))
                    found = True
                    break
            if found:
                break
        if not found:
            clusters.append(([i], {articles[i].get("source_name", "")}))
    validated_count = 0
    for indices, sources in clusters:
        if len(sources) >= CROSS_VALIDATION_MIN_SOURCES:
            for i in indices:
                articles[i]["cross_validated"] = True
                articles[i]["cross_sources"] = list(sources)
                if articles[i].get("credibility_tier") == "T4":
                    articles[i]["credibility_weight"] = CROSS_VALIDATED_WEIGHT
                validated_count += 1
        else:
            for i in indices:
                articles[i]["cross_validated"] = False
                articles[i]["cross_sources"] = []
    print(f"交叉验证: {len(clusters)} 个事件簇, {validated_count} 条被多源验证")
    return articles


def _process_single_article(article, retries=3):
    tier = article.get("credibility_tier", "T4")
    cv = "已验证" if article.get("cross_validated") else "单源"
    prompt = ARTICLE_PROCESS_PROMPT.format(
        title=article.get("title", ""),
        summary=article.get("summary", ""),
        source=article.get("source_name", ""),
        credibility=f"{tier} ({cv})",
    )
    defaults = {
        "title_cn": article.get("title", ""),
        "category": "📌 其他",
        "scores": {"credibility": 3, "freshness": 3, "applicability": 3, "insight": 3},
        "overall_score": 5, "core_feature": "", "one_liner": "",
        "explain_simple": article.get("summary", "")[:80], "application": "",
        "keywords": [], "related_tools": [],
    }
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": "你是AI情报分析师。返回合法JSON。"}, {"role": "user", "content": prompt}],
                temperature=0.3, response_format={"type": "json_object"}, max_tokens=900,
            )
            result = json.loads(response.choices[0].message.content)
            for k in ["title_cn", "category", "core_feature", "one_liner", "explain_simple", "application"]:
                article[k] = result.get(k, defaults[k])
            article["scores"] = result.get("scores", defaults["scores"])
            article["overall_score"] = int(result.get("overall_score", defaults["overall_score"]))
            article["keywords"] = result.get("keywords", defaults["keywords"])
            article["related_tools"] = result.get("related_tools", defaults["related_tools"])
            return article
        except (json.JSONDecodeError, Exception):
            if attempt < retries - 1:
                time.sleep(1)
                continue
    for k, v in defaults.items():
        article[k] = v
    return article


def process_articles(articles):
    print(f"\n🧹 ===== 去重 =====")
    before = len(articles)
    articles = deduplicate(articles)
    after_dedup = len(articles)
    print(f"{before} → {after_dedup}")
    for a in articles:
        if "credibility_tier" not in a:
            tier, weight = get_source_credibility(a.get("source_name", ""))
            a["credibility_tier"] = tier
            a["credibility_weight"] = weight
    print(f"\n🔗 ===== 交叉验证 =====")
    articles = cross_validate(articles)
    print(f"\n🤖 ===== AI 处理 ({len(articles)} 条) =====")
    processed = []
    total = len(articles)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(_process_single_article, a): i for i, a in enumerate(articles)}
        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                processed.append(future.result())
            except Exception as e:
                a = articles[idx]
                for k, v in {"title_cn": a.get("title",""), "category": "📌 其他", "overall_score": 5, "core_feature": "", "one_liner": "", "explain_simple": "", "application": "", "keywords": [], "related_tools": [], "scores": {"credibility":3,"freshness":3,"applicability":3,"insight":3}}.items():
                    a[k] = v
                processed.append(a)
            if len(processed) % 10 == 0 or len(processed) == total:
                print(f"  {len(processed)}/{total}")
    processed.sort(key=lambda x: x.get("overall_score", 0), reverse=True)
    before_f = len(processed)
    high = [a for a in processed if a.get("overall_score", 0) >= MIN_SCORE]
    print(f"\n📊 过滤: {before_f} → {len(high)} (综合分≥{MIN_SCORE})")
    return high, after_dedup


def generate_report(articles, total_before_filter=0):
    if not articles:
        print("⚠️  无高质量文章")
        return {"top_picks": [], "sections": [], "application_insights": [], "recommended_tools": [], "stats": {"total_collected": total_before_filter, "after_filter": 0, "categories": {}}}
    print(f"\n📝 ===== 生成周报 =====")
    simplified = []
    for a in articles[:60]:
        simplified.append({
            "title_cn": a.get("title_cn", ""), "core_feature": a.get("core_feature", ""),
            "one_liner": a.get("one_liner", ""), "explain_simple": a.get("explain_simple", ""),
            "application": a.get("application", ""), "category": a.get("category", ""),
            "overall_score": a.get("overall_score", 0), "url": a.get("url", ""),
            "source": a.get("source_name", ""), "related_tools": a.get("related_tools", []),
            "cross_validated": a.get("cross_validated", False),
        })
    articles_json = json.dumps(simplified, ensure_ascii=False, indent=2)
    prompt = REPORT_PROMPT.format(articles_json=articles_json)
    cat_counter = Counter(a.get("category", "📌 其他") for a in articles)
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": "你是AI周报编辑。返回合法JSON。"}, {"role": "user", "content": prompt}],
                temperature=0.5, response_format={"type": "json_object"}, max_tokens=6000,
            )
            report = json.loads(response.choices[0].message.content)
            report["stats"]["total_collected"] = total_before_filter
            report["stats"]["after_filter"] = len(articles)
            report["stats"]["categories"] = dict(cat_counter)
            print("✅ 周报生成完成")
            return report
        except (json.JSONDecodeError, Exception):
            if attempt < 2:
                time.sleep(1)
                continue
    print("  ❌ 生成失败")
    return {"top_picks": [], "sections": [], "application_insights": [], "recommended_tools": [], "stats": {"total_collected": total_before_filter, "after_filter": len(articles), "categories": dict(cat_counter)}}