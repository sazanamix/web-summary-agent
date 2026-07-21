"""巡回 -> 発見 -> 要約 -> レポート生成 を一括実行するエントリポイント。

GitHub Actions から `python scripts/main.py` として呼び出す想定。
"""

import sys

import build_report
import crawl
import discover
import summarize
from common import DATA_DIR, save_json, today_str


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else today_str()
    print(f"=== web-summary-agent run: {date} ===")

    crawl_result = crawl.run(date)
    save_json(DATA_DIR / "updates" / f"{date}.raw.json", crawl_result)
    print(f"[1/4] crawl: {len(crawl_result['changes'])} changed, "
          f"{len(crawl_result['errors'])} errors, {len(crawl_result['baseline_created'])} baseline")

    discovery_result = discover.run(date)
    save_json(DATA_DIR / "updates" / f"{date}.discovery.json", discovery_result)
    total_candidates = sum(len(g["candidates"]) for g in discovery_result["new_candidates"])
    print(f"[2/4] discover: {total_candidates} new candidates")

    summary_result = summarize.run(date)
    save_json(DATA_DIR / "updates" / f"{date}.json", summary_result)
    print(f"[3/4] summarize: source={summary_result['summary_source']}")

    build_report.run()
    print("[4/4] build_report: done")


if __name__ == "__main__":
    main()
