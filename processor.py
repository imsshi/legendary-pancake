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
    domain_signal,
)

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

# ============================================
# 类目归一化 — AI 可能返回短名/错 emoji，统一映射到标准全名
# ============================================
def normalize_category(cat):
    if not cat:
        return "📌 其他"
    # 三大类归一化。注意：命中顺序必须「特异性从高到低」——
    # 大类前缀「行业应用的案例 / AI模型技术突破」本身含「行业/应用/模型/技术」
    # 这些通用词，若先判它们，会把子类目互相吞并（实测：新工程方法全被模型吞走、
    # 企业提效全被行业吞走）。所以子类目关键词要排在通用词之前。
    if "非电商" in cat:
        return "🏭 AI在行业应用的案例 / 其他行业AI应用"
    if "电商" in cat:
        return "🏭 AI在行业应用的案例 / 电商行业AI应用"
    if "企业" in cat or "提效" in cat:
        return "🏭 AI在行业应用的案例 / 企业AI提效"
    if "行业" in cat or "应用" in cat or "落地" in cat:
        return "🏭 AI在行业应用的案例 / 其他行业AI应用"
    if "洞察" in cat or "KOL" in cat or "观点" in cat:
        return "🎙️ 专家观点与洞察"
    # 工程/前沿/工具/产品 必须先于「模型」判断：因为「AI模型技术突破」里也含「模型」，
    # 若先判「模型」，会把「新工程方法/热门工具」全部误吞成「新模型发布」
    if "工程" in cat or "前沿" in cat or "工具" in cat or "产品" in cat:
        return "🧠 AI模型技术突破 / 新工程方法"
    if "模型" in cat or "大模型" in cat:
        return "🧠 AI模型技术突破 / 新模型发布"
    if "技术" in cat:
        return "🧠 AI模型技术突破 / 新工程方法"
    return "📌 其他"

# ============================================
# 文章处理 Prompt — v4 模块边界清晰化
# ============================================
ARTICLE_PROCESS_PROMPT = """你是 AI 行业情报分析师。读者是互联网公司业务团队。

请分析以下文章，用通俗易懂的方式呈现。

文章标题: {title}
文章摘要: {summary}
来源: {source}（可信度: {credibility}）
领域命中: {domain_hint}

1. 分类（按三大类，子类目可选。先判断是否「应用落地」，再考虑技术）：
   🏭 AI在行业应用的案例（读者最关心，优先归入此类）：
     - 电商行业AI应用：电商/导购/营销/客服/选品/推荐/转化等场景的 AI 落地——含淘宝/京东/拼多多/抖音/小红书/Amazon 等平台的 AI 新功能与品牌 AI 营销案例
     - 其他行业AI应用：零售/金融/教育/医疗等非电商行业的 AI 落地案例
     - 企业AI提效：企业内部 AI 工具、自动化方案、AI 赋能办公/协作
     ⚠️ 若「领域命中」为强相关（电商/导购/营销/案例/落地/提效等），优先归入本大类，不要只因为提到「模型」就归技术类
   🎙️ 专家观点与洞察：AI 领域专家对行业方向的判断、产品方法论、趋势分析，须有实质观点
   🧠 AI模型技术突破（收窄，只留真·技术）：
     - 新模型发布/重大更新：仅 GPT/Claude/Gemini/DeepSeek/Qwen/豆包 等旗舰模型的新版本或重磅突破
     - 新工程方法/前沿技术：Agent 工程、新架构、训练方法等可复现的工程方法（热门 AI 工具/开源项目若更偏「落地/提效」请归入 🏭，纯技术才留这里）
   📌 其他：以上均不符合

2. 五维评分（各 1-10，先定级再给分，禁止堆中间值）：
   - credibility(可信度) / freshness(时新性) / applicability(应用性) / insight(启发性) / relevance(领域相关度)
   relevance 判定标准：对「AI产品经理、电商/导购、评测、应用落地、业务提效」的实际价值。
     纯技术论文/大模型架构细节/纯理论 → relevance=1~3
     有落地案例、产品方法、业务数据、可复用的工具 → relevance=7~10
   先给文章定级，再按级别打分，overall 分布要接近下面比例（一批约 40 条里）：
     - 9~10「重磅」约 10%：竞对平台 AI 大动作、旗舰模型发布、关键 KOL 趋势判断
     - 8「优质」约 18%：有明显落地价值或重要行业更新
     - 7「良好」约 25%：值得了解
     - 5~6「一般」约 30%：可看可不看
     - 3~4「低质/跑题」约 17%：纯理论、纯转发、与业务无关
   ⚠️ 严禁过半集中在 5~6 分；9~10 分必须给足约 10%，不能整批只给 1~2 条 9 分。
   combined = round(credibility×0.20 + freshness×0.10 + applicability×0.30 + insight×0.20 + relevance×0.20)
   五维分数要与 overall 级别自洽：定了「重磅」各维就给 8~10，定了「低质」就给 1~4。

3. 「核心特点」：模型类标注核心特点（如"支持视频理解"）；工具类标注核心功能（如"AI生成PPT"）；更新类标注新增了什么（如"新增Agent模式"）。20字以内。不适用写"无"。

4. 「一句话」：大白话概括，30字以内。

5. 「通俗解读」：2-3句通俗解释，80字以内。杜绝术语堆砌。

6. 「应用启示」：对业务/工作的具体启发。有可借鉴的思路或方法就具体说；没有写"暂无"。

7. 关键词 1-3 个，相关工具/项目名（空数组如无）

JSON:
{{"title_cn":"","category":"🏭 AI在行业应用的案例 / 电商行业AI应用","scores":{{"credibility":7,"freshness":6,"applicability":8,"insight":7,"relevance":8}},"overall_score":7,"core_feature":"核心特点或新功能","one_liner":"大白话","explain_simple":"通俗解读","application":"应用启示","keywords":[],"related_tools":[]}}

低质内容：overall_score≤3，explain_simple 写"低质内容"。"""

