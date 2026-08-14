"""一次性補齊 data/latest.json 既有物件的經緯度座標。

之後每輪 main.py 會自動沿用/補新，本腳本只為把「歷史快照」的座標補起來。
多工並行抓內頁（預設 5 條），每 20 筆存檔一次；已有座標者跳過，可重複執行續跑。
內頁是各自的物件頁、比列表頁溫和，適度並行通常不會被擋；若見大量抓不到，
調低 --concurrency 或調高 --interval 即可。

用法：
    .venv/bin/python scripts/backfill_coords.py                      # 全部（5 並行）
    .venv/bin/python scripts/backfill_coords.py --limit 20           # 試跑 20 筆
    .venv/bin/python scripts/backfill_coords.py --concurrency 8 --interval 0.5
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from scraper.detail_scraper import _addr_hint, fetch_coords, make_client  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="最多補幾筆（0=全部）")
    ap.add_argument("--concurrency", type=int, default=5, help="並行連線數")
    ap.add_argument("--interval", type=float, default=0.6,
                    help="每條連線送出前的間隔秒數（節流用）")
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
    log.info("待補 %d 筆（已有座標 %d，總 %d）｜並行 %d、間隔 %.1fs",
             len(todo), have, len(listings), args.concurrency, args.interval)

    client = make_client()          # httpx.Client 可跨執行緒共用
    lock = threading.Lock()         # 保護 data 寫入與計數
    done = {"n": 0, "ok": 0}

    def work(rec: dict):
        if args.interval:
            time.sleep(args.interval)   # 溫和節流（各執行緒各自等）
        coords = fetch_coords(rec["listing_id"], client, _addr_hint(rec))
        with lock:
            if coords:
                rec["lat"], rec["lng"] = coords
                done["ok"] += 1
            else:
                rec["lat"], rec["lng"] = None, None
            done["n"] += 1
            n = done["n"]
            if n % 20 == 0:
                config.LATEST_PATH.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                log.info("… 已存檔（進度 %d/%d，成功 %d）", n, len(todo), done["ok"])
        return coords

    t0 = time.time()
    try:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futures = [ex.submit(work, rec) for rec in todo]
            for _ in as_completed(futures):
                pass
    finally:
        client.close()
        config.LATEST_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("完成：成功 %d / 嘗試 %d 筆，用時 %.0fs，已寫回 %s",
             done["ok"], len(todo), time.time() - t0, config.LATEST_PATH)


if __name__ == "__main__":
    main()
