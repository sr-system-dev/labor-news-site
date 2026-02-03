# Weekly SR by iand 設計・構成書

## 1. システム概要

本システムは、労務・人事関連のニュースを自動収集し、AIによるサマリーを付けてWebページとして公開するシステムです。Cloudflare Access による認証機能により、許可されたユーザーのみが閲覧可能です。

### 利用している主要サービス・技術

| カテゴリ | サービス/技術名 | 提供元 | 用途 |
|---------|----------------|--------|------|
| コード管理 | **GitHub** | GitHub, Inc. | プログラムの保存・バージョン管理 |
| 自動実行 | **GitHub Actions** | GitHub, Inc. | 毎週月曜日の自動ニュース収集 |
| Webページ公開 | **Cloudflare Pages** | Cloudflare, Inc. | 収集したニュースのWeb公開 |
| アクセス制御 | **Cloudflare Access** | Cloudflare, Inc. | 特定ユーザーのみアクセス許可 |
| 機密情報管理 | **GitHub Secrets** | GitHub, Inc. | APIキーの安全な保管 |
| AI（サマリー生成） | **Claude API** | Anthropic, Inc. | ニュースの要約生成 |
| AIモデル | **Claude Sonnet 4** | Anthropic, Inc. | 実際に要約を行うAIモデル |
| プログラミング言語 | **Python 3.11** | Python Software Foundation | システムの開発言語 |

---

## 2. システム構成図

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  【情報源】RSSフィード                                                   │
│                                                                         │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐              │
│  │ 労働新聞社 │ │労務ドットコム│ │日本の人事部│ │SATO PORTAL│              │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘              │
│        │            │            │            │                       │
│  ┌─────┴─────┐ ┌─────┴─────┐                                          │
│  │弁護士ドットコム│ │PSRネットワーク│                                          │
│  └─────┬─────┘ └─────┬─────┘                                          │
│        └──────┬──────┘                                                │
│               │                                                        │
│               ▼                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                                                                   │  │
│  │  【GitHub Actions】自動実行環境                                   │  │
│  │                                                                   │  │
│  │   毎週月曜日 9:00（日本時間）に自動起動                          │  │
│  │                                                                   │  │
│  │   ┌───────────────────────────────────────────────────────────┐  │  │
│  │   │                                                             │  │  │
│  │   │  collect_news.py （Python スクリプト）                      │  │  │
│  │   │                                                             │  │  │
│  │   │  使用ライブラリ:                                            │  │  │
│  │   │   • feedparser - RSSフィードの解析                         │  │  │
│  │   │   • anthropic  - Claude API との通信                        │  │  │
│  │   │                                                             │  │  │
│  │   └───────────────────────────────────────────────────────────┘  │  │
│  │                              │                                    │  │
│  └──────────────────────────────┼────────────────────────────────────┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                                                                   │   │
│  │  【Anthropic Claude API】                                        │   │
│  │                                                                   │   │
│  │   モデル: Claude Sonnet 4 (claude-sonnet-4-20250514)             │   │
│  │   用途: 週間ニュースのサマリー（要約）生成                        │   │
│  │                                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                 │                                       │
│                                 ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                                                                   │   │
│  │  【Cloudflare Pages】Webページ公開                               │   │
│  │                                                                   │   │
│  │   GitHub リポジトリと連携し、自動デプロイ                         │   │
│  │                                                                   │   │
│  │   出力ファイル:                                                   │   │
│  │    • docs/index.html（メインページ）                             │   │
│  │    • docs/YYYY-MM-DD_YYYY-MM-DD.html（アーカイブ）               │   │
│  │    • news/YYYY-MM-DD_YYYY-MM-DD.md（Markdown版）                 │   │
│  │                                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                 │                                       │
│                                 ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                                                                   │   │
│  │  【Cloudflare Access】アクセス制御                               │   │
│  │                                                                   │   │
│  │   許可されたメールアドレスのみアクセス可能                         │   │
│  │   メールによるワンタイムコード認証                                │   │
│  │                                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                 │                                       │
│                                 ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                                                                   │   │
│  │  【閲覧者】（許可されたユーザーのみ）                             │   │
│  │                                                                   │   │
│  │   PC / スマートフォン / タブレット                                │   │
│  │   （インターネットブラウザでアクセス）                            │   │
│  │                                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 情報源（RSSフィード）詳細

