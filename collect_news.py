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
from datetime import datetime, timedelta
from pathlib import Path
import html
import re
from typing import NamedTuple
from collections import defaultdict


class NewsItem(NamedTuple):
    """ニュース記事を表すデータクラス"""
    title: str
    link: str
    published: datetime
    summary: str
    source: str


# RSSフィードの設定
RSS_FEEDS = {
    "厚生労働省": "https://www.mhlw.go.jp/stf/rss/shinchaku.xml",
    "厚生労働省（報道発表）": "https://www.mhlw.go.jp/stf/rss/houdou.xml",
    "労働新聞社": "https://www.rodo.co.jp/feed/",
    "労務ドットコム": "https://roumu.com/feed/",
    "日本の人事部": "https://jinjibu.jp/rss/news.rss",
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
    <title>労務関連ニュース - {period}</title>
    <style>
        :root {{
            --primary-color: #2c5282;
            --secondary-color: #4a5568;
            --accent-color: #3182ce;
            --bg-color: #f7fafc;
            --card-bg: #ffffff;
            --border-color: #e2e8f0;
            --text-color: #2d3748;
            --text-muted: #718096;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Sans", "Noto Sans JP", sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }}

        header {{
            background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
            color: white;
            padding: 40px 20px;
            text-align: center;
            margin-bottom: 30px;
            border-radius: 0 0 20px 20px;
        }}

        header h1 {{
            font-size: 1.8rem;
            margin-bottom: 10px;
        }}

        header .period {{
            font-size: 1.1rem;
            opacity: 0.9;
        }}

        header .meta {{
            font-size: 0.9rem;
            opacity: 0.8;
            margin-top: 15px;
        }}

        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 20px;
            flex-wrap: wrap;
        }}

        .stat-item {{
            background: rgba(255,255,255,0.2);
            padding: 10px 20px;
            border-radius: 10px;
        }}

        .stat-number {{
            font-size: 1.5rem;
            font-weight: bold;
        }}

        .stat-label {{
            font-size: 0.85rem;
            opacity: 0.9;
        }}

        .date-section {{
            margin-bottom: 30px;
        }}

        .date-header {{
            background: var(--primary-color);
            color: white;
            padding: 12px 20px;
            border-radius: 10px 10px 0 0;
            font-size: 1.1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .date-header .count {{
            background: rgba(255,255,255,0.2);
            padding: 4px 12px;
            border-radius: 15px;
            font-size: 0.85rem;
        }}

        .source-section {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-top: none;
        }}

        .source-section:last-child {{
            border-radius: 0 0 10px 10px;
        }}

        .source-header {{
            background: var(--bg-color);
            padding: 10px 20px;
            font-weight: bold;
            color: var(--secondary-color);
            border-bottom: 1px solid var(--border-color);
            font-size: 0.95rem;
        }}

        .news-item {{
            padding: 15px 20px;
            border-bottom: 1px solid var(--border-color);
            transition: background-color 0.2s;
        }}

        .news-item:hover {{
            background-color: #f0f7ff;
        }}

        .news-item:last-child {{
            border-bottom: none;
        }}

        .news-title {{
            margin-bottom: 8px;
        }}

        .news-title a {{
            color: var(--accent-color);
            text-decoration: none;
            font-weight: 500;
            font-size: 1rem;
        }}

        .news-title a:hover {{
            text-decoration: underline;
        }}

        .news-time {{
            color: var(--text-muted);
            font-size: 0.8rem;
            margin-left: 8px;
        }}

        .news-summary {{
            color: var(--text-muted);
            font-size: 0.9rem;
            line-height: 1.5;
        }}

        footer {{
            text-align: center;
            padding: 30px;
            color: var(--text-muted);
            font-size: 0.85rem;
        }}

        footer a {{
            color: var(--accent-color);
        }}

        @media (max-width: 600px) {{
            .container {{
                padding: 10px;
            }}

            header {{
                padding: 25px 15px;
                border-radius: 0;
            }}

            header h1 {{
                font-size: 1.4rem;
            }}

            .stats {{
                gap: 15px;
            }}

            .stat-item {{
                padding: 8px 15px;
            }}

            .date-header {{
                flex-direction: column;
                gap: 8px;
                text-align: center;
            }}

            .news-item {{
                padding: 12px 15px;
            }}

            .news-title a {{
                font-size: 0.95rem;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>労務関連ニュース</h1>
        <div class="period">{period}</div>
        <div class="stats">
            <div class="stat-item">
                <div class="stat-number">{total_count}</div>
                <div class="stat-label">ニュース件数</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{source_count}</div>
                <div class="stat-label">情報ソース</div>
            </div>
        </div>
        <div class="meta">収集日時: {collected_at}</div>
    </header>

    <div class="container">
        {content}
    </div>

    <footer>
        <p>RSSフィードから自動収集 | <a href="https://github.com/" target="_blank">GitHub</a>で公開中</p>
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
            # 厚生労働省のフィードは全て含める
            if "厚生労働省" in source_name or is_labor_related(title + summary):
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


def generate_html(
    items: list[NewsItem], start_date: datetime, end_date: datetime
) -> str:
    """HTMLコンテンツを生成"""
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    period = f"{start_str} 〜 {end_str}"

    # 日付ごとにグループ化
    by_date = group_by_date(items)

    # ソース数をカウント
    sources = set(item.source for item in items)

    # コンテンツ生成
    content_parts = []

    for date_str in sorted(by_date.keys(), reverse=True):
        date_items = by_date[date_str]

        # 日付ヘッダー
        content_parts.append(f'<div class="date-section">')
        content_parts.append(
            f'<div class="date-header">'
            f'<span>{date_str}</span>'
            f'<span class="count">{len(date_items)}件</span>'
            f'</div>'
        )

        # ソースごとにグループ化
        by_source = defaultdict(list)
        for item in date_items:
            by_source[item.source].append(item)

        for source, source_items in sorted(by_source.items()):
            content_parts.append(f'<div class="source-section">')
            content_parts.append(
                f'<div class="source-header">{escape_html(source)}</div>'
            )

            for item in sorted(source_items, key=lambda x: x.published, reverse=True):
                time_str = item.published.strftime("%H:%M")
                title_escaped = escape_html(item.title)
                link_escaped = escape_html(item.link)
                summary_escaped = escape_html(item.summary) if item.summary else ""

                content_parts.append(f'<div class="news-item">')
                content_parts.append(f'<div class="news-title">')
                content_parts.append(
                    f'<a href="{link_escaped}" target="_blank" rel="noopener">{title_escaped}</a>'
                )
                content_parts.append(f'<span class="news-time">{time_str}</span>')
                content_parts.append(f'</div>')
                if summary_escaped:
                    short_summary = (
                        summary_escaped[:120] + "..."
                        if len(summary_escaped) > 120
                        else summary_escaped
                    )
                    content_parts.append(f'<div class="news-summary">{short_summary}</div>')
                content_parts.append(f'</div>')

            content_parts.append(f'</div>')

        content_parts.append(f'</div>')

    content = "\n".join(content_parts)

    # テンプレートに埋め込み
    html_content = HTML_TEMPLATE.format(
        period=period,
        total_count=len(items),
        source_count=len(sources),
        collected_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        content=content,
    )

    return html_content


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

    # Markdownファイルを生成
    if not args.no_markdown:
        print("Markdownファイルを生成中...")
        md_content = generate_markdown(filtered_items, start_date, end_date)
        md_path = save_markdown(start_date, end_date, md_content)
        print(f"  → {md_path}")

    # HTMLファイルを生成
    if not args.no_html:
        print("HTMLファイルを生成中...")
        html_content = generate_html(filtered_items, start_date, end_date)
        html_path = save_html(start_date, end_date, html_content)
        print(f"  → {html_path} (GitHub Pages用)")

    print()
    print("完了しました！")


if __name__ == "__main__":
    main()
