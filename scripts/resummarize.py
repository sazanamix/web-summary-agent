"""指定した日付のdata/updates/{date}.raw.jsonを元に、再クロールせずに要約とレポートだけを作り直す。

Gemini API呼び出しの失敗時や、誤って要約なし版でレポートを上書きしてしまった場合の復旧用。
"""

import sys

import build_report
import summarize
from common import DATA_DIR, save_json, today_str


def main():
    date = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else today_str()
    result = summarize.run(date)
    save_json(DATA_DIR / "updates" / f"{date}.json", result)
    build_report.run()
    print(f"resummarize: date={date} changes={len(result['changes'])} source={result['summary_source']}")


if __name__ == "__main__":
    main()
