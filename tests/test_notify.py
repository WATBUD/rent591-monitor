"""驗證通知排版：分區、降價顯示、無變動時不發送。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from notify import format_report  # noqa: E402


def test_no_changes_returns_none():
    assert format_report({"new": [], "price_drop": [], "removed": []}) is None


def test_groups_by_district_and_shows_counts():
    report = {
        "new": [
            {"title": "板橋物件", "district": "板橋區", "total_monthly": 33000,
             "rooms": 4, "size_ping": 40.0, "floor": "4F", "url": "u1"},
            {"title": "三重物件", "district": "三重區", "total_monthly": 40000,
             "rooms": 4, "size_ping": 45.0, "floor": "7F", "url": "u2"},
        ],
        "price_drop": [
            {"title": "降價物件", "district": "三重區", "old_price": 39000,
             "new_price": 36000, "drop_pct": 7.7, "url": "u3"},
        ],
        "removed": [{"title": "下架物件", "district": "板橋區"}],
    }
    text = format_report(report, header="測試訂閱")
    assert "🔔 測試訂閱" in text
    assert "🆕 新增 2｜💰 降價 1｜❌ 下架 1" in text
    assert "📍板橋區" in text and "📍三重區" in text
    assert "$39000→$36000（↓7.7%）" in text
    assert "u1" in text and "u3" in text
