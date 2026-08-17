"""AI 情报采集 Bot — 配置文件"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================
# 飞书配置
# ============================================
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")

# ============================================
# DeepSeek API
# ============================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# ============================================
# Twitter 采集
# ============================================
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
]
RSSHUB_BASE = "https://rsshub.app"
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD", "")

# ============================================
# 采集配置
# ============================================
COLLECT_DAYS = 7
REQUEST_TIMEOUT = (8, 20)  # 连接超时 8s, 读取超时 20s
MAX_WORKERS = 5

# ============================================
# 内容筛选
# ============================================
MIN_SCORE = 4  # v3: 四维评分下综合分≥4 即可

# ============================================
# 信源可信度分级
# ============================================
# T1: 官方一手信源 — 最高可信度
# T2: 国际知名科技媒体
# T3: 国内知名科技媒体
# T4: 社交媒体/聚合 — 需交叉验证
SOURCE_CREDIBILITY = {
    # T1 — 官方
    "OpenAI Blog": "T1",
    "Anthropic Blog": "T1",
    "DeepMind Blog": "T1",
    "NVIDIA AI Blog": "T1",
    "Hugging Face Blog": "T1",
    "Import AI": "T1",
    "GitHub Blog": "T1",
    "GitHub Changelog": "T1",
    "HuggingFace Papers": "T1",
    "Hacker News": "T2",
    "HuggingFace Models": "T2",
    "ArXiv cs.AI": "T1",
    "ArXiv cs.CL": "T1",

    # T2 — 国际媒体
    "The Verge AI": "T2",
    "TechCrunch AI": "T2",
    "MIT Tech Review": "T2",
    "MarkTechPost": "T2",
    "InfoQ (en)": "T2",
    "ZDNet AI": "T2",
    "Wired AI": "T2",
    "The Register AI": "T2",
    "Nature AI": "T2",
    "GitHub Trending": "T2",
    "GitHub Trending AI": "T2",
    "Product Hunt": "T2",

    # T3 — 国内媒体
    "量子位": "T3",
    "机器之心 AI": "T3",
    "36氪 AI": "T3",
    "少数派": "T3",
    "极客公园": "T3",
    "极客公园 热门": "T3",
    "雷锋网": "T3",
    "InfoQ 中文": "T3",
    "爱范儿": "T3",
    "Retail Dive": "T3",
    "Modern Retail": "T3",
    "MarTech": "T3",
    "掘金 热榜": "T3",
    "36氪 热榜": "T3",

    # 网页采集源
    "Anthropic Blog": "T1",
    "Stability AI Blog": "T1",
    "GitHub Trending": "T2",
    "GitHub Trending AI": "T2",

    # T4 — 社交媒体（匹配前缀）
    "Twitter @": "T4",
    "微信公众号": "T3",
    "微信:": "T3",
}

# 信源等级 → 基础可信度权重
CREDIBILITY_WEIGHTS = {"T1": 1.0, "T2": 0.9, "T3": 0.85, "T4": 0.7}

# T4 被交叉验证后权重回升
CROSS_VALIDATED_WEIGHT = 0.9

# 交叉验证：标题 Jaccard 相似度阈值
CROSS_VALIDATION_SIMILARITY = 0.55
# 至少 N 个独立来源才算交叉验证
CROSS_VALIDATION_MIN_SOURCES = 2

# ============================================
# 关注领域关键词 — 用于「领域相关度」打分/提权
# 注意：不做硬淘汰（避免误杀），只作为加分信号交给 AI 判断
# ============================================
# 强相关：命中 = 高优先（应用/产品/导购/评测/业务提效）
DOMAIN_STRONG_KEYWORDS = [
    # 导购/电商
    "导购", "推荐", "电商", "购物", "商品", "零售", "搜索", "转化", "选品", "客服", "营销", "商业化",
    "ecommerce", "e-commerce", "recommendation", "shopping", "retail", "marketplace", "merchandise",
    # 评测
    "评测", "benchmark", "基准", "榜单", "模型对比", "eval",
    # 产品经理/方法论
    "产品经理", "产品设计", "增长", "用户体验", "方法论", "a/b", "ab测试",
    # 应用落地/业务
    "案例", "落地", "部署", "roi", "提效", "赋能", "降本", "企业", "业务",
    # Agent/自动化
    "agent", "智能体", "工作流", "copilot", "自动化", "workflow", "rpa",
]
# 弱相关：命中 = 一般（大模型/前沿技术，需 AI 进一步判断是否有落地价值）
DOMAIN_WEAK_KEYWORDS = [
    "大模型", "模型", "gpt", "claude", "gemini", "deepseek", "llm", "llama", "mistral",
    "多模态", "视觉", "图像", "视频", "语音", "生成", "vlm", "diffusion",
    "论文", "arxiv", "架构", "训练", "推理", "transformer", "微调", "fine-tun",
    "openai", "anthropic", "nvidia", "huggingface", "通义", "文心", "混元", "豆包",
]


def domain_signal(title, summary=""):
    """计算领域相关信号（不淘汰，只返回命中情况）"""
    text = f"{title} {summary}".lower()
    strong_hits = [kw for kw in DOMAIN_STRONG_KEYWORDS if kw.lower() in text]
    weak_hits = [kw for kw in DOMAIN_WEAK_KEYWORDS if kw.lower() in text]
    return strong_hits, weak_hits


def get_source_credibility(source_name):
    """根据来源名返回 (等级, 权重)"""
    # 精确匹配
    if source_name in SOURCE_CREDIBILITY:
        tier = SOURCE_CREDIBILITY[source_name]
    else:
        # 前缀匹配（如 "Twitter @xxx"）
        tier = "T4"  # 默认 T4
        for prefix, t in SOURCE_CREDIBILITY.items():
            if source_name.startswith(prefix):
                tier = t
                break
    return tier, CREDIBILITY_WEIGHTS.get(tier, 0.7)


def load_config():
    """验证必要配置是否齐全"""
    missing = []
    if not FEISHU_WEBHOOK:
        missing.append("FEISHU_WEBHOOK")
    if not DEEPSEEK_API_KEY:
        missing.append("DEEPSEEK_API_KEY")

    if missing:
        print(f"⚠️  缺少配置: {', '.join(missing)}")
        return False

    print("✅ 配置检查通过")
    return True
