"""快照比對：算出新增 / 降價 / 下架。

純函式、無 I/O（快照讀寫在 storage.py），方便單元測試。

狀態模型（state）以 listing_id 為 key 累積：
    {
      "generated_at": "...",
      "listings": {
        "<id>": { ...列表欄位..., "price_history": [{date, price}],
                  "missing_count": 0, "status": "active"|"removed",
                  "first_seen": "...", "last_seen": "..." }
      }
    }

比對規則（對照 CLAUDE.md）：
- 新 ID → 🆕 新增
- 同 ID 且 total_monthly 下降 → 💰 降價（寫入 price_history）
- 舊 ID 消失 → missing_count +1；達門檻（預設 2 輪）才判 ❌ 下架
  （避免暫時被擋就誤判下架；只在「跨過門檻的那一輪」列入下架報告，不重複通知）
比價一律用 total_monthly（含額外費用），而非單看租金。
"""
from __future__ import annotations


def _last_price(rec: dict) -> int | None:
    hist = rec.get("price_history") or []
    if hist:
        return hist[-1]["price"]
    return rec.get("total_monthly")


def diff_snapshots(
    previous: dict | None,
    current_listings: list[dict],
    today: str,
    missing_rounds_before_removed: int = 2,
) -> tuple[dict, dict]:
    """比對前次狀態與本輪抓取結果。

    回傳 (new_state, report)。report 內每筆保留完整物件 dict，方便通知分組。
    today 為本輪日期字串（YYYY-MM-DD），供 price_history 記錄；不在函式內取系統時間。
    """
    prev_listings: dict[str, dict] = dict((previous or {}).get("listings", {}))
    current_by_id = {c["listing_id"]: c for c in current_listings}

    new_state_listings: dict[str, dict] = {}
    report = {"new": [], "price_drop": [], "removed": []}

    # 1) 本輪出現的物件：判斷新增 / 降價 / 續存
    for lid, cur in current_by_id.items():
        cur_total = cur.get("total_monthly")
        if lid not in prev_listings:
            rec = {
                **cur,
                "price_history": (
                    [{"date": today, "price": cur_total}] if cur_total is not None else []
                ),
                "missing_count": 0,
                "status": "active",
                "first_seen": cur.get("first_seen", today),
                "last_seen": today,
            }
            new_state_listings[lid] = rec
            report["new"].append(rec)
            continue

        prev = prev_listings[lid]
        prev_price = _last_price(prev)
        history = list(prev.get("price_history") or [])

        rec = {
            **cur,  # 以最新抓到的欄位為主（標題、坪數等可能更新）
            "price_history": history,
            "missing_count": 0,
            "status": "active",
            "first_seen": prev.get("first_seen", cur.get("first_seen", today)),
            "last_seen": today,
        }

        # 價格變動：寫入 history；下降才列入降價報告
        if cur_total is not None and cur_total != prev_price:
            history.append({"date": today, "price": cur_total})
            if prev_price is not None and cur_total < prev_price:
                drop = prev_price - cur_total
                pct = round(drop / prev_price * 100, 1) if prev_price else 0.0
                report["price_drop"].append({
                    **rec,
                    "old_price": prev_price,
                    "new_price": cur_total,
                    "drop": drop,
                    "drop_pct": pct,
                })
        new_state_listings[lid] = rec

    # 2) 本輪消失的物件：累積 missing，達門檻才判下架
    for lid, prev in prev_listings.items():
        if lid in current_by_id:
            continue
        prev_status = prev.get("status", "active")
        missing = prev.get("missing_count", 0) + 1
        rec = {**prev, "missing_count": missing}

        if missing >= missing_rounds_before_removed:
            rec["status"] = "removed"
            # 只在「剛跨過門檻」那輪列入報告，避免每輪重複通知
            if prev_status != "removed":
                report["removed"].append(rec)
        else:
            rec["status"] = "missing"
        new_state_listings[lid] = rec

    new_state = {"generated_at": today, "listings": new_state_listings}
    return new_state, report
