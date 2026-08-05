# 🤖 AI 情报采集 Bot

每周自动采集国内外 AI 行业情报，通过 AI 智能处理（分类、评分、摘要），生成结构化周报推送到飞书群聊。

**定位**：帮助团队全面了解 AI 领域前沿发展，同时识别可落地的工具、方法和应用案例。

## 功能

- 📡 **16 个 RSS 源**：覆盖国内 AI 媒体、海外官方博客、主流科技媒体、学术论文
- 🐦 **17 个 Twitter KOL**：产品管理 + AI 领军人物 + AI 工具评测，免费采集
- 🌐 **网页采集**：36氪、虎嗅、Product Hunt、GitHub Trending
- 🤖 **AI 智能处理**：自动翻译、分类、评分、生成摘要和应用价值分析
- 📰 **飞书卡片推送**：结构化周报，含 Top 5、分类详情、推荐工具、每周看点
- 💰 **全部免费**：GitHub Actions 定时运行 + DeepSeek API

## 快速开始

### 1. 克隆项目

```bash
git clone <你的仓库地址>
cd ai-news-bot
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env 填入配置
```

需要填写：
| 变量 | 说明 | 获取方式 |
|------|------|----------|
| `FEISHU_WEBHOOK` | 飞书群机器人 Webhook | 飞书群 → 设置 → 群机器人 → 添加自定义机器人 |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | [platform.deepseek.com](https://platform.deepseek.com) → API Keys |
| `TWITTER_USERNAME` | Twitter 用户名（可选） | 用于 RSSHub 采集方案 |
| `TWITTER_PASSWORD` | Twitter 密码（可选） | 同上 |

### 3. 安装

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 4. 运行

```bash
python main.py          # 完整运行 → 采集 → AI处理 → 推送飞书
python main.py --test   # 测试模式（只采集，不推送）
```

### 5. 部署到 GitHub Actions（免费定时运行）

```bash
git push origin main
```

在 GitHub 仓库：**Settings → Secrets → Actions → New secret**，添加 `DEEPSEEK_API_KEY`、`FEISHU_WEBHOOK`。

Bot 会在**每周一早上 9:00（北京时间）**自动运行。也可在 Actions 页面手动触发。

---

## 信息源

### RSS（16 个）

| 类别 | 源 | 备注 |
|------|-----|------|
| 国内媒体 | 机器之心、量子位、36氪、虎嗅、少数派 | 直连 RSS |
| 产品/工具 | 人人都是产品经理 | RSSHub |
| 官方博客 | OpenAI、Anthropic、Google AI、Meta AI | 需 VPN |
| 海外媒体 | The Verge、TechCrunch、MIT Tech Review、VentureBeat | 需 VPN |
| 学术 | ArXiv cs.AI | 限 50 篇/次 |

### Twitter KOL（17 个）

- **产品管理**：shreyas、lennysan、wes_kao
- **AI 领军**：sama、ylecun、AndrewYNg、DrJimFan
- **AI 工程**：swyx、chipro、_akhaliq
- **AI 产品/工具**：minchoi、heyBarsee、rowancheung、rachel_l_woods、saranormous、alexalbert__、ai_sources

### 网页采集

36氪 AI、虎嗅 AI、Product Hunt、GitHub Trending

---

## 周报分类

| 分类 | 说明 |
|------|------|
| 🧠 大模型动态 | 模型发布、更新、评测、技术突破 |
| 🛠️ AI工具与产品 | AI 工具、开源项目、GitHub 热门 |
| 💼 AI应用落地 | 企业在电商/营销/客服等领域的 AI 落地案例 |
| 🎙️ KOL洞察 | AI 领域专家观点、行业趋势判断 |
| 🔬 前沿技术 | Agent、多模态、RAG 等前沿方向 |

---

## 成本

| 项目 | 方案 | 费用 |
|------|------|------|
| 服务器 | GitHub Actions | 免费 |
| LLM | DeepSeek API | ¥10 起充，能用很久 |
| Twitter | Nitter RSS + Playwright | 免费 |
| RSS | 直连 + RSSHub 公共实例 | 免费 |
| 飞书 | Webhook | 免费 |

---

## 项目结构

```
ai-news-bot/
├── main.py                 # 主入口
├── config.py               # 配置
├── processor.py            # AI 处理（分类、评分、周报生成）
├── reporter.py             # 飞书卡片推送
├── collectors/
│   ├── __init__.py         # 整合入口
│   ├── rss_collector.py    # RSS（16源）
│   ├── web_collector.py    # 网页爬虫
│   └── twitter_collector.py # Twitter（3级降级）
├── .github/workflows/
│   └── weekly-report.yml   # GitHub Actions 定时
├── requirements.txt        # Python 依赖
└── .env.example            # 环境变量模板
```

## 常见问题

**Q: 国内 RSS 源采集不到？**
A: 部分 RSS 地址可能需要 VPN。可以先检查 `curl -I <rss_url>` 看是否可达。

**Q: Twitter 采集不稳定？**
A: Nitter 实例经常挂了，方案 B（RSSHub）需要填 Twitter 账号，方案 C（Playwright）最可靠。

**Q: 想增删信息源？**
A: 编辑 `collectors/rss_collector.py` 的 `SOURCES` 列表，或 `collectors/twitter_collector.py` 的 `KOLS` 列表。

**Q: 改推送频率？**
A: 修改 `.github/workflows/weekly-report.yml` 的 cron 表达式。
