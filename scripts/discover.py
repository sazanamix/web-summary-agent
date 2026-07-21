"""config/hubs.yaml のハブページを巡回し、未登録の新規候補URLを検出する。

自動では config/sites.yaml に追加しない。レポートに「新規候補」として載せるのみ。
"""

import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

from common import CONFIG_DIR, STATE_DIR, http_get, extract_links, load_json, load_yaml, save_json

CANDIDATES_STATE_PATH = STATE_DIR / "candidates_state.json"


def _known_urls():
    sites = load_yaml(CONFIG_DIR / "sites.yaml").get("sites", [])
    return {s["url"].rstrip("/") for s in sites}


def _matches_keywords(text: str, url: str, keywords) -> bool:
    # 英数字のみのキーワード（AI, QA, testなど）は単語境界つきで判定し、
    # "maintainers" に "ai" が含まれるような誤マッチを防ぐ。日本語キーワードは部分一致でよい。
    haystack = f"{text} {url}"
    for kw in keywords:
        if re.fullmatch(r"[A-Za-z0-9]+", kw):
            if re.search(rf"\b{re.escape(kw)}\b", haystack, re.IGNORECASE):
                return True
        elif kw.lower() in haystack.lower():
            return True
    return False


def _same_site(url_a: str, url_b: str) -> bool:
    return urlparse(url_a).netloc == urlparse(url_b).netloc


def run(run_date: str) -> dict:
    hub_config = load_yaml(CONFIG_DIR / "hubs.yaml")
    hubs = hub_config.get("hubs", [])
    common_keywords = hub_config.get("common_keywords", [])
    max_new = hub_config.get("max_new_candidates_per_hub", 20)

    known_urls = _known_urls()
    seen_state = load_json(CANDIDATES_STATE_PATH, {})

    new_candidates = []
    errors = []

    for hub in hubs:
        hub_id = hub["id"]
        try:
            html = http_get(hub["url"])
        except Exception as exc:  # noqa: BLE001
            errors.append({"id": hub_id, "name": hub["name"], "url": hub["url"], "error": str(exc)})
            continue

        keywords = hub.get("keywords", common_keywords)
        links = extract_links(html, hub["url"])

        prev_seen = set(seen_state.get(hub_id, []))
        found_this_run = []

        for text, url in links:
            url_norm = url.rstrip("/")
            if url_norm in known_urls:
                continue
            if _same_site(url, hub["url"]):
                # ハブページ自身のサイト内リンク（メニュー等）はノイズが多いので除外
                continue
            if url_norm in prev_seen:
                continue
            if not _matches_keywords(text, url, keywords):
                continue
            found_this_run.append({"text": text[:120], "url": url})
            if len(found_this_run) >= max_new:
                break

        if found_this_run:
            new_candidates.append(
                {
                    "hub_id": hub_id,
                    "hub_name": hub["name"],
                    "hub_url": hub["url"],
                    "category": hub.get("category", "other"),
                    "candidates": found_this_run,
                }
            )

        prev_seen.update(c["url"].rstrip("/") for c in found_this_run)
        seen_state[hub_id] = list(prev_seen)[-2000:]

    save_json(CANDIDATES_STATE_PATH, seen_state)

    return {
        "date": run_date,
        "new_candidates": new_candidates,
        "errors": errors,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    from common import DATA_DIR, today_str

    date = sys.argv[1] if len(sys.argv) > 1 else today_str()
    result = run(date)
    out_path = DATA_DIR / "updates" / f"{date}.discovery.json"
    save_json(out_path, result)
    total = sum(len(g["candidates"]) for g in result["new_candidates"])
    print(f"discover: {total} new candidates across {len(result['new_candidates'])} hubs -> {out_path}")
