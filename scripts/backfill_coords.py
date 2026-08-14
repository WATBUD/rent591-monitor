"""一次性補齊 data/latest.json 既有物件的經緯度座標。

之後每輪 main.py 會自動沿用/補新，本腳本只為把「歷史快照」的座標補起來。
逐筆抓內頁、每 10 筆存檔一次；已有座標者跳過，可重複執行續跑。

用法：
    .venv/bin/python scripts/backfill_coords.py            # 補全部在架
    .venv/bin/python scripts/backfill_coords.py --limit 5  # 只補 5 筆（試跑）
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from scraper.detail_scraper import _addr_hint, fetch_coords, make_client  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="最多補幾筆（0=全部）")
    ap.add_argument("--interval", type=float, default=config.REQUEST_INTERVAL_SEC)
    args = ap.parse_args()

    data = json.loads(config.LATEST_PATH.read_text(encoding="utf-8"))
    listings = data.get("listings", {})

    todo = [
        rec for rec in listings.values()
        if rec.get("status") in ("active", "missing")
        and (rec.get("lat") is None or rec.get("lng") is None)
    ]
    if args.limit:
        todo = todo[: args.limit]

    have = sum(1 for r in listings.values() if r.get("lat") is not None)
    log.info("待補 %d 筆（已有座標 %d，總 %d）", len(todo), have, len(listings))

    client = make_client()
    ok = 0
    try:
        for i, rec in enumerate(todo):
            if i:
                time.sleep(args.interval)
            coords = fetch_coords(rec["listing_id"], client, _addr_hint(rec))
            if coords:
                rec["lat"], rec["lng"] = coords
                ok += 1
            else:
                rec["lat"], rec["lng"] = None, None
            log.info("%d/%d  %s → %s", i + 1, len(todo), rec["listing_id"], coords)
            if (i + 1) % 10 == 0:
                config.LATEST_PATH.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                log.info("… 已存檔（進度 %d/%d）", i + 1, len(todo))
    finally:
        client.close()
        config.LATEST_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("完成：成功 %d / 嘗試 %d 筆，已寫回 %s", ok, len(todo), config.LATEST_PATH)


if __name__ == "__main__":
    main()
