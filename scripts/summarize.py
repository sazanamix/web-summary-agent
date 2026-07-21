"""crawl.py / discover.py の生データをまとめ、Gemini無料APIで日本語要約を付けて
data/updates/{date}.json (最終レポート用データ) を作成する。

GEMINI_API_KEY が未設定 / API呼び出し失敗時は、差分テキストをそのまま短く整形して
「要約なし」として扱う（フォールバック）。
"""

import json
import os
import sys

import requests

from common import DATA_DIR, load_json, save_json

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)
FALLBACK_NOTE = "(要約なし: GEMINI_API_KEY未設定のため差分をそのまま表示しています)"


def _fallback_summary(diff_text: str) -> str:
    text = diff_text.strip().replace("\n", " ")
    return text[:200] + ("…" if len(text) > 200 else "")


def _build_prompt(changes):
    items = []
    for c in changes:
        items.append(
            f'id: "{c["id"]}"\n'
            f'サイト名: {c["name"]}\n'
            f'差分/新着内容:\n{c["diff_text"][:1500]}\n'
        )
    joined = "\n---\n".join(items)
    return (
        "あなたはソフトウェアテスト業界のニュースを要約するアシスタントです。"
        "以下は複数のWebサイトで検出された更新内容（差分または新着記事）です。"
        "各サイトについて、日本語で2〜3文の簡潔な要約を作成してください。"
        "出力は必ず次のJSON配列形式のみで返してください（説明文やコードブロック記号は不要）:\n"
        '[{"id": "サイトのid", "summary": "要約文"}, ...]\n\n'
        f"{joined}"
    )


def _call_gemini(changes, api_key: str):
    prompt = _build_prompt(changes)
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(
        GEMINI_URL,
        params={"key": api_key},
        json=payload,
        timeout=60,
    )
    if not resp.ok:
        raise RuntimeError(f"{resp.status_code} {resp.reason}: {resp.text[:500]}")
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    parsed = json.loads(text)
    return {item["id"]: item["summary"] for item in parsed if "id" in item and "summary" in item}


def run(run_date: str) -> dict:
    raw_path = DATA_DIR / "updates" / f"{run_date}.raw.json"
    discovery_path = DATA_DIR / "updates" / f"{run_date}.discovery.json"

    raw = load_json(raw_path, {"changes": [], "errors": [], "baseline_created": []})
    discovery = load_json(discovery_path, {"new_candidates": [], "errors": []})

    changes = raw.get("changes", [])
    api_key = os.environ.get("GEMINI_API_KEY", "")
    summaries = {}
    summary_source = "none"

    if changes and api_key:
        try:
            summaries = _call_gemini(changes, api_key)
            summary_source = "gemini"
        except Exception as exc:  # noqa: BLE001
            summary_source = f"gemini_failed: {exc}"

    for c in changes:
        c["summary"] = summaries.get(c["id"]) or _fallback_summary(c["diff_text"])
        if c["id"] not in summaries:
            c["summary"] += f"\n{FALLBACK_NOTE}" if not api_key else "\n(要約なし: API応答の解析に失敗)"

    result = {
        "date": run_date,
        "changes": changes,
        "errors": raw.get("errors", []) + discovery.get("errors", []),
        "baseline_created": raw.get("baseline_created", []),
        "new_candidates": discovery.get("new_candidates", []),
        "summary_source": summary_source,
    }
    return result


if __name__ == "__main__":
    from common import today_str

    date = sys.argv[1] if len(sys.argv) > 1 else today_str()
    result = run(date)
    out_path = DATA_DIR / "updates" / f"{date}.json"
    save_json(out_path, result)
    print(f"summarize: {len(result['changes'])} changes summarized (source={result['summary_source']}) -> {out_path}")
