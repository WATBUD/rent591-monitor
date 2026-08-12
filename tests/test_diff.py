"""驗證 diff_snapshots 的新增/降價/下架判定。

為何重要：這是整套監控的判斷核心，錯誤會直接變成誤報或漏報。
特別驗證商業規則：
- 下架需連續達門檻輪才成立（避免 591 暫時被擋就誤判）
- 下架只在跨過門檻那輪通知一次（不每輪重複騷擾）
- 降價一律以 total_monthly（含額外費用）比較
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from diff import diff_snapshots  # noqa: E402


def _listing(lid, total, **kw):
    d = {
        "listing_id": lid, "title": f"物件{lid}", "district": "板橋區",
        "total_monthly": total, "first_seen": "2026-08-12", "last_seen": "2026-08-12",
    }
    d.update(kw)
    return d


def test_new_listing_detected_and_history_seeded():
    state, report = diff_snapshots(None, [_listing("A", 30000)], today="2026-08-12")
    assert [r["listing_id"] for r in report["new"]] == ["A"]
    assert state["listings"]["A"]["price_history"] == [{"date": "2026-08-12", "price": 30000}]
    assert not report["price_drop"] and not report["removed"]


def test_price_drop_uses_total_monthly():
    prev = {"listings": {"A": _listing("A", 39000, price_history=[{"date": "2026-08-10", "price": 39000}],
                                       missing_count=0, status="active")}}
    # 租金沒變但額外費用降 → total_monthly 由 39000 降到 36000
    cur = [_listing("A", 36000)]
    state, report = diff_snapshots(prev, cur, today="2026-08-12")
    assert len(report["price_drop"]) == 1
    d = report["price_drop"][0]
    assert (d["old_price"], d["new_price"], d["drop"]) == (39000, 36000, 3000)
    assert d["drop_pct"] == 7.7
    assert state["listings"]["A"]["price_history"][-1] == {"date": "2026-08-12", "price": 36000}


def test_price_increase_not_reported_as_drop_but_recorded():
    prev = {"listings": {"A": _listing("A", 30000, price_history=[{"date": "2026-08-10", "price": 30000}],
                                       missing_count=0, status="active")}}
    state, report = diff_snapshots(prev, [_listing("A", 32000)], today="2026-08-12")
    assert report["price_drop"] == []
    assert state["listings"]["A"]["price_history"][-1]["price"] == 32000


def test_removal_requires_two_missing_rounds():
    prev = {"listings": {"A": _listing("A", 30000, missing_count=0, status="active")}}

    # 第一輪消失：只累積 missing，尚未判下架
    state1, report1 = diff_snapshots(prev, [], today="2026-08-12", missing_rounds_before_removed=2)
    assert report1["removed"] == []
    assert state1["listings"]["A"]["status"] == "missing"
    assert state1["listings"]["A"]["missing_count"] == 1

    # 第二輪仍消失：達門檻 → 判下架並通知一次
    state2, report2 = diff_snapshots(state1, [], today="2026-08-13", missing_rounds_before_removed=2)
    assert [r["listing_id"] for r in report2["removed"]] == ["A"]
    assert state2["listings"]["A"]["status"] == "removed"

    # 第三輪仍消失：已下架，不再重複通知
    _, report3 = diff_snapshots(state2, [], today="2026-08-14", missing_rounds_before_removed=2)
    assert report3["removed"] == []


def test_reappearing_listing_resets_missing():
    prev = {"listings": {"A": _listing("A", 30000, missing_count=1, status="missing")}}
    state, report = diff_snapshots(prev, [_listing("A", 30000)], today="2026-08-12")
    assert state["listings"]["A"]["missing_count"] == 0
    assert state["listings"]["A"]["status"] == "active"
    assert report["removed"] == []


def test_mixed_round():
    prev = {"listings": {
        "keep": _listing("keep", 30000, price_history=[{"date": "2026-08-10", "price": 30000}],
                         missing_count=0, status="active"),
        "drop": _listing("drop", 40000, price_history=[{"date": "2026-08-10", "price": 40000}],
                         missing_count=0, status="active"),
        "gone": _listing("gone", 25000, missing_count=1, status="missing"),
    }}
    cur = [_listing("keep", 30000), _listing("drop", 37000), _listing("NEW", 28000)]
    state, report = diff_snapshots(prev, cur, today="2026-08-12", missing_rounds_before_removed=2)
    assert {r["listing_id"] for r in report["new"]} == {"NEW"}
    assert {r["listing_id"] for r in report["price_drop"]} == {"drop"}
    assert {r["listing_id"] for r in report["removed"]} == {"gone"}
