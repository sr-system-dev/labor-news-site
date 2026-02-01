#!/usr/bin/env python3
"""
労務関連ニュース収集スクリプト
RSSフィードから最新ニュースを取得し、Markdown形式で保存する

使用方法:
    python collect_news.py           # 過去7日間のニュースを収集（デフォルト）
    python collect_news.py --days 14 # 過去14日間のニュースを収集
"""

import argparse
import feedparser
import os
from datetime import datetime, timedelta
from pathlib import Path
import html
import re
from typing import NamedTuple
from collections import defaultdict

# Anthropic APIクライアント（オプション）
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class NewsItem(NamedTuple):
    """ニュース記事を表すデータクラス"""
    title: str
    link: str
    published: datetime
    summary: str
    source: str


# RSSフィードの設定
RSS_FEEDS = {
    "労働新聞社": "https://www.rodo.co.jp/feed/",
    "労務ドットコム": "https://roumu.com/feed/",
    "日本の人事部": "https://jinjibu.jp/rss/?mode=atcl",
    "日本の人事部（プレスリリース）": "https://jinjibu.jp/rss/?mode=news",
}

# 労務関連キーワード（フィルタリング用）
LABOR_KEYWORDS = [
    "労働", "雇用", "賃金", "給与", "残業", "働き方", "労務",
    "人事", "採用", "退職", "解雇", "休暇", "有給", "育児",
    "介護", "ハラスメント", "パワハラ", "セクハラ", "労災",
    "社会保険", "厚生年金", "健康保険", "雇用保険", "労働基準",
    "最低賃金", "同一労働", "テレワーク", "在宅勤務", "副業",
    "兼業", "定年", "再雇用", "派遣", "契約社員", "正社員",
    "非正規", "就業規則", "労働組合", "団体交渉", "ストライキ",
    "36協定", "安全衛生", "メンタルヘルス", "過労", "長時間労働",
]

# 出力ディレクトリ
OUTPUT_DIR = Path("news")
DOCS_DIR = Path("docs")  # GitHub Pages用

# デフォルトの収集日数
DEFAULT_DAYS = 7

