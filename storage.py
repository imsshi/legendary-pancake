"""
文章存储层 — SQLite 持久化 + 全文搜索

每次周报生成后自动保存，供 DewuClaw @bot 答疑读取
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "articles.db")


def init_db():
    """建表（幂等）"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title_cn TEXT NOT NULL,
            one_liner TEXT DEFAULT '',
            explain_simple TEXT DEFAULT '',
            application TEXT DEFAULT '',
            category TEXT DEFAULT '',
            overall_score INTEGER DEFAULT 5,
            credibility_score INTEGER DEFAULT 3,
            freshness_score INTEGER DEFAULT 3,
            applicability_score INTEGER DEFAULT 3,
            insight_score INTEGER DEFAULT 3,
            url TEXT DEFAULT '',
            source_name TEXT DEFAULT '',
            source_type TEXT DEFAULT '',
            credibility_tier TEXT DEFAULT '',
            cross_validated INTEGER DEFAULT 0,
            published TEXT DEFAULT '',
            keywords TEXT DEFAULT '[]',
            related_tools TEXT DEFAULT '[]',
            saved_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
            title_cn, one_liner, explain_simple, application, keywords,
            content='articles', content_rowid='id'
        )
    """)
    # 触发器：INSERT/DELETE/UPDATE 同步 FTS
    conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
            INSERT INTO articles_fts(rowid, title_cn, one_liner, explain_simple, application, keywords)
            VALUES (new.id, new.title_cn, new.one_liner, new.explain_simple, new.application, new.keywords);
        END;
        CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
            INSERT INTO articles_fts(articles_fts, rowid, title_cn, one_liner, explain_simple, application, keywords)
            VALUES('delete', old.id, old.title_cn, old.one_liner, old.explain_simple, old.application, old.keywords);
        END;
    """)
    conn.commit()
    conn.close()


def save_articles(articles):
    """批量保存文章（先清旧数据，再写入）"""
    init_db()
    conn = sqlite3.connect(DB_PATH)

    # 保留最近 4 周的数据
    conn.execute("DELETE FROM articles WHERE saved_at < datetime('now', '-28 days')")

    for a in articles:
        scores = a.get("scores", {})
        conn.execute(
            """INSERT INTO articles
            (title_cn, one_liner, explain_simple, application, category, overall_score,
             credibility_score, freshness_score, applicability_score, insight_score,
             url, source_name, source_type, credibility_tier, cross_validated, published,
             keywords, related_tools)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                a.get("title_cn", ""),
                a.get("one_liner", ""),
                a.get("explain_simple", ""),
                a.get("application", ""),
                a.get("category", ""),
                a.get("overall_score", 5),
                scores.get("credibility", 3),
                scores.get("freshness", 3),
                scores.get("applicability", 3),
                scores.get("insight", 3),
                a.get("url", ""),
                a.get("source_name", ""),
                a.get("source_type", ""),
                a.get("credibility_tier", ""),
                1 if a.get("cross_validated") else 0,
                a.get("published", ""),
                json.dumps(a.get("keywords", []), ensure_ascii=False),
                json.dumps(a.get("related_tools", []), ensure_ascii=False),
            ),
        )

    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    print(f"💾 已保存 {len(articles)} 篇文章 (数据库共 {count} 篇)")


def search_articles(query, limit=20):
    """全文搜索"""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT title_cn, one_liner, explain_simple, application, category,
                  overall_score, url, source_name, published
           FROM articles WHERE id IN (
               SELECT rowid FROM articles_fts WHERE articles_fts MATCH ?
               ORDER BY rank LIMIT ?
           )""",
        (query, limit),
    ).fetchall()
    conn.close()
    return [
        {
            "title_cn": r[0], "one_liner": r[1], "explain_simple": r[2],
            "application": r[3], "category": r[4], "overall_score": r[5],
            "url": r[6], "source_name": r[7], "published": r[8],
        }
        for r in rows
    ]


if __name__ == "__main__":
    init_db()
    print(f"DB 已初始化: {DB_PATH}")
