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

# デフォルトの収集日数
DEFAULT_DAYS = 7


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


def parse_args():
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description="労務関連ニュースを収集してMarkdown形式で保存します"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"収集する日数（デフォルト: {DEFAULT_DAYS}日間）",
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

    # 週次レポートとして1ファイルに保存
    print("Markdownファイルを生成中...")
    content = generate_markdown(filtered_items, start_date, end_date)
    file_path = save_markdown(start_date, end_date, content)
    print(f"  → {file_path}")

    print()
    print("完了しました！")


if __name__ == "__main__":
    main()