| サイト名 | 運営元 | RSSフィードURL | 取得内容 |
|---------|--------|---------------|----------|
| 労働新聞社 | 株式会社労働新聞社 | https://www.rodo.co.jp/feed/ | 労働関連の専門ニュース |
| 労務ドットコム | 株式会社名南経営コンサルティング | https://roumu.com/feed/ | 実務に役立つ労務情報 |
| 日本の人事部（記事） | 株式会社HRビジョン | https://jinjibu.jp/rss/?mode=atcl | 人事・労務の記事 |
| 日本の人事部（ニュース） | 株式会社HRビジョン | https://jinjibu.jp/rss/?mode=news | 企業のプレスリリース |
| SATO PORTAL | SATO社会保険労務士法人 | https://www.sato-group-sr.jp/portal/feed/ | 社労士向け実務情報 |
| 弁護士ドットコム | 弁護士ドットコム株式会社 | https://news.yahoo.co.jp/rss/media/bengocom/all.xml | 労働判例・法律ニュース |
| PSRネットワーク（総合） | 株式会社ブレインコンサルティングオフィス | https://www.psrn.jp/index.xml | 社労士向け総合情報 |
| PSRネットワーク（法改正） | 株式会社ブレインコンサルティングオフィス | https://www.psrn.jp/houkaisei/index.xml | 法改正情報 |

---

## 4. 使用技術・ライブラリ詳細

### 4.1 プログラミング言語

| 名称 | バージョン | 用途 |
|------|-----------|------|
| **Python** | 3.11 | メインのプログラミング言語 |

### 4.2 Pythonライブラリ

| ライブラリ名 | 用途 | 配布元 |
|-------------|------|--------|
| **feedparser** | RSSフィードの取得・解析 | PyPI (Python Package Index) |
| **anthropic** | Claude APIとの通信 | PyPI (Anthropic公式) |

### 4.3 Webページ関連

| 技術/サービス | 提供元 | 用途 |
|--------------|--------|------|
| **HTML5** | W3C標準 | Webページの構造 |
| **CSS3** | W3C標準 | Webページのデザイン |
| **Google Fonts** | Google | Webフォントの配信 |
| - Inter | Google Fonts | 英数字用フォント |
| - Noto Sans JP | Google Fonts | 日本語用フォント |

---

## 5. ファイル構成

```
labor-news-site/
│
├── .github/
│   └── workflows/
│       └── news-scraper.yml    ← GitHub Actions 設定ファイル
│
├── docs/                        ← Cloudflare Pages 公開フォルダ
│   ├── index.html              ← メインWebページ
│   ├── YYYY-MM-DD_YYYY-MM-DD.html  ← 週次アーカイブ
│   ├── favicon.png             ← ファビコン
│   ├── _headers                ← Cloudflare Pages ヘッダー設定
│   ├── _redirects              ← Cloudflare Pages リダイレクト設定
│   ├── SYSTEM_OVERVIEW.md      ← システム概要説明
│   └── SYSTEM_ARCHITECTURE.md  ← 本ドキュメント
│
├── news/                        ← Markdown出力フォルダ
│   └── YYYY-MM-DD_YYYY-MM-DD.md    ← 週次ニュース（Markdown形式）
│
├── collect_news.py              ← メインプログラム
├── requirements.txt             ← 依存ライブラリ一覧
└── README.md                    ← プロジェクト説明
```

---

## 6. 自動実行スケジュール

| 項目 | 設定値 |
|------|--------|
| 実行サービス | GitHub Actions |
| 実行タイミング | 毎週月曜日 9:00（日本時間） |
| 実行環境 | ubuntu-latest（Linux） |
| 収集期間 | 過去7日間 |

### 実行フロー

```
1. GitHub Actions が自動起動（毎週月曜 9:00 JST）
       │
       ▼
2. Python環境をセットアップ（Python 3.11）
       │
       ▼
3. 依存ライブラリをインストール（feedparser, anthropic）
       │
       ▼
4. collect_news.py を実行
       │
       ├─→ RSSフィードからニュース取得
       │
       ├─→ 労務関連キーワードでフィルタリング
       │
       ├─→ Claude API でサマリー生成
       │
       └─→ HTML/Markdown ファイル生成
       │
       ▼
5. 生成ファイルを GitHub にコミット＆プッシュ
       │
       ▼
6. Cloudflare Pages が変更を検知し自動デプロイ
       │
       ▼
7. Cloudflare Access が認証チェック
       │
       ▼
8. 許可されたユーザーのみ閲覧可能
```

