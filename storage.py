"""快照讀寫：latest.json（供網頁與下一輪比對基準）+ 每輪時間戳快照。"""
from __future__ import annotations

import json

import config


def load_latest() -> dict | None:
    """讀取上一輪的完整狀態；不存在則回 None。"""
    if not config.LATEST_PATH.exists():
        return None
    return json.loads(config.LATEST_PATH.read_text(encoding="utf-8"))


def save_snapshot(payload: dict, timestamp: str) -> None:
    """寫入時間戳快照與 latest.json（兩者同內容）。timestamp 形如 20260812-140000。"""
    config.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    (config.SNAPSHOT_DIR / f"{timestamp}.json").write_text(text, encoding="utf-8")
    config.LATEST_PATH.write_text(text, encoding="utf-8")


def load_watchlist() -> dict:
    """讀取關注清單（listing_id -> {note, added_at}）；不存在則回空 dict。"""
    if not config.WATCHLIST_PATH.exists():
        return {}
    data = json.loads(config.WATCHLIST_PATH.read_text(encoding="utf-8"))
    # 允許兩種格式：{id: {...}} 或 {"items": {id: {...}}}
    return data.get("items", data) if isinstance(data, dict) else {}
