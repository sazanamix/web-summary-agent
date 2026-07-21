"""GEMINI_API_KEYが正しく機能するかを、実際のサイト更新を待たずに確認するための単体テスト。

ダミーの更新データを1件作り、summarize._call_gemini() を直接呼び出して結果を表示する。
GitHub Actionsのログで確認する用途（本番のレポートデータには影響しない）。
"""

import os
import sys

import requests

from summarize import _call_gemini


def _list_available_models(api_key: str):
    resp = requests.get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        params={"key": api_key},
        timeout=30,
    )
    if not resp.ok:
        print(f"(モデル一覧の取得にも失敗: {resp.status_code} {resp.text[:300]})")
        return
    models = resp.json().get("models", [])
    usable = [
        m["name"].replace("models/", "")
        for m in models
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    print("このAPIキーで利用可能な generateContent 対応モデル:")
    for name in usable:
        print(f"  - {name}")


def main():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("NG: GEMINI_API_KEY が環境変数に設定されていません。")
        sys.exit(1)

    dummy_changes = [
        {
            "id": "test-dummy",
            "name": "テスト用ダミーサイト",
            "diff_text": (
                "+ 新しいテスト管理ツール「ExampleQA」がリリースされました。\n"
                "+ AIによるテストケース自動生成機能が追加され、従来より30%高速にテストを作成できます。\n"
                "+ 料金プランに無料枠が新設されました。"
            ),
        }
    ]

    try:
        summaries = _call_gemini(dummy_changes, api_key)
    except Exception as exc:  # noqa: BLE001
        print(f"NG: Gemini API呼び出しに失敗しました: {exc}")
        _list_available_models(api_key)
        sys.exit(1)

    summary = summaries.get("test-dummy")
    if not summary:
        print(f"NG: レスポンスの解析に失敗しました（想定外の形式）。生データ: {summaries}")
        sys.exit(1)

    print("OK: GEMINI_API_KEY は正しく機能しています。")
    print(f"生成された要約サンプル:\n{summary}")


if __name__ == "__main__":
    main()