---

## 7. セキュリティ設定

### 7.1 APIキーの管理

| 項目 | 設定 |
|------|------|
| 保管場所 | GitHub Secrets |
| シークレット名 | `ANTHROPIC_API_KEY` |
| アクセス制限 | GitHub Actions 実行時のみ読み取り可能 |

### 7.2 アクセス制御（Cloudflare Access）

| 項目 | 設定 |
|------|------|
| 認証方式 | メールによるワンタイムコード |
| アクセス許可 | 登録されたメールアドレスのみ |
| セッション時間 | 24時間（設定により変更可能） |

### 7.3 セキュリティ上の特徴

- APIキーはソースコードに直接記載しない
- GitHub Secrets により暗号化して保管
- Cloudflare Access により許可されたユーザーのみアクセス可能
- Webページは一般公開されない（認証必須）

---

## 8. コスト

### 8.1 無料のサービス

| サービス | 費用 |
|---------|------|
| GitHub（リポジトリ） | 無料 |
| GitHub Actions | 無料（月2,000分まで） |
| Cloudflare Pages | 無料 |
| Cloudflare Access | 無料（50ユーザーまで） |
| RSSフィード | 無料 |

### 8.2 有料のサービス

| サービス | 費用 | 備考 |
|---------|------|------|
| Claude API | 従量課金 | 週1回実行で月額約$0.20（約30円） |

### 8.3 コスト管理

- Anthropic Console（https://platform.claude.com/）で月間上限を設定可能
- 上限に達するとAPI呼び出しが自動停止（超過請求なし）

---

## 9. 運用情報

### 9.1 URL一覧

| 用途 | URL |
|------|-----|
| Webページ（認証必須） | Cloudflare Pages で発行されたURL |
| GitHubリポジトリ | https://github.com/sr-system-dev/labor-news-site |
| GitHub Actions | https://github.com/sr-system-dev/labor-news-site/actions |
| GitHub Secrets設定 | https://github.com/sr-system-dev/labor-news-site/settings/secrets/actions |
| Cloudflare ダッシュボード | https://dash.cloudflare.com/ |
| Cloudflare Zero Trust | https://one.dash.cloudflare.com/ |
| Anthropic Console | https://platform.claude.com/ |

### 9.2 手動実行方法

1. GitHub Actions ページを開く
2. 「労務関連ニュース収集」を選択
3. 「Run workflow」をクリック
4. 日数を指定して「Run workflow」を実行

---

## 10. トラブルシューティング

### 10.1 ニュースが収集されない場合

| 原因 | 対処法 |
|------|--------|
| RSSフィードのURL変更 | 各サイトの最新RSSフィードURLを確認し、collect_news.py を更新 |
| サイト側の一時的な障害 | 時間をおいて再実行 |

### 10.2 AIサマリーが生成されない場合

| 原因 | 対処法 |
|------|--------|
| APIキー未設定 | GitHub Secrets に `ANTHROPIC_API_KEY` を設定 |
| クレジット不足 | Anthropic Console でクレジットを追加購入 |
| API利用上限到達 | 翌月まで待つか、上限を引き上げ |

### 10.3 Webページが更新されない場合

| 原因 | 対処法 |
|------|--------|
| Cloudflare Pages 連携エラー | Cloudflare ダッシュボードでデプロイ状況を確認 |
| キャッシュ | ブラウザのキャッシュをクリア、または強制リロード（Ctrl+F5） |

### 10.4 アクセスできない場合

| 原因 | 対処法 |
|------|--------|
| メールアドレス未登録 | Cloudflare Zero Trust でユーザーを追加 |
| 認証コード期限切れ | 新しいコードを再送信 |
| セッション期限切れ | 再度認証を行う |

---

## 11. 改訂履歴

| 日付 | 内容 |
|------|------|
| 2026-02-01 | 初版作成 |
| 2026-02-03 | Cloudflare Pages/Access に移行、RSSソース追加（SATO PORTAL、弁護士ドットコム、PSRネットワーク） |