# HTMLテンプレート
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>労務ニュース Weekly | {period}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --secondary: #8b5cf6;
            --accent: #06b6d4;
            --success: #10b981;
            --warning: #f59e0b;
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #334155;
            --bg-hover: #475569;
            --text-primary: #f8fafc;
            --text-secondary: #cbd5e1;
            --text-muted: #94a3b8;
            --border: #475569;
            --gradient-1: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --gradient-2: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #06b6d4 100%);
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
            --shadow-glow: 0 0 40px rgba(99, 102, 241, 0.15);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Noto Sans JP', 'Inter', -apple-system, BlinkMacSystemFont, "Hiragino Kaku Gothic ProN", "Hiragino Sans", Meiryo, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.7;
            min-height: 100vh;
        }}

        * {{
            font-family: inherit;
        }}

        .hero {{
            background: var(--gradient-2);
            position: relative;
            overflow: hidden;
            padding: 60px 20px 80px;
        }}

        .hero::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Ccircle cx='30' cy='30' r='2'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
            opacity: 0.5;
        }}

        .hero-content {{
            position: relative;
            max-width: 800px;
            margin: 0 auto;
            text-align: center;
        }}

        .hero-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(255,255,255,0.15);
            backdrop-filter: blur(10px);
            padding: 8px 16px;
            border-radius: 50px;
            font-size: 0.85rem;
            font-weight: 500;
            margin-bottom: 24px;
            border: 1px solid rgba(255,255,255,0.2);
        }}

        .hero-badge::before {{
            content: '📰';
        }}

        .hero h1 {{
            font-size: clamp(2rem, 5vw, 3rem);
            font-weight: 700;
            margin-bottom: 16px;
            letter-spacing: -0.02em;
        }}

        .hero .period {{
            font-size: 1.25rem;
            opacity: 0.9;
            margin-bottom: 32px;
        }}

        .stats-grid {{
            display: flex;
            justify-content: center;
            gap: 16px;
            flex-wrap: wrap;
            margin-bottom: 24px;
        }}

        .stat-card {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
            padding: 20px 32px;
            border-radius: 16px;
            text-align: center;
            min-width: 140px;
        }}

        .stat-value {{
            font-size: 2.5rem;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 4px;
        }}

        .stat-label {{
            font-size: 0.875rem;
            opacity: 0.8;
        }}

        .meta {{
            font-size: 0.875rem;
            opacity: 0.7;
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 0 20px;
            transform: translateY(-40px);
        }}

        .date-card {{
            background: var(--bg-secondary);
            border-radius: 20px;
            margin-bottom: 24px;
            overflow: hidden;
            box-shadow: var(--shadow-lg), var(--shadow-glow);
            border: 1px solid var(--border);
        }}

        .date-header {{
            background: var(--bg-card);
            padding: 20px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
        }}

        .date-info {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .date-icon {{
            width: 44px;
            height: 44px;
            background: var(--gradient-1);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
        }}

        .date-text {{
            font-size: 1.125rem;
            font-weight: 600;
        }}

        .date-weekday {{
            font-size: 0.875rem;
            color: var(--text-muted);
            margin-top: 2px;
        }}

        .date-count {{
            background: var(--primary);
            color: white;
            padding: 6px 14px;
            border-radius: 50px;
            font-size: 0.875rem;
            font-weight: 600;
        }}

        .source-group {{
            border-bottom: 1px solid var(--border);
        }}

        .source-group:last-child {{
            border-bottom: none;
        }}

        .source-header {{
            padding: 16px 24px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 600;
            color: var(--text-secondary);
            font-size: 0.9rem;
            background: rgba(255,255,255,0.02);
        }}

        .source-icon {{
            width: 28px;
            height: 28px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.875rem;
        }}

        .source-icon.rodo {{ background: linear-gradient(135deg, #3b82f6, #6366f1); }}
        .source-icon.roumu {{ background: linear-gradient(135deg, #10b981, #14b8a6); }}
        .source-icon.jinjibu {{ background: linear-gradient(135deg, #8b5cf6, #a855f7); }}

        .news-list {{
            padding: 0;
        }}

        .news-item {{
            padding: 20px 24px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            transition: all 0.2s ease;
            cursor: pointer;
        }}

        .news-item:last-child {{
            border-bottom: none;
        }}

        .news-item:hover {{
            background: var(--bg-hover);
        }}

        .news-item a {{
            text-decoration: none;
            color: inherit;
            display: block;
        }}

        .news-title {{
            font-size: 1rem;
            font-weight: 500;
            color: var(--text-primary);
            margin-bottom: 8px;
            line-height: 1.5;
            display: flex;
            align-items: flex-start;
            gap: 8px;
        }}

        .news-title::before {{
            content: '';
            width: 6px;
            height: 6px;
            background: var(--accent);
            border-radius: 50%;
            margin-top: 8px;
            flex-shrink: 0;
        }}

        .news-item:hover .news-title {{
            color: var(--accent);
        }}

        .news-meta {{
            display: flex;
            align-items: center;
            gap: 16px;
            margin-left: 14px;
        }}

        .news-time {{
            font-size: 0.8rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 4px;
        }}

        .news-time::before {{
            content: '🕐';
            font-size: 0.75rem;
        }}

        .news-summary {{
            font-size: 0.875rem;
            color: var(--text-muted);
            line-height: 1.6;
            margin-left: 14px;
            margin-top: 8px;
            padding: 12px 16px;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            border-left: 3px solid var(--primary);
        }}

        .summary-card {{
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.1));
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: 20px;
            padding: 28px;
            margin-bottom: 32px;
            position: relative;
            overflow: hidden;
        }}

        .summary-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: var(--gradient-2);
        }}

        .summary-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }}

        .summary-icon {{
            width: 48px;
            height: 48px;
            background: var(--gradient-1);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            flex-shrink: 0;
        }}

        .summary-header-text {{
            flex: 1;
            min-width: 150px;
        }}

        .summary-title {{
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .summary-subtitle {{
            font-size: 0.875rem;
            color: var(--text-muted);
        }}

        .summary-content {{
            color: var(--text-secondary);
            line-height: 1.9;
            font-size: 0.95rem;
        }}

        .summary-content ul {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}

        .summary-content li {{
            padding: 16px 20px;
            padding-left: 44px;
            position: relative;
            background: rgba(0, 0, 0, 0.15);
            border-radius: 12px;
            margin-bottom: 12px;
            border-left: 4px solid var(--success);
        }}

        .summary-content li:last-child {{
            margin-bottom: 0;
        }}

        .summary-content li::before {{
            content: '✓';
            position: absolute;
            left: 16px;
            top: 16px;
            color: var(--success);
            font-weight: bold;
            font-size: 1rem;
        }}

        .ai-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(99, 102, 241, 0.2);
            color: var(--accent);
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }}

        .archive-section {{
            background: var(--bg-secondary);
            border-radius: 20px;
            padding: 28px;
            margin-top: 40px;
            border: 1px solid var(--border);
        }}

        .archive-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 20px;
        }}

        .archive-icon {{
            width: 40px;
            height: 40px;
            background: var(--bg-card);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
        }}

        .archive-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text-primary);
        }}

        .archive-list {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 12px;
        }}

        .archive-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px 18px;
            background: var(--bg-card);
            border-radius: 12px;
            text-decoration: none;
            color: var(--text-secondary);
            transition: all 0.2s ease;
            border: 1px solid transparent;
        }}

        .archive-item:hover {{
            background: var(--bg-hover);
            border-color: var(--primary);
            color: var(--text-primary);
        }}

        .archive-item.current {{
            border-color: var(--primary);
            background: rgba(99, 102, 241, 0.1);
        }}

        .archive-item-icon {{
            font-size: 1.25rem;
        }}

        .archive-item-date {{
            font-weight: 500;
        }}

        .archive-item-badge {{
            margin-left: auto;
            background: var(--bg-primary);
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        .archive-item.current .archive-item-badge {{
            background: var(--primary);
            color: white;
        }}

        footer {{
            text-align: center;
            padding: 48px 20px;
            color: var(--text-muted);
            font-size: 0.875rem;
        }}

        footer a {{
            color: var(--accent);
            text-decoration: none;
        }}

        footer a:hover {{
            text-decoration: underline;
        }}

        .footer-brand {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }}

        @media (max-width: 640px) {{
            .hero {{
                padding: 40px 16px 60px;
            }}

            .hero h1 {{
                font-size: 1.75rem;
            }}

            .stats-grid {{
                gap: 12px;
            }}

            .stat-card {{
                padding: 16px 24px;
                min-width: 120px;
            }}

            .stat-value {{
                font-size: 2rem;
            }}

            .container {{
                padding: 0 12px;
            }}

            .date-card {{
                border-radius: 16px;
            }}

            .date-header {{
                flex-direction: column;
                align-items: flex-start;
                gap: 12px;
                padding: 16px 20px;
            }}

            .date-count {{
                align-self: flex-start;
            }}

            .source-header,
            .news-item {{
                padding: 14px 20px;
            }}

            .news-title {{
                font-size: 0.95rem;
            }}
        }}

        /* Animation */
        @keyframes fadeInUp {{
            from {{
                opacity: 0;
                transform: translateY(20px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        .date-card {{
            animation: fadeInUp 0.5s ease-out;
            animation-fill-mode: both;
        }}

        .date-card:nth-child(1) {{ animation-delay: 0.1s; }}
        .date-card:nth-child(2) {{ animation-delay: 0.2s; }}
        .date-card:nth-child(3) {{ animation-delay: 0.3s; }}
        .date-card:nth-child(4) {{ animation-delay: 0.4s; }}
        .date-card:nth-child(5) {{ animation-delay: 0.5s; }}
        .date-card:nth-child(6) {{ animation-delay: 0.6s; }}
        .date-card:nth-child(7) {{ animation-delay: 0.7s; }}
    </style>
</head>
<body>
    <div class="hero">
        <div class="hero-content">
            <div class="hero-badge">Weekly Report</div>
            <h1>労務ニュース Weekly</h1>
            <div class="period">{period}</div>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{total_count}</div>
                    <div class="stat-label">ニュース</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{source_count}</div>
                    <div class="stat-label">ソース</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{day_count}</div>
                    <div class="stat-label">日間</div>
                </div>
            </div>
            <div class="meta">Last updated: {collected_at}</div>
        </div>
    </div>

    <div class="container">
        {summary_section}
        {content}
        {archive_section}
    </div>

    <footer>
        <div class="footer-brand">労務ニュース Weekly</div>
        <p>RSSフィードから自動収集・更新</p>
    </footer>
</body>
</html>
"""


def clean_html(text: str) -> str:
    """HTMLタグを除去してテキストをクリーンアップ"""
    if not text:
        return ""
    # HTMLエンティティをデコード
    text = html.unescape(text)
    # HTMLタグを除去
    text = re.sub(r'<[^>]+>', '', text)
    # 連続する空白を1つに
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_date(entry: dict) -> datetime:
    """フィードエントリから日付を解析"""
    # published_parsedがあればそれを使用
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime(*entry.published_parsed[:6])
    # updated_parsedがあればそれを使用
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6])
    # どちらもなければ現在時刻
    return datetime.now()


def is_labor_related(text: str) -> bool:
    """テキストが労務関連かどうかを判定"""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in LABOR_KEYWORDS)


def fetch_feed(url: str, source_name: str) -> list[NewsItem]:
    """RSSフィードを取得してニュースアイテムのリストを返す"""
    items = []
    try:
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            print(f"  警告: {source_name} のフィード取得に問題がありました")
            return items

        for entry in feed.entries:
            title = clean_html(entry.get('title', ''))
            link = entry.get('link', '')
            summary = clean_html(entry.get('summary', entry.get('description', '')))
            published = parse_date(entry)

            # タイトルまたはサマリーが労務関連の場合のみ追加
            if is_labor_related(title + summary):
                items.append(NewsItem(
                    title=title,
                    link=link,
                    published=published,
                    summary=summary[:200] + "..." if len(summary) > 200 else summary,
                    source=source_name,
                ))
    except Exception as e:
        print(f"  エラー: {source_name} の取得に失敗しました - {e}")

    return items


def generate_ai_summary(items: list[NewsItem]) -> str | None:
    """AIを使って週次ニュースサマリーを生成"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not ANTHROPIC_AVAILABLE:
        print("  警告: anthropicパッケージがインストールされていません")
        return None

    if not api_key:
        print("  警告: ANTHROPIC_API_KEYが設定されていません")
        return None

    # ニュースをテキストにまとめる
    news_text = ""
    for item in items[:50]:  # 最大50件に制限（トークン節約）
        news_text += f"- {item.title} ({item.source})\n"

    prompt = f"""以下は今週の労務関連ニュースの一覧です。これを人事・労務担当者向けに、重要なポイントを3〜5つにまとめてください。

【今週のニュース一覧】
{news_text}

【出力形式】
- 箇条書きで3〜5つのポイント
- 各ポイントは1〜2文で簡潔に
- 専門用語は避け、わかりやすい表現で
- 実務に役立つ視点でまとめる

日本語で回答してください。"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text
    except Exception as e:
        print(f"  エラー: サマリー生成に失敗しました - {e}")
        return None


def filter_by_date_range(
    items: list[NewsItem], start_date: datetime, end_date: datetime
) -> list[NewsItem]:
    """指定された日付範囲内のニュースのみをフィルタリング"""
    filtered = []
    for item in items:
        item_date = item.published.replace(hour=0, minute=0, second=0, microsecond=0)
        if start_date <= item_date <= end_date:
            filtered.append(item)
    return filtered


def group_by_date(items: list[NewsItem]) -> dict[str, list[NewsItem]]:
    """ニュースアイテムを日付ごとにグループ化"""
    grouped = defaultdict(list)
    for item in items:
        date_str = item.published.strftime("%Y-%m-%d")
        grouped[date_str].append(item)
    return grouped


def generate_markdown(
    items: list[NewsItem], start_date: datetime, end_date: datetime
) -> str:
    """週次レポート用のMarkdownコンテンツを生成"""
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    lines = [
        f"# 労務関連ニュース",
        f"## 期間: {start_str} 〜 {end_str}",
        "",
        f"*収集日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        f"ニュース件数: **{len(items)}件**",
        "",
        "---",
        "",
    ]

    # 日付ごとにグループ化
    by_date = group_by_date(items)

    for date_str in sorted(by_date.keys(), reverse=True):
        date_items = by_date[date_str]
        lines.append(f"## 📅 {date_str}（{len(date_items)}件）")
        lines.append("")

        # ソースごとにグループ化
        by_source = defaultdict(list)
        for item in date_items:
            by_source[item.source].append(item)

        for source, source_items in sorted(by_source.items()):
            lines.append(f"### {source}")
            lines.append("")

            for item in sorted(source_items, key=lambda x: x.published, reverse=True):
                time_str = item.published.strftime("%H:%M")
                lines.append(f"- [{item.title}]({item.link}) *({time_str})*")
                if item.summary:
                    # サマリーを短く表示
                    short_summary = item.summary[:100] + "..." if len(item.summary) > 100 else item.summary
                    lines.append(f"  > {short_summary}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def save_markdown(start_date: datetime, end_date: datetime, content: str) -> Path:
    """Markdownファイルを保存（日付範囲形式）"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    file_path = OUTPUT_DIR / f"{start_str}_{end_str}.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def escape_html(text: str) -> str:
    """HTMLエスケープ"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def get_source_icon_class(source: str) -> str:
    """ソース名からアイコンクラスを取得"""
    if "労働新聞" in source:
        return "rodo"
    elif "労務ドットコム" in source or "roumu" in source.lower():
        return "roumu"
    elif "人事部" in source:
        return "jinjibu"
    return "default"


def get_source_emoji(source: str) -> str:
    """ソース名から絵文字を取得"""
    if "労働新聞" in source:
        return "📰"
    elif "労務ドットコム" in source or "roumu" in source.lower():
        return "💼"
    elif "人事部" in source:
        return "👥"
    return "📄"


def get_weekday_jp(date_str: str) -> str:
    """日付文字列から日本語曜日を取得"""
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return weekdays[date_obj.weekday()]


def generate_html(
    items: list[NewsItem], start_date: datetime, end_date: datetime,
    summary: str | None = None,
    archives: list[tuple[str, str, bool]] | None = None
) -> str:
    """HTMLコンテンツを生成

    Args:
        items: ニュースアイテムのリスト
        start_date: 開始日
        end_date: 終了日
        summary: AIサマリー（オプション）
        archives: アーカイブ一覧 [(ファイル名, 期間表示, 現在かどうか), ...]
    """
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    period = f"{start_str} 〜 {end_str}"

    # サマリーセクションを生成
    if summary:
        # サマリーテキストをHTMLに変換（箇条書きをリストに）
        lines = summary.split("\n")
        list_items = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 箇条書きのパターンをチェック
            if line.startswith("- ") or line.startswith("・") or line.startswith("• "):
                item_text = line.lstrip("-・• ").strip()
                if item_text:
                    list_items.append(f"<li>{escape_html(item_text)}</li>")
            elif line.startswith("* "):
                item_text = line.lstrip("* ").strip()
                if item_text:
                    list_items.append(f"<li>{escape_html(item_text)}</li>")
            elif not line.startswith("#") and not line.startswith("**"):
                # 番号付きリストも対応
                match = re.match(r'^\d+[\.\)]\s*(.+)$', line)
                if match:
                    list_items.append(f"<li>{escape_html(match.group(1))}</li>")
                elif len(line) > 10:  # 短すぎる行は除外
                    # 通常のテキスト行も箇条書きとして追加
                    list_items.append(f"<li>{escape_html(line)}</li>")

        if list_items:
            summary_list = "<ul>" + "".join(list_items) + "</ul>"
        else:
            # 箇条書きが見つからない場合は段落として表示
            paragraphs = [f"<p>{escape_html(p.strip())}</p>" for p in summary.split("\n\n") if p.strip()]
            summary_list = "".join(paragraphs) if paragraphs else f"<p>{escape_html(summary)}</p>"

        summary_section = f'''
        <div class="summary-card">
            <div class="summary-header">
                <div class="summary-icon">🤖</div>
                <div class="summary-header-text">
                    <div class="summary-title">今週のポイント</div>
                    <div class="summary-subtitle">AIによる自動サマリー</div>
                </div>
                <div class="ai-badge">✨ AI Generated</div>
            </div>
            <div class="summary-content">
                {summary_list}
            </div>
        </div>
        '''
    else:
        summary_section = ""

    # 日付ごとにグループ化
    by_date = group_by_date(items)

    # ソース数をカウント
    sources = set(item.source for item in items)

    # 日数をカウント
    day_count = len(by_date)

    # コンテンツ生成
    content_parts = []

    for date_str in sorted(by_date.keys(), reverse=True):
        date_items = by_date[date_str]
        weekday = get_weekday_jp(date_str)

        # 日付カード
        content_parts.append(f'<div class="date-card">')
        content_parts.append(f'<div class="date-header">')
        content_parts.append(f'<div class="date-info">')
        content_parts.append(f'<div class="date-icon">📅</div>')
        content_parts.append(f'<div>')
        content_parts.append(f'<div class="date-text">{date_str}</div>')
        content_parts.append(f'<div class="date-weekday">{weekday}曜日</div>')
        content_parts.append(f'</div>')
        content_parts.append(f'</div>')
        content_parts.append(f'<div class="date-count">{len(date_items)}件</div>')
        content_parts.append(f'</div>')

        # ソースごとにグループ化
        by_source = defaultdict(list)
        for item in date_items:
            by_source[item.source].append(item)

        for source, source_items in sorted(by_source.items()):
            icon_class = get_source_icon_class(source)
            emoji = get_source_emoji(source)

            content_parts.append(f'<div class="source-group">')
            content_parts.append(
                f'<div class="source-header">'
                f'<span class="source-icon {icon_class}">{emoji}</span>'
                f'{escape_html(source)}'
                f'</div>'
            )
            content_parts.append(f'<div class="news-list">')

            for item in sorted(source_items, key=lambda x: x.published, reverse=True):
                time_str = item.published.strftime("%H:%M")
                title_escaped = escape_html(item.title)
                link_escaped = escape_html(item.link)
                summary_escaped = escape_html(item.summary) if item.summary else ""

                content_parts.append(f'<div class="news-item">')
                content_parts.append(
                    f'<a href="{link_escaped}" target="_blank" rel="noopener">'
                )
                content_parts.append(f'<div class="news-title">{title_escaped}</div>')
                content_parts.append(f'<div class="news-meta">')
                content_parts.append(f'<span class="news-time">{time_str}</span>')
                content_parts.append(f'</div>')
                if summary_escaped:
                    short_summary = (
                        summary_escaped[:100] + "..."
                        if len(summary_escaped) > 100
                        else summary_escaped
                    )
                    content_parts.append(f'<div class="news-summary">{short_summary}</div>')
                content_parts.append(f'</a>')
                content_parts.append(f'</div>')

            content_parts.append(f'</div>')
            content_parts.append(f'</div>')

        content_parts.append(f'</div>')

    content = "\n".join(content_parts)

    # アーカイブセクションを生成
    if archives and len(archives) > 0:
        archive_items = []
        for filename, period_label, is_current in archives:
            current_class = " current" if is_current else ""
            badge_text = "現在" if is_current else "過去"
            archive_items.append(
                f'<a href="{filename}" class="archive-item{current_class}">'
                f'<span class="archive-item-icon">📅</span>'
                f'<span class="archive-item-date">{period_label}</span>'
                f'<span class="archive-item-badge">{badge_text}</span>'
                f'</a>'
            )
        archive_section = f'''
        <div class="archive-section">
            <div class="archive-header">
                <div class="archive-icon">📚</div>
                <div class="archive-title">過去のニュース一覧</div>
            </div>
            <div class="archive-list">
                {"".join(archive_items)}
            </div>
        </div>
        '''
    else:
        archive_section = ""

    # テンプレートに埋め込み
    html_content = HTML_TEMPLATE.format(
        period=period,
        total_count=len(items),
        source_count=len(sources),
        day_count=day_count,
        collected_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        summary_section=summary_section,
        archive_section=archive_section,
        content=content,
    )

    return html_content


def get_archive_list(current_start: str, current_end: str) -> list[tuple[str, str, bool]]:
    """既存のアーカイブ一覧を取得"""
    archives = []
    current_filename = f"{current_start}_{current_end}.html"

    if DOCS_DIR.exists():
        # HTMLファイルを検索（日付範囲形式のもののみ）
        for html_file in sorted(DOCS_DIR.glob("????-??-??_????-??-??.html"), reverse=True):
            filename = html_file.name
            # ファイル名から期間を抽出
            parts = filename.replace(".html", "").split("_")
            if len(parts) == 2:
                start, end = parts
                period_label = f"{start} 〜 {end}"
                is_current = (filename == current_filename)
                archives.append((filename, period_label, is_current))

    # 現在のファイルがまだ存在しない場合は追加
    if not any(a[0] == current_filename for a in archives):
        period_label = f"{current_start} 〜 {current_end}"
        archives.insert(0, (current_filename, period_label, True))

    return archives


def save_html(start_date: datetime, end_date: datetime, content: str) -> Path:
    """HTMLファイルを保存（GitHub Pages用）"""
    DOCS_DIR.mkdir(exist_ok=True)

    # index.htmlとして保存（GitHub Pages用）
    index_path = DOCS_DIR / "index.html"
    index_path.write_text(content, encoding="utf-8")

    # アーカイブ用にも保存
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    archive_path = DOCS_DIR / f"{start_str}_{end_str}.html"
    archive_path.write_text(content, encoding="utf-8")

    return index_path


def parse_args():
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description="労務関連ニュースを収集してMarkdown/HTML形式で保存します"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"収集する日数（デフォルト: {DEFAULT_DAYS}日間）",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="HTML生成をスキップする",
    )
    parser.add_argument(
        "--no-markdown",
        action="store_true",
        help="Markdown生成をスキップする",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="AIサマリー生成をスキップする",
    )
    return parser.parse_args()


def main():
    """メイン処理"""
    args = parse_args()
    days = args.days

    # 日付範囲を計算（今日を含む過去N日間）
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days - 1)

    print("=" * 50)
    print("労務関連ニュース収集スクリプト")
    print("=" * 50)
    print()
    print(f"収集期間: {start_date.strftime('%Y-%m-%d')} 〜 {end_date.strftime('%Y-%m-%d')}（{days}日間）")
    print()

    all_items = []

    # 各フィードからニュースを取得
    for source_name, url in RSS_FEEDS.items():
        print(f"取得中: {source_name}...")
        items = fetch_feed(url, source_name)
        print(f"  → {len(items)}件取得")
        all_items.extend(items)

    print()
    print(f"フィードから合計: {len(all_items)}件取得")

    # 日付範囲でフィルタリング
    filtered_items = filter_by_date_range(all_items, start_date, end_date)
    print(f"期間内のニュース: {len(filtered_items)}件")
    print()

    if not filtered_items:
        print("指定期間内にニュースが見つかりませんでした。")
        return

    # AIサマリーを生成
    summary = None
    if not args.no_summary:
        print("AIサマリーを生成中...")
        summary = generate_ai_summary(filtered_items)
        if summary:
            print("  → サマリー生成完了")
        else:
            print("  → サマリー生成スキップ（APIキー未設定または失敗）")

    # Markdownファイルを生成
    if not args.no_markdown:
        print("Markdownファイルを生成中...")
        md_content = generate_markdown(filtered_items, start_date, end_date)
        md_path = save_markdown(start_date, end_date, md_content)
        print(f"  → {md_path}")

    # HTMLファイルを生成
    if not args.no_html:
        print("HTMLファイルを生成中...")
        # アーカイブ一覧を取得
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        archives = get_archive_list(start_str, end_str)
        print(f"  アーカイブ数: {len(archives)}件")

        html_content = generate_html(filtered_items, start_date, end_date, summary, archives)
        html_path = save_html(start_date, end_date, html_content)
        print(f"  → {html_path} (GitHub Pages用)")

    print()
    print("完了しました！")


if __name__ == "__main__":
    main()
