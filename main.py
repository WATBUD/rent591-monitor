"""主流程：讀訂閱 → 逐訂閱抓取 → 比對 → 通知 → 存快照。

供 GitHub Actions 排程呼叫（python main.py）。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

import config
import notify
from diff import diff_snapshots
from scraper.list_scraper import scrape_subscription
from storage import load_latest, load_watchlist, save_snapshot

log = logging.getLogger("main")


def load_subscriptions() -> tuple[list[dict], dict]:
    data = json.loads(config.SUBSCRIPTIONS_PATH.read_text(encoding="utf-8"))
    subs = [s for s in data.get("subscriptions", []) if s.get("enabled", True)]
    settings = data.get("settings", {})
    return subs, settings


def collect_current(subs: list[dict], fetched_at: datetime) -> tuple[list[dict], list[dict]]:
    """逐訂閱抓取，跨訂閱以 listing_id 去重（先出現者為準）。

    回傳 (去重後物件清單, 每訂閱統計)。
    """
    merged: dict[str, dict] = {}
    stats = []
    for sub in subs:
        rows = scrape_subscription(sub, fetched_at=fetched_at)
        added = 0
        for r in rows:
            if r["listing_id"] not in merged:
                merged[r["listing_id"]] = r
                added += 1
        stats.append({"id": sub["id"], "name": sub.get("name", sub["id"]),
                      "fetched": len(rows), "unique_added": added})
        log.info("訂閱 %s：抓到 %d 筆，新增去重 %d 筆", sub["id"], len(rows), added)
    return list(merged.values()), stats


def run() -> dict:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    now = datetime.now()
    today = now.date().isoformat()
    timestamp = now.strftime("%Y%m%d-%H%M%S")

    subs, settings = load_subscriptions()
    if not subs:
        log.warning("沒有啟用中的訂閱，結束。")
        return {}

    threshold = settings.get("missing_rounds_before_removed", 2)
    watchlist = load_watchlist()

    current, stats = collect_current(subs, fetched_at=now)
    previous = load_latest()

    # 保險絲：整批抓到 0 筆、但上輪明明有資料 → 幾乎必為反爬/被擋，
    # 不可拿來比對（否則會把全部物件誤判為下架）。中止本輪、不動已存狀態。
    prev_active = sum(1 for v in (previous or {}).get("listings", {}).values()
                      if v.get("status") == "active")
    if not current and prev_active > 0:
        log.error("本輪抓到 0 筆，但上輪有 %d 筆在架 —— 疑似被反爬/擋 IP。"
                  "中止本輪，不覆寫狀態、不通知。", prev_active)
        raise SystemExit(1)

    new_state, report = diff_snapshots(previous, current, today=today,
                                       missing_rounds_before_removed=threshold)

    # 標記關注狀態，供網頁使用
    for lid, rec in new_state["listings"].items():
        rec["watched"] = lid in watchlist
        if lid in watchlist and isinstance(watchlist[lid], dict):
            rec["note"] = watchlist[lid].get("note", rec.get("note", ""))

    payload = {
        "generated_at": now.isoformat(timespec="seconds"),
        "subscriptions": stats,
        "report": report,
        "listings": new_state["listings"],
    }
    save_snapshot(payload, timestamp)

    header = subs[0].get("name", "591 租屋監控") if len(subs) == 1 else "591 租屋監控"
    notify.send(notify.format_report(report, header=header))

    log.info("完成：🆕%d 💰%d ❌%d（狀態共 %d 筆）",
             len(report["new"]), len(report["price_drop"]), len(report["removed"]),
             len(new_state["listings"]))
    return payload


if __name__ == "__main__":
    run()
