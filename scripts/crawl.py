"""登録サイト(config/sites.yaml)を巡回し、更新を検出して data/updates/{date}.raw.json に保存する。"""

import difflib
import sys
from datetime import datetime, timezone

import feedparser

from common import (
    CONFIG_DIR,
    STATE_DIR,
    content_hash,
    extract_amazon_search_results,
    extract_visible_text,
    http_get,
    load_json,
    load_yaml,
)

STATE_PATH = STATE_DIR / "state.json"
SNAPSHOT_MAX_CHARS = 6000
DIFF_MAX_LINES = 60
RSS_KEEP_IDS = 200
AMAZON_KEEP_ASINS = 500
AMAZON_MAX_NEW_ITEMS = 10


def _entry_id(entry):
    return entry.get("id") or entry.get("link") or entry.get("title", "")


def _check_html(site, state):
    html = http_get(site["url"])
    text = extract_visible_text(html)[:SNAPSHOT_MAX_CHARS]
    new_hash = content_hash(text)
    prev = state.get(site["id"], {})
    prev_hash = prev.get("hash")
    prev_snapshot = prev.get("snapshot", "")

    is_first_run = prev_hash is None
    changed = (not is_first_run) and (prev_hash != new_hash)

    diff_text = ""
    if changed:
        diff = difflib.unified_diff(
            prev_snapshot.splitlines(),
            text.splitlines(),
            lineterm="",
        )
        diff_lines = [line for line in diff if line[:1] in ("+", "-") and line[:3] not in ("+++", "---")]
        diff_text = "\n".join(diff_lines[:DIFF_MAX_LINES])
        if not diff_text.strip():
            # ハッシュは変わったが差分抽出では実質的な差が見えないケース（空白/順序程度の差）
            diff_text = text[:1500]

    state[site["id"]] = {
        "hash": new_hash,
        "snapshot": text,
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }
    return changed, diff_text, is_first_run


def _check_rss(site, state):
    raw = http_get(site["url"])
    feed = feedparser.parse(raw)
    entries = feed.entries or []
    current_ids = [_entry_id(e) for e in entries]

    prev = state.get(site["id"], {})
    prev_ids = set(prev.get("entry_ids", []))
    is_first_run = "entry_ids" not in prev

    new_entries = [] if is_first_run else [e for e in entries if _entry_id(e) not in prev_ids]
    changed = len(new_entries) > 0

    diff_text = ""
    if changed:
        parts = []
        for e in new_entries[:20]:
            title = e.get("title", "(no title)")
            link = e.get("link", "")
            summary = e.get("summary", "")
            summary = summary[:300] if summary else ""
            parts.append(f"- {title}\n  {link}\n  {summary}".strip())
        diff_text = "\n\n".join(parts)

    state[site["id"]] = {
        "entry_ids": current_ids[:RSS_KEEP_IDS],
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }
    return changed, diff_text, is_first_run


def _check_amazon_search(site, state):
    """Amazon検索結果ページを取得し、前回未確認のASIN（新着商品）を検出する。

    Amazonはボット対策のマークアップ変更・アクセス制限を行うことがあるため、
    取得や解析に失敗した場合は呼び出し元のtry/exceptでエラーとして扱われる想定。
    """
    html = http_get(site["url"])
    items = extract_amazon_search_results(html)
    current_asins = [asin for asin, _, _ in items]

    prev = state.get(site["id"], {})
    prev_asins = set(prev.get("seen_asins", []))
    is_first_run = "seen_asins" not in prev

    new_items = [] if is_first_run else [i for i in items if i[0] not in prev_asins]
    changed = len(new_items) > 0

    diff_text = ""
    if changed:
        parts = []
        for asin, title, url in new_items[:AMAZON_MAX_NEW_ITEMS]:
            parts.append(f"- {title or '(タイトル取得失敗)'}\n  {url}")
        diff_text = "\n\n".join(parts)

    state[site["id"]] = {
        "seen_asins": current_asins[:AMAZON_KEEP_ASINS],
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }
    return changed, diff_text, is_first_run


def run(run_date: str) -> dict:
    config = load_yaml(CONFIG_DIR / "sites.yaml")
    sites = config.get("sites", [])
    state = load_json(STATE_PATH, {})

    changes = []
    errors = []
    baseline_created = []

    for site in sites:
        try:
            if site.get("type") == "rss":
                changed, diff_text, is_first_run = _check_rss(site, state)
            elif site.get("type") == "amazon_search":
                changed, diff_text, is_first_run = _check_amazon_search(site, state)
            else:
                changed, diff_text, is_first_run = _check_html(site, state)
        except Exception as exc:  # noqa: BLE001 - サイトごとの失敗は他に影響させない
            errors.append({"id": site["id"], "name": site["name"], "url": site["url"], "error": str(exc)})
            continue

        if is_first_run:
            baseline_created.append(site["id"])
            continue

        if changed:
            changes.append(
                {
                    "id": site["id"],
                    "name": site["name"],
                    "url": site["url"],
                    "category": site.get("category", "other"),
                    "type": site.get("type", "html"),
                    "diff_text": diff_text,
                }
            )

    from common import save_json

    save_json(STATE_PATH, state)

    return {
        "date": run_date,
        "changes": changes,
        "errors": errors,
        "baseline_created": baseline_created,
    }


if __name__ == "__main__":
    from common import DATA_DIR, save_json, today_str

    date = sys.argv[1] if len(sys.argv) > 1 else today_str()
    result = run(date)
    out_path = DATA_DIR / "updates" / f"{date}.raw.json"
    save_json(out_path, result)
    print(f"crawl: {len(result['changes'])} changed, {len(result['errors'])} errors, "
          f"{len(result['baseline_created'])} baseline -> {out_path}")
