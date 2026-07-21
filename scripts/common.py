"""共通ユーティリティ: HTTP取得、状態(state)の読み書き、HTMLからのテキスト/リンク抽出。"""

import hashlib
import json
import os
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
STATE_DIR = ROOT / "state"
DOCS_DIR = ROOT / "docs"

USER_AGENT = (
    "Mozilla/5.0 (compatible; web-summary-agent/1.0; "
    "+https://github.com/sazanamix/web-summary-agent)"
)

REQUEST_TIMEOUT = 20


def http_get(url: str) -> str:
    """URLを取得してテキストを返す。失敗時は例外を投げる。"""
    resp = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.text


def extract_visible_text(html: str) -> str:
    """HTMLから比較・要約に使う本文テキストを抽出する（script/style/nav等は除外）。"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text("\n")
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def extract_links(html: str, base_url: str):
    """HTMLから (テキスト, URL) のリストを抽出する。"""
    from urllib.parse import urljoin

    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        text = a.get_text(" ", strip=True)
        links.append((text, urljoin(base_url, href)))
    return links


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_yaml(path: Path):
    import yaml

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def today_str(run_date=None) -> str:
    """呼び出し側から日付を渡せるようにする（テスト容易性のため）。未指定ならJST日付。"""
    if run_date:
        return run_date
    from datetime import datetime, timedelta, timezone

    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m-%d")
