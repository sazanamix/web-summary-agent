"""data/updates/*.json (要約済み) から GitHub Pages 用の静的レポートを生成する。

出力先: docs/index.html (一覧), docs/reports/{date}.html (日別詳細)
"""

import html

from common import DATA_DIR, DOCS_DIR, load_json

CATEGORY_LABELS = {
    "company": "会社",
    "certification": "資格",
    "tool": "ツール",
    "book": "書籍",
    "ai": "AI",
    "other": "その他",
}

STYLE = """
:root { color-scheme: light dark; }
body { font-family: -apple-system, "Segoe UI", "Hiragino Sans", "Yu Gothic", sans-serif;
       max-width: 900px; margin: 0 auto; padding: 24px 16px 80px; line-height: 1.7; }
h1 { font-size: 1.6rem; }
h2 { font-size: 1.2rem; margin-top: 2rem; }
.site { border: 1px solid rgba(128,128,128,0.35); border-radius: 8px; padding: 14px 16px; margin: 12px 0; }
.site h3 { margin: 0 0 6px; font-size: 1rem; }
.badge { display: inline-block; font-size: 0.75rem; padding: 2px 8px; border-radius: 999px;
         background: rgba(100,150,255,0.18); margin-left: 6px; }
.diff { background: rgba(128,128,128,0.08); border-radius: 6px; padding: 8px 10px;
        font-size: 0.85rem; white-space: pre-wrap; overflow-x: auto; margin-top: 8px; }
.dates { list-style: none; padding: 0; }
.dates li { margin: 6px 0; }
.dates a { text-decoration: none; font-weight: 600; }
.count { color: #888; font-size: 0.9rem; }
.candidate { font-size: 0.9rem; margin: 4px 0; }
footer { margin-top: 3rem; font-size: 0.8rem; color: #888; }
a { color: #3b7dd8; }
"""


def _esc(s: str) -> str:
    return html.escape(s or "")


def _render_day(data: dict) -> str:
    date = data["date"]
    changes = data.get("changes", [])
    candidates = data.get("new_candidates", [])
    errors = data.get("errors", [])

    by_category = {}
    for c in changes:
        by_category.setdefault(c["category"], []).append(c)

    body = [f"<h1>更新レポート: {_esc(date)}</h1>", '<p><a href="../index.html">&larr; 一覧に戻る</a></p>']

    if not changes:
        body.append("<p>この日は更新が検出されたサイトはありませんでした。</p>")

    for category, items in by_category.items():
        label = CATEGORY_LABELS.get(category, category)
        body.append(f"<h2>{_esc(label)}</h2>")
        for c in items:
            body.append(
                f'<div class="site"><h3><a href="{_esc(c["url"])}" target="_blank" rel="noopener">'
                f'{_esc(c["name"])}</a><span class="badge">{_esc(label)}</span></h3>'
                f'<p>{_esc(c.get("summary", "")).replace(chr(10), "<br>")}</p>'
                f'<details><summary>差分/新着の詳細</summary><div class="diff">{_esc(c.get("diff_text", ""))}</div></details>'
                f"</div>"
            )

    if candidates:
        body.append("<h2>新規候補サイト（未登録・要確認）</h2>")
        for group in candidates:
            body.append(f'<p><strong>{_esc(group["hub_name"])}</strong> から検出:</p>')
            for cand in group["candidates"]:
                body.append(
                    f'<div class="candidate">- <a href="{_esc(cand["url"])}" target="_blank" '
                    f'rel="noopener">{_esc(cand["text"] or cand["url"])}</a></div>'
                )

    if errors:
        body.append("<h2>取得エラー</h2><ul>")
        for e in errors:
            body.append(f'<li>{_esc(e.get("name", e.get("id","")))}: {_esc(e["error"])}</li>')
        body.append("</ul>")

    return _page(f"更新レポート {date}", "\n".join(body))


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>{STYLE}</style>
</head>
<body>
{body}
<footer>Web Summary Agent &mdash; 自動巡回・自動要約レポート</footer>
</body>
</html>
"""


def run():
    updates_dir = DATA_DIR / "updates"
    reports_dir = DOCS_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    daily_files = sorted(updates_dir.glob("*.json"))
    daily_files = [p for p in daily_files if not p.name.endswith((".raw.json", ".discovery.json"))]
    daily_files.sort(reverse=True)

    index_items = []
    for path in daily_files:
        data = load_json(path, None)
        if not data:
            continue
        date = data["date"]
        changed_count = len(data.get("changes", []))
        candidate_count = sum(len(g["candidates"]) for g in data.get("new_candidates", []))
        (reports_dir / f"{date}.html").write_text(_render_day(data), encoding="utf-8")
        note = f'更新 {changed_count}件'
        if candidate_count:
            note += f' / 新規候補 {candidate_count}件'
        index_items.append(f'<li><a href="reports/{date}.html">{date}</a> <span class="count">({note})</span></li>')

    body = [
        "<h1>Webサイト更新モニター</h1>",
        "<p>登録サイトを毎日巡回し、更新があったページを検出・要約しています。"
        "巡回対象は <code>config/sites.yaml</code> で管理しています。</p>",
    ]
    if index_items:
        body.append('<ul class="dates">' + "\n".join(index_items) + "</ul>")
    else:
        body.append("<p>まだレポートがありません。次回の巡回をお待ちください。</p>")

    (DOCS_DIR).mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "index.html").write_text(_page("Webサイト更新モニター", "\n".join(body)), encoding="utf-8")
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    print(f"build_report: {len(index_items)} daily reports rendered -> {DOCS_DIR}")


if __name__ == "__main__":
    run()
