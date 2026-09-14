# CLAUDE.md — AI 情报采集 Bot

每周采集 AI 行业情报 → DeepSeek 处理（分类 / 五维评分 / 摘要）→ 推送飞书周报。
定位：服务互联网业务团队（AI 产品经理为主），重点是「应用落地 / 电商 / 导购 / 评测」，不是纯前沿研究。

## 常用命令

- `venv/bin/python main.py` — 完整跑一遍：采集 → AI 处理 → 推飞书 → 存库
- `venv/bin/python main.py --test` — 只采集，不推送
- 依赖在 `venv/` 已装好；新机器需 `pip install -r requirements.txt && playwright install chromium`

## 定时推送（重要）

推送由 GitHub Actions 自动完成：`.github/workflows/weekly-report.yml`，**每周一 10:00（北京时间）**。
密钥（`FEISHU_WEBHOOK` / `DEEPSEEK_API_KEY` / `TWITTER_*`）走 GitHub Secrets；本地 `.env` 被 gitignore，不进仓库。

## 每次运行后必须做「采集复盘」

跑完 `main.py` 并产出周报后，查 `articles.db`，把「问题 + 采集质量评测结论」发给用户：

1. **评分分布** — 是否拉开差距（9-10 分应约 10%，不能 5-6 分过半堆在一起）
2. **类目平衡** — 应用落地 vs 前沿技术是否失衡（电商/应用类不能接近 0，技术类不能过半）
3. **来源分布** — Top 来源是否某源霸榜
4. **采集问题汇总** — 哪些源 0 篇、哪些 KOL 被跳过

查询「本次入库批次」的方法：

```sql
SELECT MAX(saved_at) FROM articles;                                   -- 得到本次时间戳
SELECT overall_score, category, source_name FROM articles
  WHERE saved_at = '<上一步结果>';                                     -- 三件事的原始数据
```

复盘后**一旦改了代码**，必须同步更新 `docs/product-design.md`，并把改动内容发给用户（用户会手动同步到飞书文档）。

## 代码注意事项

- `processor.py` 的 `normalize_category()` 命中顺序是「特异性从高到低」，修过吞并 bug（大类前缀里的「模型/行业」会吞掉子类目）。改动时**不要**恢复成「按通用词先匹配」的顺序。
- 评分分布约束在 `ARTICLE_PROCESS_PROMPT` 里，是「定级比例」写法（9-10≈10% / 8≈18% / 7≈25% / 5-6≈30% / 3-4≈17%），不要退回「9-10 ≤10%」这种上限写法。
- `MIN_SCORE`（config.py，当前 4）是入库过滤线；想更「降噪」可提到 5。
- Twitter 采集靠 RapidAPI → Playwright 三级降级，无凭据/被限流时 17 个 KOL 会全部「跳过」，属环境问题而非代码 bug。