# ============================================
# 周报 Prompt — v4 三字段格式 + 差异化条目数
# ============================================
REPORT_PROMPT = """你是 AI 行业周报编辑。读者是互联网公司业务团队（非技术背景居多）。

用通俗语言编写周报。每条信息输出三字段：标题 + 通俗解读 + 应用启示。

情报列表：
{articles_json}

要求：

1. 「🔥 本周必读」：5~8 条最重要的。优先选「对产品经理和互联网行业最有影响力」的内容（竞对电商AI新动作、重大应用落地、热议工具、关键KOL趋势判断），而非纯技术研究。每条含 title(标题)、explain_simple(通俗解读)、application(应用启示)、url、source。

2. 「📂 分类详情」：按以下三大类组织，每个大类下分子类目：
   - 🏭 AI在行业应用的案例（电商行业/其他行业/企业提效）：10~15 条
     - 电商行业AI应用：5~8 条（核心，竞对平台的AI新动作）
     - 其他行业AI应用：3~5 条（非电商行业AI落地案例）
     - 企业AI提效：2~3 条（企业内部AI提效方案）
   - 🎙️ 专家观点与洞察：3~5 条（只留关键KOL的实质观点）
   - 🧠 AI模型技术突破（新模型/新工程方法）：3~5 条
     - 新模型发布/重大更新：1~2 条（只留最重磅）
     - 新工程方法/前沿技术/热议工具：2~3 条（可落地的工程方法或热议工具）
   每条含 title、explain_simple、application、url、source。

3. 「💡 应用启示」：3~5 条对业务/工作的具体启发。每条 insight(可以做什么) + why(为什么现在值得关注)。

4. 「🛠️ 值得关注」：AI 工具/项目。name + description + url。

JSON:
{{
  "top_picks": [{{"title":"","explain_simple":"","application":"","url":"","source":""}}],
  "sections": [{{"category":"🏭 AI在行业应用的案例","items":[{{"title":"","explain_simple":"","application":"","url":"","source":""}}]}}],
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
    strong_hits, weak_hits = domain_signal(
        article.get("title", ""), article.get("summary", "")
    )
    if strong_hits:
        domain_hint = f"强相关命中: {'/'.join(strong_hits[:5])}（领域高度相关）"
    elif weak_hits:
        domain_hint = f"弱相关命中: {'/'.join(weak_hits[:5])}（可能偏前沿，需判断落地价值）"
    else:
        domain_hint = "无关键词命中（需判断是否跑题或换种表达仍相关）"
    prompt = ARTICLE_PROCESS_PROMPT.format(
        title=article.get("title", ""),
        summary=article.get("summary", ""),
        source=article.get("source_name", ""),
        credibility=f"{tier} ({cv})",
        domain_hint=domain_hint,
    )
    defaults = {
        "title_cn": article.get("title", ""),
        "category": "📌 其他",
        "scores": {"credibility": 5, "freshness": 5, "applicability": 5, "insight": 5, "relevance": 5},
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
            article["category"] = normalize_category(article["category"])
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
                for k, v in {"title_cn": a.get("title",""), "category": "📌 其他", "overall_score": 5, "core_feature": "", "one_liner": "", "explain_simple": "", "application": "", "keywords": [], "related_tools": [], "scores": {"credibility":5,"freshness":5,"applicability":5,"insight":5,"relevance":5}}.items():
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
                temperature=0.5, response_format={"type": "json_object"}, max_tokens=12000,
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