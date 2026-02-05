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
import json
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
# (ソース名, URL) のリスト形式。同じソース名は1つに統合される
RSS_FEEDS = [
    ("労働新聞社", "https://www.rodo.co.jp/feed/"),
    ("労務ドットコム", "https://roumu.com/feed/"),
    ("日本の人事部", "https://jinjibu.jp/rss/?mode=atcl"),
    ("日本の人事部", "https://jinjibu.jp/rss/?mode=news"),
    ("SATO PORTAL", "https://www.sato-group-sr.jp/portal/feed/"),
    ("弁護士ドットコム", "https://news.yahoo.co.jp/rss/media/bengocom/all.xml"),
    ("PSRネットワーク", "https://www.psrn.jp/index.xml"),
    ("PSRネットワーク", "https://www.psrn.jp/houkaisei/index.xml"),
]

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
    <title>iand weekly | {period}</title>
    <link rel="icon" type="image/png" href="favicon.png">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+JP:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            /* i-and.com inspired color scheme */
            --primary: #007cff;
            --primary-dark: #0066d6;
            --primary-light: #4da3ff;
            --primary-bg: #e6f2ff;
            --secondary: #233a5d;
            --accent: #007cff;
            --accent-bg: #e6f2ff;
            --success: #059669;
            --success-bg: #ecfdf5;
            --navy: #152638;
            --navy-light: #233a5d;
            --bg-page: #f5f7fa;
            --bg-white: #ffffff;
            --bg-gray: #eef2f7;
            --text-dark: #152638;
            --text-primary: #233a5d;
            --text-secondary: #4a5568;
            --text-muted: #718096;
            --border: #d8e1eb;
            --border-light: #eef2f7;
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-xl: 24px;
            --shadow-sm: 0 1px 3px rgba(21,38,56,0.08);
            --shadow-md: 0 4px 12px rgba(21,38,56,0.1);
            --shadow-lg: 0 8px 24px rgba(21,38,56,0.12);
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html {{ scroll-behavior: smooth; }}
        body {{
            font-family: 'Noto Sans JP', 'Inter', sans-serif;
            background: var(--bg-page);
            color: var(--text-primary);
            line-height: 1.7;
            font-size: 15px;
        }}

        /* ===== HEADER ===== */
        .header {{
            background: var(--navy);
            border-bottom: none;
            padding: 20px 32px;
            position: sticky;
            top: 0;
            z-index: 100;
        }}

        .header-inner {{
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 24px;
        }}

        .logo {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .logo-icon {{
            height: 36px;
            width: auto;
        }}

        .logo-text {{
            font-size: 1.25rem;
            font-weight: 700;
            color: #f5b800;
        }}

        .header-stats {{
            display: flex;
            gap: 24px;
        }}

        .header-stat {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: rgba(255,255,255,0.1);
            border-radius: 100px;
            font-size: 0.9rem;
        }}

        .header-stat-value {{
            font-weight: 700;
            color: #4da3ff;
        }}

        .header-stat-label {{
            color: rgba(255,255,255,0.7);
        }}

        .header-meta {{
            font-size: 0.85rem;
            color: rgba(255,255,255,0.8);
        }}

        /* ===== LAYOUT ===== */
        .layout {{
            max-width: 1400px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 280px 1fr;
            gap: 32px;
            padding: 32px;
            min-height: calc(100vh - 85px);
        }}

        /* ===== SIDEBAR ===== */
        .sidebar {{
            position: sticky;
            top: 117px;
            height: fit-content;
        }}

        .sidebar-section {{
            background: var(--bg-white);
            border-radius: var(--radius-lg);
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid var(--border);
        }}

        .sidebar-title {{
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-light);
        }}

        /* Filter Tabs */
        .filter-tabs {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}

        .filter-tab {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 14px;
            background: transparent;
            border: none;
            border-radius: var(--radius-md);
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 500;
            color: var(--text-secondary);
            transition: all 0.2s;
            text-align: left;
        }}

        .filter-tab:hover {{
            background: var(--bg-gray);
        }}

        .filter-tab.active {{
            background: var(--primary-bg);
            color: var(--primary);
        }}

        .filter-tab-icon {{
            width: 32px;
            height: 32px;
            border-radius: var(--radius-sm);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.95rem;
        }}

        .filter-tab-icon.all {{ background: var(--bg-gray); }}
        .filter-tab-icon.rodo {{ background: #dbeafe; }}
        .filter-tab-icon.roumu {{ background: #d1fae5; }}
        .filter-tab-icon.jinjibu {{ background: #ede9fe; }}
        .filter-tab-icon.sato {{ background: #fef3c7; }}
        .filter-tab-icon.bengo {{ background: #fce7f3; }}
        .filter-tab-icon.psr {{ background: #ccfbf1; }}

        .filter-tab-count {{
            margin-left: auto;
            background: var(--bg-gray);
            padding: 2px 10px;
            border-radius: 100px;
            font-size: 0.8rem;
            font-weight: 600;
        }}

        .filter-tab.active .filter-tab-count {{
            background: var(--primary);
            color: white;
        }}

        /* Date Navigation */
        .date-nav {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}

        .date-nav-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 14px;
            border-radius: var(--radius-md);
            text-decoration: none;
            color: var(--text-secondary);
            font-size: 0.9rem;
            transition: all 0.2s;
        }}

        .date-nav-item:hover {{
            background: var(--bg-gray);
            color: var(--text-primary);
        }}

        .date-nav-item.active {{
            background: var(--primary-bg);
            color: var(--primary);
            font-weight: 600;
        }}

        .date-nav-weekday {{
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-left: auto;
        }}

        /* ===== MAIN CONTENT ===== */
        .main-content {{
            min-width: 0;
        }}

        /* Summary Card */
        .summary-card {{
            background: linear-gradient(135deg, var(--primary-bg) 0%, var(--bg-white) 100%);
            border: 1px solid var(--border);
            border-radius: var(--radius-xl);
            padding: 28px;
            margin-bottom: 28px;
            display: grid;
            grid-template-columns: auto 1fr auto;
            gap: 20px;
            align-items: start;
        }}

        .summary-icon {{
            width: 56px;
            height: 56px;
            background: var(--navy);
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
        }}

        .summary-body {{ min-width: 0; }}

        .summary-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 16px;
        }}

        .summary-title {{
            font-size: 1.2rem;
            font-weight: 700;
            color: var(--text-dark);
        }}

        .ai-badge {{
            background: var(--bg-white);
            color: var(--primary);
            padding: 4px 12px;
            border-radius: 100px;
            font-size: 0.75rem;
            font-weight: 600;
            border: 1px solid var(--primary-light);
        }}

        .summary-content {{
            color: var(--text-secondary);
            font-size: 0.95rem;
            line-height: 1.8;
        }}

        .summary-content ul {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}

        .summary-content li {{
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 12px 16px;
            background: var(--bg-white);
            border-radius: var(--radius-md);
            border-left: 3px solid var(--success);
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .summary-content li:hover {{
            background: var(--success-bg);
            transform: translateX(4px);
        }}

        .summary-content li.active {{
            background: var(--success-bg);
            border-left-color: var(--primary);
            border-left-width: 4px;
        }}

        .summary-content li::before {{
            content: '✓';
            color: var(--success);
            font-weight: 700;
        }}

        /* Category-based summary styles */
        .summary-category {{
            margin-bottom: 20px;
            padding: 16px;
            border-radius: var(--radius-md);
            background: var(--bg-white);
        }}

        .summary-category:last-child {{
            margin-bottom: 0;
        }}

        .summary-category-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 12px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--border-light);
        }}

        .summary-category-icon {{
            font-size: 1.2rem;
        }}

        .summary-category-title {{
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--text-dark);
        }}

        .summary-category-law {{
            border-left: 4px solid #6366f1;
        }}

        .summary-category-law .summary-category-header {{
            border-bottom-color: #e0e7ff;
        }}

        .summary-category-law li {{
            border-left-color: #6366f1;
        }}

        .summary-category-law li::before {{
            color: #6366f1;
        }}

        .summary-category-court {{
            border-left: 4px solid #f59e0b;
        }}

        .summary-category-court .summary-category-header {{
            border-bottom-color: #fef3c7;
        }}

        .summary-category-court li {{
            border-left-color: #f59e0b;
        }}

        .summary-category-court li::before {{
            color: #f59e0b;
        }}

        .summary-category-subsidy {{
            border-left: 4px solid #10b981;
        }}

        .summary-category-subsidy .summary-category-header {{
            border-bottom-color: #d1fae5;
        }}

        .summary-category-subsidy li {{
            border-left-color: #10b981;
        }}

        .summary-category-subsidy li::before {{
            color: #10b981;
        }}

        .summary-category-other {{
            border-left: 4px solid #64748b;
        }}

        .summary-category-other .summary-category-header {{
            border-bottom-color: #e2e8f0;
        }}

        .summary-category-other li {{
            border-left-color: #64748b;
        }}

        .summary-category-other li::before {{
            color: #64748b;
        }}

        .summary-category ul {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin: 0;
            padding: 0;
        }}

        .summary-category li {{
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 10px 14px;
            background: var(--bg-gray);
            border-radius: var(--radius-sm);
            border-left: 3px solid var(--success);
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.9rem;
        }}

        .summary-category li:hover {{
            background: var(--primary-bg);
            transform: translateX(4px);
        }}

        .summary-category li.active {{
            background: var(--primary-bg);
            border-left-width: 4px;
        }}

        .summary-keywords {{
            display: inline-flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 8px;
        }}

        .summary-keyword {{
            background: var(--primary-bg);
            color: var(--primary);
            padding: 2px 10px;
            border-radius: 100px;
            font-size: 0.75rem;
            font-weight: 600;
        }}

        /* Highlighted news cards */
        .news-card.highlighted {{
            border-color: var(--primary);
            box-shadow: 0 0 0 2px var(--primary-bg), var(--shadow-md);
        }}

        .news-card.dimmed {{
            opacity: 0.4;
        }}

        /* News Grid */
        .news-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
        }}

        .news-card {{
            background: var(--bg-white);
            border-radius: var(--radius-lg);
            border: 1px solid var(--border);
            overflow: hidden;
            transition: all 0.25s ease;
            display: flex;
            flex-direction: column;
        }}

        .news-card:hover {{
            box-shadow: var(--shadow-lg);
            transform: translateY(-4px);
            border-color: var(--primary-light);
        }}

        .news-card-header {{
            padding: 16px 20px;
            background: var(--bg-gray);
            display: flex;
            align-items: center;
            gap: 12px;
            border-bottom: 1px solid var(--border-light);
        }}

        .news-card-source {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-secondary);
        }}

        .news-card-source-icon {{
            width: 28px;
            height: 28px;
            border-radius: var(--radius-sm);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.85rem;
        }}

        .news-card-source-icon.rodo {{ background: #dbeafe; }}
        .news-card-source-icon.roumu {{ background: #d1fae5; }}
        .news-card-source-icon.jinjibu {{ background: #ede9fe; }}

        .news-card-date {{
            margin-left: auto;
            font-size: 0.8rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 4px;
        }}

        .news-card-body {{
            padding: 20px;
            flex: 1;
            display: flex;
            flex-direction: column;
        }}

        .news-card-body a {{
            text-decoration: none;
            color: inherit;
            display: flex;
            flex-direction: column;
            height: 100%;
        }}

        .news-card-title {{
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-primary);
            line-height: 1.6;
            margin-bottom: 12px;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .news-card:hover .news-card-title {{
            color: var(--primary);
        }}

        .news-card-summary {{
            font-size: 0.875rem;
            color: var(--text-muted);
            line-height: 1.65;
            flex: 1;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .news-card-footer {{
            margin-top: auto;
            padding-top: 16px;
            border-top: 1px solid var(--border-light);
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .news-card-time {{
            font-size: 0.8rem;
            color: var(--text-muted);
        }}

        .news-card-arrow {{
            margin-left: auto;
            color: var(--primary);
            font-size: 1.1rem;
            opacity: 0;
            transform: translateX(-8px);
            transition: all 0.2s;
        }}

        .news-card:hover .news-card-arrow {{
            opacity: 1;
            transform: translateX(0);
        }}

        /* Date Section */
        .date-section {{
            margin-bottom: 32px;
        }}

        .date-section-header {{
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 2px solid var(--border);
        }}

        .date-section-icon {{
            width: 48px;
            height: 48px;
            background: var(--navy);
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
            color: white;
        }}

        .date-section-info {{
            flex: 1;
        }}

        .date-section-date {{
            font-size: 1.2rem;
            font-weight: 700;
            color: var(--text-dark);
        }}

        .date-section-weekday {{
            font-size: 0.9rem;
            color: var(--text-muted);
        }}

        .date-section-count {{
            background: var(--navy);
            color: white;
            padding: 6px 16px;
            border-radius: 100px;
            font-size: 0.875rem;
            font-weight: 600;
        }}

        /* Archive Section */
        .archive-section {{
            background: var(--bg-white);
            border-radius: var(--radius-xl);
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
            width: 44px;
            height: 44px;
            background: var(--accent-bg);
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
        }}

        .archive-title {{
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--text-dark);
        }}

        .archive-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }}

        .archive-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 18px;
            background: var(--bg-gray);
            border-radius: var(--radius-md);
            text-decoration: none;
            color: var(--text-secondary);
            font-size: 0.9rem;
            font-weight: 500;
            transition: all 0.2s;
            border: 2px solid transparent;
        }}

        .archive-item:hover {{
            background: var(--primary-bg);
            border-color: var(--primary);
            color: var(--primary);
        }}

        .archive-item.current {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }}

        .archive-item-icon {{ font-size: 1rem; }}

        /* Footer */
        footer {{
            text-align: center;
            padding: 48px 32px;
            color: rgba(255,255,255,0.7);
            font-size: 0.875rem;
            background: var(--navy);
            margin-top: 48px;
        }}

        .footer-brand {{
            font-size: 1.25rem;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 8px;
        }}

        /* ===== RESPONSIVE ===== */
        @media (max-width: 1024px) {{
            .layout {{
                grid-template-columns: 1fr;
            }}

            .sidebar {{
                position: static;
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 16px;
            }}

            .sidebar-section {{
                margin-bottom: 0;
            }}
        }}

        @media (max-width: 768px) {{
            .header {{
                padding: 14px 16px;
            }}

            .header-inner {{
                flex-wrap: wrap;
            }}

            .header-stats {{
                display: none;
            }}

            .header-meta {{
                font-size: 0.75rem;
            }}

            .logo-text {{
                font-size: 1.05rem;
            }}

            .layout {{
                padding: 16px;
                gap: 16px;
            }}

            .sidebar {{
                grid-template-columns: 1fr;
            }}

            .sidebar-section {{
                padding: 14px;
            }}

            .filter-tab {{
                padding: 10px 12px;
                font-size: 0.85rem;
            }}

            .news-grid {{
                grid-template-columns: 1fr;
                gap: 14px;
            }}

            .summary-card {{
                grid-template-columns: 1fr;
                padding: 18px;
                border-radius: var(--radius-lg);
            }}

            .summary-icon {{
                display: none;
            }}

            .summary-title {{
                font-size: 1rem;
            }}

            .summary-content {{
                font-size: 0.88rem;
            }}

            .summary-category {{
                padding: 12px;
                margin-bottom: 14px;
            }}

            .summary-category li {{
                padding: 8px 10px;
                font-size: 0.83rem;
                line-height: 1.6;
            }}

            .summary-category-title {{
                font-size: 0.88rem;
            }}

            .summary-keyword {{
                font-size: 0.7rem;
                padding: 1px 8px;
            }}

            .date-section-header {{
                gap: 10px;
                margin-bottom: 14px;
                padding-bottom: 12px;
            }}

            .date-section-icon {{
                width: 36px;
                height: 36px;
                font-size: 1rem;
            }}

            .date-section-date {{
                font-size: 1rem;
            }}

            .news-card-header {{
                padding: 12px 14px;
            }}

            .news-card-body {{
                padding: 14px;
            }}

            .news-card-title {{
                font-size: 0.92rem;
                line-height: 1.5;
            }}

            .news-card-summary {{
                font-size: 0.82rem;
                -webkit-line-clamp: 2;
            }}

            .archive-section {{
                padding: 18px;
            }}

            .archive-list {{
                gap: 8px;
            }}

            .archive-item {{
                padding: 10px 14px;
                font-size: 0.82rem;
            }}

            footer {{
                padding: 32px 16px;
            }}
        }}

        /* ===== ANIMATIONS ===== */
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(16px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .news-card {{
            animation: fadeIn 0.4s ease both;
        }}

        .date-section:nth-child(1) .news-card {{ animation-delay: 0s; }}
        .date-section:nth-child(2) .news-card {{ animation-delay: 0.05s; }}
        .date-section:nth-child(3) .news-card {{ animation-delay: 0.1s; }}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-inner">
            <div class="logo">
                <img class="logo-icon" src="logo.png" alt="iand">
                <div class="logo-text">iand weekly</div>
            </div>
            <div class="header-stats">
                <div class="header-stat">
                    <span class="header-stat-value">{total_count}</span>
                    <span class="header-stat-label">ニュース</span>
                </div>
                <div class="header-stat">
                    <span class="header-stat-value">{source_count}</span>
                    <span class="header-stat-label">ソース</span>
                </div>
                <div class="header-stat">
                    <span class="header-stat-value">{day_count}</span>
                    <span class="header-stat-label">日間</span>
                </div>
            </div>
            <div class="header-meta">
                {period}<br>
                <small>更新: {collected_at}</small>
                <div style="margin-top:6px"><a href="summary.html" style="color:rgba(255,255,255,0.8);text-decoration:none;font-size:0.8rem;padding:4px 12px;border:1px solid rgba(255,255,255,0.3);border-radius:100px;">🤖 AIサマリー一覧</a></div>
            </div>
        </div>
    </header>

    <div class="layout">
        <aside class="sidebar">
            <div class="sidebar-section">
                <div class="sidebar-title">ソースで絞り込み</div>
                <div class="filter-tabs">
                    <button class="filter-tab active" data-filter="all">
                        <span class="filter-tab-icon all">📋</span>
                        すべて
                        <span class="filter-tab-count">{total_count}</span>
                    </button>
                    {source_filters}
                </div>
            </div>

            <div class="sidebar-section">
                <div class="sidebar-title">日付で移動</div>
                <nav class="date-nav">
                    {date_nav}
                </nav>
            </div>
        </aside>

        <main class="main-content">
            {summary_section}
            {content}
            {archive_section}
        </main>
    </div>

    <footer>
        <div class="footer-brand">iand weekly</div>
        <p>RSSフィードから自動収集・更新</p>
    </footer>

    <script>
        // Source filtering
        document.querySelectorAll('.filter-tab').forEach(tab => {{
            tab.addEventListener('click', () => {{
                // Clear topic selection
                document.querySelectorAll('.summary-content li').forEach(li => li.classList.remove('active'));
                document.querySelectorAll('.news-card').forEach(card => {{
                    card.classList.remove('highlighted', 'dimmed');
                }});

                document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                const filter = tab.dataset.filter;
                document.querySelectorAll('.news-card').forEach(card => {{
                    if (filter === 'all' || card.dataset.source === filter) {{
                        card.style.display = '';
                    }} else {{
                        card.style.display = 'none';
                    }}
                }});
            }});
        }});

        // Smooth scroll for date nav
        document.querySelectorAll('.date-nav-item').forEach(link => {{
            link.addEventListener('click', (e) => {{
                document.querySelectorAll('.date-nav-item').forEach(l => l.classList.remove('active'));
                link.classList.add('active');
            }});
        }});

        // Topic click to highlight related articles
        document.querySelectorAll('.summary-content li').forEach(item => {{
            item.addEventListener('click', () => {{
                const keywords = item.dataset.keywords;
                if (!keywords) return;

                const keywordList = keywords.split(',').map(k => k.trim().toLowerCase());
                const isActive = item.classList.contains('active');

                // Reset all
                document.querySelectorAll('.summary-content li').forEach(li => li.classList.remove('active'));
                document.querySelectorAll('.news-card').forEach(card => {{
                    card.classList.remove('highlighted', 'dimmed');
                    card.style.display = '';
                }});

                // Reset source filter to "all"
                document.querySelectorAll('.filter-tab').forEach(t => {{
                    t.classList.toggle('active', t.dataset.filter === 'all');
                }});

                if (isActive) return; // Toggle off

                item.classList.add('active');

                // Find matching cards
                let hasMatch = false;
                document.querySelectorAll('.news-card').forEach(card => {{
                    const title = card.querySelector('.news-card-title')?.textContent.toLowerCase() || '';
                    const summary = card.querySelector('.news-card-summary')?.textContent.toLowerCase() || '';
                    const content = title + ' ' + summary;

                    const matches = keywordList.some(kw => content.includes(kw));
                    if (matches) {{
                        card.classList.add('highlighted');
                        hasMatch = true;
                    }} else {{
                        card.classList.add('dimmed');
                    }}
                }});

                // Scroll to first match
                if (hasMatch) {{
                    const firstMatch = document.querySelector('.news-card.highlighted');
                    if (firstMatch) {{
                        firstMatch.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    }}
                }}
            }});
        }});
    </script>
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
    """AIを使って週次ニュースサマリーを生成（カテゴリー別）"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not ANTHROPIC_AVAILABLE:
        print("  警告: anthropicパッケージがインストールされていません")
        return None

    if not api_key:
        print("  警告: ANTHROPIC_API_KEYが設定されていません")
        return None

    # ニュースをソース付きでテキストにまとめる
    news_text = ""
    for item in items[:50]:  # 最大50件に制限（トークン節約）
        news_text += f"- 【{item.source}】{item.title}\n"

    prompt = f"""あなたは企業の人事・労務担当者向けに情報を提供する専門家です。
以下は今週の労務関連ニュースの一覧です。これを分析し、カテゴリー別に重要トピックをまとめてください。

【今週のニュース一覧】
{news_text}

【分析の観点】
1. 複数のニュースソースで取り上げられている話題は、今週の労務業界で特に重要なトピックです。優先的に取り上げてください。
2. 法改正、制度変更、判例など、企業の実務に直接影響するものを重視してください。
3. 各トピックについて、企業への影響や必要な対応を具体的に述べてください。

【出力形式】
以下のカテゴリーごとに、該当するトピックがあれば記載してください。該当するトピックがないカテゴリーは省略してください。

## 📜 法改正・制度変更
- トピック名 … 説明文。[関連キーワード: キーワード1, キーワード2]

## ⚖️ 裁判例・判例
- トピック名 … 説明文。[関連キーワード: キーワード1, キーワード2]

## 💰 助成金・補助金
- トピック名 … 説明文。[関連キーワード: キーワード1, キーワード2]

## 📌 その他重要トピック
- トピック名 … 説明文。[関連キーワード: キーワード1, キーワード2]

【注意事項】
- 必ず「## 📜」「## ⚖️」「## 💰」「## 📌」の見出し形式を使用してください
- 各カテゴリーには1〜3つのトピックを記載
- 該当トピックがないカテゴリーは見出しごと省略
- Markdown記号（**、##以外の#、>、``など）は使わないでください。読みやすい自然な日本語で書いてください
- トピック名の後は「 … 」（スペース三点リーダースペース）で区切り、続けて説明を書いてください
- 専門用語は避け、わかりやすい表現を使用
- 関連キーワードは行末に [関連キーワード: ...] の形式で付けてください。ニュース記事を検索するための単語です（2〜4個）
- 日本語で回答"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
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
    elif "SATO" in source:
        return "sato"
    elif "弁護士ドットコム" in source:
        return "bengo"
    elif "PSR" in source:
        return "psr"
    return "default"


def get_source_emoji(source: str) -> str:
    """ソース名から絵文字を取得"""
    if "労働新聞" in source:
        return "📰"
    elif "労務ドットコム" in source or "roumu" in source.lower():
        return "💼"
    elif "人事部" in source:
        return "👥"
    elif "SATO" in source:
        return "🏢"
    elif "弁護士ドットコム" in source:
        return "⚖️"
    elif "PSR" in source:
        return "📋"
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

    # 日付ごとにグループ化
    by_date = group_by_date(items)

    # ソースごとにカウント
    source_counts = defaultdict(int)
    for item in items:
        source_counts[item.source] += 1

    # ソース数をカウント
    sources = set(item.source for item in items)

    # 日数をカウント
    day_count = len(by_date)

    # サマリーセクションを生成（カテゴリー別）
    if summary:
        lines = summary.split("\n")

        # カテゴリー定義
        categories = {
            "📜 法改正・制度変更": {"icon": "📜", "color": "law", "items": []},
            "⚖️ 裁判例・判例": {"icon": "⚖️", "color": "court", "items": []},
            "💰 助成金・補助金": {"icon": "💰", "color": "subsidy", "items": []},
            "📌 その他重要トピック": {"icon": "📌", "color": "other", "items": []},
        }

        current_category = None

        def parse_summary_line(line: str) -> tuple[str, list[str]]:
            """サマリー行からテキストとキーワードを抽出し、Markdown記号を除去"""
            keywords = []
            # [関連キーワード: ...] パターンを検索
            keyword_match = re.search(r'\[関連キーワード[:：]\s*([^\]]+)\]', line)
            if keyword_match:
                keywords = [k.strip() for k in keyword_match.group(1).split(',')]
                line = line[:keyword_match.start()].strip()
            # Markdown記号を除去（**太字**、*斜体*、`コード`）
            line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
            line = re.sub(r'\*(.+?)\*', r'\1', line)
            line = re.sub(r'`(.+?)`', r'\1', line)
            # 「：」の前後のスペースを正規化
            line = line.strip()
            return line, keywords

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # カテゴリー見出しをチェック
            if line.startswith("## "):
                header_text = line[3:].strip()
                for cat_name in categories.keys():
                    if cat_name in header_text or header_text in cat_name:
                        current_category = cat_name
                        break
                continue

            # 現在のカテゴリーがあれば、アイテムを追加
            if current_category:
                item_text = None
                if line.startswith("- ") or line.startswith("・") or line.startswith("• "):
                    item_text = line.lstrip("-・• ").strip()
                elif line.startswith("* "):
                    item_text = line.lstrip("* ").strip()
                elif not line.startswith("#") and not line.startswith("**"):
                    match = re.match(r'^\d+[\.\)]\s*(.+)$', line)
                    if match:
                        item_text = match.group(1)

                if item_text:
                    text, keywords = parse_summary_line(item_text)
                    if text:
                        categories[current_category]["items"].append({
                            "text": text,
                            "keywords": keywords
                        })

        # カテゴリー別HTMLを生成
        category_sections = []
        for cat_name, cat_data in categories.items():
            if not cat_data["items"]:
                continue

            items_html = []
            for item in cat_data["items"]:
                keywords_attr = escape_html(','.join(item["keywords"])) if item["keywords"] else ''
                keywords_html = ''
                if item["keywords"]:
                    keyword_badges = ''.join(
                        f'<span class="summary-keyword">{escape_html(k)}</span>'
                        for k in item["keywords"]
                    )
                    keywords_html = f'<div class="summary-keywords">{keyword_badges}</div>'
                items_html.append(
                    f'<li data-keywords="{keywords_attr}">'
                    f'<div><div>{escape_html(item["text"])}</div>{keywords_html}</div>'
                    f'</li>'
                )

            category_sections.append(f'''
                <div class="summary-category summary-category-{cat_data["color"]}">
                    <div class="summary-category-header">
                        <span class="summary-category-icon">{cat_data["icon"]}</span>
                        <span class="summary-category-title">{escape_html(cat_name.split(" ", 1)[1] if " " in cat_name else cat_name)}</span>
                    </div>
                    <ul>{"".join(items_html)}</ul>
                </div>
            ''')

        if category_sections:
            summary_content = "".join(category_sections)
        else:
            # フォールバック: 旧形式の処理
            list_items = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                item_text = None
                if line.startswith("- ") or line.startswith("・") or line.startswith("• "):
                    item_text = line.lstrip("-・• ").strip()
                elif line.startswith("* "):
                    item_text = line.lstrip("* ").strip()
                if item_text:
                    text, keywords = parse_summary_line(item_text)
                    if text:
                        keywords_attr = escape_html(','.join(keywords)) if keywords else ''
                        keywords_html = ''
                        if keywords:
                            keyword_badges = ''.join(
                                f'<span class="summary-keyword">{escape_html(k)}</span>'
                                for k in keywords
                            )
                            keywords_html = f'<div class="summary-keywords">{keyword_badges}</div>'
                        list_items.append(
                            f'<li data-keywords="{keywords_attr}">'
                            f'<div><div>{escape_html(text)}</div>{keywords_html}</div>'
                            f'</li>'
                        )
            if list_items:
                summary_content = "<ul>" + "".join(list_items) + "</ul>"
            else:
                paragraphs = [f"<p>{escape_html(p.strip())}</p>" for p in summary.split("\n\n") if p.strip()]
                summary_content = "".join(paragraphs) if paragraphs else f"<p>{escape_html(summary)}</p>"

        summary_section = f'''
            <div class="summary-card">
                <div class="summary-icon">🤖</div>
                <div class="summary-body">
                    <div class="summary-header">
                        <div class="summary-title">今週のポイント</div>
                        <div class="ai-badge">✨ AI Generated</div>
                    </div>
                    <div class="summary-content">
                        {summary_content}
                    </div>
                </div>
            </div>
        '''
    else:
        summary_section = ""

    # ソースフィルタータブを生成
    source_filters = []
    for source, count in sorted(source_counts.items()):
        icon_class = get_source_icon_class(source)
        emoji = get_source_emoji(source)
        filter_id = icon_class if icon_class != "default" else source.lower().replace(" ", "-")
        source_filters.append(
            f'<button class="filter-tab" data-filter="{filter_id}">'
            f'<span class="filter-tab-icon {icon_class}">{emoji}</span>'
            f'{escape_html(source)}'
            f'<span class="filter-tab-count">{count}</span>'
            f'</button>'
        )
    source_filters_html = "\n".join(source_filters)

    # 日付ナビゲーションを生成
    date_nav_items = []
    for i, date_str in enumerate(sorted(by_date.keys(), reverse=True)):
        weekday = get_weekday_jp(date_str)
        active_class = " active" if i == 0 else ""
        date_nav_items.append(
            f'<a href="#date-{date_str}" class="date-nav-item{active_class}">'
            f'📅 {date_str}'
            f'<span class="date-nav-weekday">{weekday}</span>'
            f'</a>'
        )
    date_nav_html = "\n".join(date_nav_items)

    # コンテンツ生成（カードグリッド形式）
    content_parts = []

    for date_str in sorted(by_date.keys(), reverse=True):
        date_items = by_date[date_str]
        weekday = get_weekday_jp(date_str)

        content_parts.append(f'<section class="date-section" id="date-{date_str}">')
        content_parts.append(f'<div class="date-section-header">')
        content_parts.append(f'<div class="date-section-icon">📅</div>')
        content_parts.append(f'<div class="date-section-info">')
        content_parts.append(f'<div class="date-section-date">{date_str}</div>')
        content_parts.append(f'<div class="date-section-weekday">{weekday}曜日</div>')
        content_parts.append(f'</div>')
        content_parts.append(f'<div class="date-section-count">{len(date_items)}件</div>')
        content_parts.append(f'</div>')

        content_parts.append(f'<div class="news-grid">')

        for item in sorted(date_items, key=lambda x: x.published, reverse=True):
            time_str = item.published.strftime("%H:%M")
            date_display = item.published.strftime("%m/%d")
            title_escaped = escape_html(item.title)
            link_escaped = escape_html(item.link)
            summary_escaped = escape_html(item.summary) if item.summary else ""
            icon_class = get_source_icon_class(item.source)
            emoji = get_source_emoji(item.source)
            filter_id = icon_class if icon_class != "default" else item.source.lower().replace(" ", "-")

            short_summary = (
                summary_escaped[:120] + "..."
                if len(summary_escaped) > 120
                else summary_escaped
            )

            content_parts.append(f'<article class="news-card" data-source="{filter_id}">')
            content_parts.append(f'<div class="news-card-header">')
            content_parts.append(f'<div class="news-card-source">')
            content_parts.append(f'<span class="news-card-source-icon {icon_class}">{emoji}</span>')
            content_parts.append(f'{escape_html(item.source)}')
            content_parts.append(f'</div>')
            content_parts.append(f'<span class="news-card-date">🕐 {time_str}</span>')
            content_parts.append(f'</div>')
            content_parts.append(f'<div class="news-card-body">')
            content_parts.append(f'<a href="{link_escaped}" target="_blank" rel="noopener">')
            content_parts.append(f'<h3 class="news-card-title">{title_escaped}</h3>')
            if short_summary:
                content_parts.append(f'<p class="news-card-summary">{short_summary}</p>')
            content_parts.append(f'<div class="news-card-footer">')
            content_parts.append(f'<span class="news-card-time">{date_display} {time_str}</span>')
            content_parts.append(f'<span class="news-card-arrow">→</span>')
            content_parts.append(f'</div>')
            content_parts.append(f'</a>')
            content_parts.append(f'</div>')
            content_parts.append(f'</article>')

        content_parts.append(f'</div>')
        content_parts.append(f'</section>')

    content = "\n".join(content_parts)

    # アーカイブセクションを生成
    if archives and len(archives) > 0:
        archive_items = []
        for filename, period_label, is_current in archives:
            current_class = " current" if is_current else ""
            archive_items.append(
                f'<a href="{filename}" class="archive-item{current_class}">'
                f'<span class="archive-item-icon">📅</span>'
                f'{period_label}'
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
        source_filters=source_filters_html,
        date_nav=date_nav_html,
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


def save_summary(start_date: datetime, end_date: datetime, summary: str) -> Path:
    """AIサマリーをJSONファイルに保存"""
    summaries_dir = DOCS_DIR / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    data = {
        "period_start": start_str,
        "period_end": end_str,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": summary,
    }

    file_path = summaries_dir / f"{start_str}_{end_str}.json"
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return file_path


def load_all_summaries() -> list[dict]:
    """保存済みの全サマリーを読み込む（新しい順）"""
    summaries_dir = DOCS_DIR / "summaries"
    if not summaries_dir.exists():
        return []

    summaries = []
    for json_file in sorted(summaries_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            summaries.append(data)
        except (json.JSONDecodeError, KeyError):
            continue
    return summaries


def parse_summary_to_categories(summary_text: str) -> list[dict]:
    """サマリーテキストをカテゴリー構造にパース"""
    categories_def = {
        "📜 法改正・制度変更": {"icon": "📜", "color": "law"},
        "⚖️ 裁判例・判例": {"icon": "⚖️", "color": "court"},
        "💰 助成金・補助金": {"icon": "💰", "color": "subsidy"},
        "📌 その他重要トピック": {"icon": "📌", "color": "other"},
    }

    lines = summary_text.split("\n")
    current_category = None
    result = []
    current_items = []

    def clean_text(text):
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        keyword_match = re.search(r'\[関連キーワード[:：]\s*([^\]]+)\]', text)
        if keyword_match:
            text = text[:keyword_match.start()].strip()
        return text.strip()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("## "):
            if current_category and current_items:
                result.append({
                    "name": current_category,
                    **categories_def.get(current_category, {"icon": "📌", "color": "other"}),
                    "items": current_items,
                })
            header_text = line[3:].strip()
            current_category = None
            current_items = []
            for cat_name in categories_def.keys():
                if cat_name in header_text or header_text in cat_name:
                    current_category = cat_name
                    break
            continue

        if current_category:
            item_text = None
            if line.startswith("- ") or line.startswith("・") or line.startswith("• "):
                item_text = line.lstrip("-・• ").strip()
            elif line.startswith("* "):
                item_text = line.lstrip("* ").strip()
            if item_text:
                current_items.append(clean_text(item_text))

    if current_category and current_items:
        result.append({
            "name": current_category,
            **categories_def.get(current_category, {"icon": "📌", "color": "other"}),
            "items": current_items,
        })

    # カテゴリーなしのフォールバック
    if not result:
        items = []
        for line in lines:
            line = line.strip()
            if line.startswith("- ") or line.startswith("・"):
                items.append(clean_text(line.lstrip("-・• ").strip()))
        if items:
            result.append({"name": "トピック", "icon": "📌", "color": "other", "items": items})

    return result


SUMMARY_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIサマリー一覧 | iand weekly</title>
    <link rel="icon" type="image/png" href="favicon.png">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+JP:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #007cff;
            --primary-dark: #0066d6;
            --primary-light: #4da3ff;
            --primary-bg: #e6f2ff;
            --navy: #152638;
            --navy-light: #233a5d;
            --bg-page: #f5f7fa;
            --bg-white: #ffffff;
            --bg-gray: #eef2f7;
            --text-dark: #152638;
            --text-primary: #233a5d;
            --text-secondary: #4a5568;
            --text-muted: #718096;
            --border: #d8e1eb;
            --border-light: #eef2f7;
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-xl: 24px;
            --shadow-sm: 0 1px 3px rgba(21,38,56,0.08);
            --shadow-md: 0 4px 12px rgba(21,38,56,0.1);
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html {{ scroll-behavior: smooth; }}
        body {{
            font-family: 'Noto Sans JP', 'Inter', sans-serif;
            background: var(--bg-page);
            color: var(--text-primary);
            line-height: 1.7;
            font-size: 15px;
        }}

        .header {{
            background: var(--navy);
            padding: 20px 24px;
            position: sticky;
            top: 0;
            z-index: 100;
        }}

        .header-inner {{
            max-width: 900px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
        }}

        .logo {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .logo-icon {{
            width: 40px;
            height: 40px;
            background: var(--primary);
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
            color: #fff;
        }}

        .logo-text {{
            font-size: 1.15rem;
            font-weight: 700;
            color: #ffffff;
        }}

        .back-link {{
            color: rgba(255,255,255,0.8);
            text-decoration: none;
            font-size: 0.85rem;
            padding: 6px 14px;
            border-radius: 100px;
            border: 1px solid rgba(255,255,255,0.2);
            transition: all 0.2s;
        }}

        .back-link:hover {{
            background: rgba(255,255,255,0.1);
            color: #fff;
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 32px 24px;
        }}

        .page-title {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-dark);
            margin-bottom: 8px;
        }}

        .page-subtitle {{
            color: var(--text-muted);
            font-size: 0.9rem;
            margin-bottom: 32px;
        }}

        .week-card {{
            background: var(--bg-white);
            border: 1px solid var(--border);
            border-radius: var(--radius-xl);
            margin-bottom: 24px;
            overflow: hidden;
        }}

        .week-card-header {{
            background: var(--bg-gray);
            padding: 16px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border-light);
            cursor: pointer;
        }}

        .week-card-header:hover {{
            background: var(--primary-bg);
        }}

        .week-period {{
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--text-dark);
        }}

        .week-meta {{
            font-size: 0.8rem;
            color: var(--text-muted);
        }}

        .week-card-body {{
            padding: 20px 24px;
        }}

        .cat-section {{
            margin-bottom: 16px;
            padding: 14px 16px;
            border-radius: var(--radius-md);
            background: var(--bg-gray);
        }}

        .cat-section:last-child {{
            margin-bottom: 0;
        }}

        .cat-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
            font-size: 0.9rem;
            font-weight: 700;
            color: var(--text-dark);
        }}

        .cat-law {{ border-left: 4px solid #6366f1; }}
        .cat-court {{ border-left: 4px solid #f59e0b; }}
        .cat-subsidy {{ border-left: 4px solid #10b981; }}
        .cat-other {{ border-left: 4px solid #64748b; }}

        .cat-item {{
            color: var(--text-secondary);
            font-size: 0.88rem;
            line-height: 1.7;
            padding: 6px 0;
        }}

        .cat-item + .cat-item {{
            border-top: 1px solid var(--border-light);
        }}

        .week-link {{
            display: inline-block;
            margin-top: 12px;
            color: var(--primary);
            text-decoration: none;
            font-size: 0.85rem;
            font-weight: 600;
        }}

        .week-link:hover {{
            text-decoration: underline;
        }}

        .empty-state {{
            text-align: center;
            padding: 60px 24px;
            color: var(--text-muted);
        }}

        footer {{
            text-align: center;
            padding: 48px 24px;
            color: rgba(255,255,255,0.7);
            font-size: 0.875rem;
            background: var(--navy);
            margin-top: 48px;
        }}

        .footer-brand {{
            font-size: 1.1rem;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 8px;
        }}

        @media (max-width: 640px) {{
            .container {{
                padding: 20px 16px;
            }}

            .page-title {{
                font-size: 1.2rem;
            }}

            .week-card-header {{
                padding: 14px 16px;
                flex-direction: column;
                align-items: flex-start;
                gap: 4px;
            }}

            .week-card-body {{
                padding: 16px;
            }}

            .cat-section {{
                padding: 12px;
            }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-inner">
            <div class="logo">
                <img class="logo-icon" src="logo.png" alt="iand" style="height:32px;width:auto;">
                <div class="logo-text" style="color:#f5b800;">iand weekly</div>
            </div>
            <a href="index.html" class="back-link">← 最新ニュースへ</a>
        </div>
    </header>

    <div class="container">
        <h1 class="page-title">AIサマリー 週次まとめ</h1>
        <p class="page-subtitle">毎週のAI分析レポートを振り返ることができます</p>

        {content}
    </div>

    <footer>
        <div class="footer-brand">iand weekly</div>
        <p>RSSフィードから自動収集・AI分析</p>
    </footer>
</body>
</html>
"""


def generate_summary_page() -> Path:
    """AIサマリー一覧ページを生成"""
    summaries = load_all_summaries()

    if not summaries:
        content = '<div class="empty-state"><p>まだサマリーがありません。</p></div>'
    else:
        cards = []
        for s in summaries:
            period = f'{s["period_start"]} 〜 {s["period_end"]}'
            generated = s.get("generated_at", "")
            archive_file = f'{s["period_start"]}_{s["period_end"]}.html'

            categories = parse_summary_to_categories(s["summary"])

            cat_html_parts = []
            for cat in categories:
                items_html = "".join(
                    f'<div class="cat-item">{escape_html(item)}</div>'
                    for item in cat["items"]
                )
                cat_html_parts.append(
                    f'<div class="cat-section cat-{cat["color"]}">'
                    f'<div class="cat-header">{cat["icon"]} {escape_html(cat["name"].split(" ", 1)[1] if " " in cat["name"] else cat["name"])}</div>'
                    f'{items_html}'
                    f'</div>'
                )

            cats_html = "".join(cat_html_parts)

            cards.append(
                f'<div class="week-card">'
                f'<div class="week-card-header">'
                f'<span class="week-period">{period}</span>'
                f'<span class="week-meta">生成: {generated}</span>'
                f'</div>'
                f'<div class="week-card-body">'
                f'{cats_html}'
                f'<a href="{archive_file}" class="week-link">この週のニュース一覧を見る →</a>'
                f'</div>'
                f'</div>'
            )
        content = "\n".join(cards)

    html_content = SUMMARY_PAGE_TEMPLATE.format(content=content)
    page_path = DOCS_DIR / "summary.html"
    page_path.write_text(html_content, encoding="utf-8")
    return page_path


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
    for source_name, url in RSS_FEEDS:
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
            # サマリーをJSONファイルに保存
            summary_path = save_summary(start_date, end_date, summary)
            print(f"  → サマリー保存: {summary_path}")
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

        # AIサマリー一覧ページを生成
        summary_page_path = generate_summary_page()
        print(f"  → {summary_page_path} (サマリー一覧)")

    print()
    print("完了しました！")


if __name__ == "__main__":
    main()
