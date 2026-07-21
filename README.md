# web-summary-agent

ソフトウェアテスト関連（会社・資格・ツール・書籍・AI）のWebサイトを毎日自動巡回し、
更新があったページを検出して要約し、GitHub Pagesでレポートを公開するツールです。

公開レポート: `https://sazanamix.github.io/web-summary-agent/`
（[sazanamix/github-pages](https://github.com/sazanamix/github-pages) からもリンクできます）

## 仕組み

```
config/sites.yaml   … 巡回対象サイトの一覧（ここを編集してURLを追加/削除）
config/hubs.yaml     … 新規サイト発見用のハブページ一覧（まとめサイト等）
        │
        ▼
scripts/crawl.py      … 各サイトを取得し、前回との差分/新着記事を検出（state/state.json に前回内容を保存）
scripts/discover.py   … ハブページのリンクからキーワードに合う未登録サイトを検出（自動追加はしない）
scripts/summarize.py  … 検出した差分をGemini無料APIで要約（キー未設定時は差分をそのまま表示）
scripts/build_report.py … docs/ 以下に静的HTMLレポートを生成（GitHub Pagesで公開）
scripts/main.py        … 上記を順番に実行するエントリポイント
        │
        ▼
.github/workflows/crawl.yml … 毎日1回（07:00 JST）自動実行し、結果をコミット&プッシュ
```

## サイトの追加・編集方法

`config/sites.yaml` を編集するだけです。例:

```yaml
  - id: tool-example        # 一意なID（変更すると差分履歴がリセットされます）
    name: Example Tool（ブログ）
    url: https://example.com/blog/
    category: tool           # company / certification / tool / book / ai
    type: html                # html（本文差分） or rss（フィードの新着）
```

RSS/Atomフィードがあるサイトは `type: rss` にすると、ページ全文のハッシュ比較ではなく
新着エントリの有無で判定するため、誤検知が少なくなります（Selenium/Playwrightなどで採用）。

初回巡回時はそのサイトの「基準値」を記録するだけで、更新ありとしては報告されません
（2回目以降の巡回から差分検出が有効になります）。

## 新規サイトの自動発見について

ご相談いただいた「URL登録以外の発見方法」について、以下の理由で **RSS対応＋ハブページのリンク抽出** を採用しました。

- 検索エンジンAPI（Google Custom Search等）で「ソフトウェアテストで検索して上位N件」を毎回取得する方式は、
  APIキー・利用枠（無料枠は1日100件程度）が必要な上、検索結果は同じような大手サイトに偏りやすく、
  巡回対象が肥大化してノイズが増えやすいという欠点があります。
- 代わりに、業界の「まとめサイト・リンク集」（例: [awesome-testing](https://github.com/TheJambo/awesome-testing) や
  Qiitaのタグページ）をハブとして登録し、そこに載っている未登録リンクをキーワードで絞り込んで
  「新規候補」として毎回レポートに表示する方式にしました。
- 候補は自動で `sites.yaml` に追加されません。レポート下部の「新規候補サイト」を見て、
  良さそうなものを手動で `sites.yaml` に追記する運用を想定しています（誤って質の低いサイトを
  巡回対象に混入させないためです）。
- ハブページは `config/hubs.yaml` で追加できます。1ハブあたり最大件数（`max_new_candidates_per_hub`）で
  ノイズの量を制御できます。

将来的に検索API方式を追加したい場合は、`scripts/discover.py` と同じ構造（候補を出すだけで自動追加しない）
で `search_discover.py` を追加する形が拡張しやすいと思います。

## 巡回数・巡回タイミングについての提案

- **巡回サイト数**: 検索結果を毎回大量に舐める方式は避け、カテゴリごとに質の高いサイトを
  数件〜10件程度手動で選定 → 増やしたい場合は「新規候補」から追記、という運用を推奨します
  （初期セットは各カテゴリ3〜6件、計19件で動作確認済み）。サイト数が増えても1サイトの巡回は数秒程度なので、
  数十〜100件程度までは日次実行で問題ありません。
- **巡回タイミング**: 深夜〜早朝（更新が出揃っている時間帯）を推奨し、07:00 JST（22:00 UTC）の日次実行にしています。
  `crawl.yml` の `cron` を変更すれば頻度や時刻を調整できます（例: 1日2回にする、平日のみにする等）。
- **報告方法**: 今回はGitHub Pagesのみを実装しました（認証情報が不要で運用がシンプルなため）。
  メール通知やX投稿は、それぞれSMTP認証情報／X API利用登録が必要になるため、必要になったタイミングで
  `scripts/notify_mail.py` 等を追加し、`main.py` の最後で呼び出す形が追加しやすいです。

## 要約（Gemini API）の設定

要約にはGoogleの無料枠があるGemini APIを使います。設定しない場合は、検出した差分/新着内容を
そのまま短く整形して表示するだけになります（要約なしでも動作します）。

1. [Google AI Studio](https://aistudio.google.com/app/apikey) で無料のAPIキーを発行する
2. GitHubリポジトリの `Settings > Secrets and variables > Actions` で
   `GEMINI_API_KEY` という名前のSecretに登録する
3. 次回の巡回から自動的に要約が使われます

無料枠には利用制限があるため、サイト数が非常に多くなった場合は
`scripts/summarize.py` の `GEMINI_MODEL` を軽量モデルに変更するか、要約対象を絞る調整をしてください。

## GitHub Pagesの公開設定（初回のみ）

このリポジトリの `Settings > Pages` で、Source を `Deploy from a branch`、
Branch を `main` / `/docs` に設定してください（`gh` コマンドで自動設定済みの場合は不要です）。

## ローカルでの動作確認

```bash
pip install -r requirements.txt
python scripts/main.py            # 今日の日付で1回実行
python scripts/main.py 2026-01-01 # 日付を指定して実行（テスト用）
```

`state/` 以下に前回巡回時の内容が保存されるため、2回目の実行から差分検出が機能します。

## ディレクトリ構成

```
config/sites.yaml   巡回対象サイト一覧（編集対象）
config/hubs.yaml     新規発見用ハブページ一覧（編集対象）
scripts/             巡回・発見・要約・レポート生成のスクリプト
state/                前回巡回内容（差分検出用、自動更新）
data/updates/         日別の生データ・要約データ（自動生成、履歴として蓄積）
docs/                 GitHub Pages公開用の静的HTML（自動生成）
.github/workflows/    日次実行用のGitHub Actions
```
