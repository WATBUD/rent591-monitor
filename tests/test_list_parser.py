"""驗證 list_parser 對真實 591 列表頁 HTML 的解析結果。

為何重要：這些欄位是後續 diff（降價判斷靠 total_monthly）與通知的資料來源，
解析一旦錯位（例如把額外費用當租金、樓層與坪數對調），會導致誤報或漏報。
fixture 為實抓的 SSR 頁面；fetched_at 固定以讓相對時間換算可重現。
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.list_parser import parse_list_html  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "list_sample.html"
FETCHED_AT = datetime(2026, 8, 12, 14, 0, 0)


def _load():
    html = FIXTURE.read_text(encoding="utf-8")
    return parse_list_html(html, fetched_at=FETCHED_AT)


def _by_id(rows, lid):
    return next(r for r in rows if r["listing_id"] == lid)


def test_parses_all_ssr_items():
    rows = _load()
    # SSR 首頁約 30 筆（實測固定 30）
    assert len(rows) == 30
    assert all(r["listing_id"] for r in rows)


def test_owner_listing_fields():
    r = _by_id(_load(), "21813196")
    assert r["district"] == "板橋區"
    assert r["street"] == "金門街369巷36號"
    assert r["community"] == "金龍名邸"
    assert r["kind_name"] == "整層住家"
    assert (r["rooms"], r["halls"]) == (4, 2)
    assert r["size_ping"] == 40.0
    assert (r["floor"], r["total_floor"]) == ("4F", "7F")
    assert r["price"] == 33000
    assert r["extra_fee"] == 0
    assert r["total_monthly"] == 33000
    assert r["poster_type"] == "屋主"
    assert r["poster_name"] == "廖小姐"
    assert "屋主直租" in r["tags"]
    assert r["image"].startswith("https://") and "591.com.tw" in r["image"]


def test_extra_fee_added_to_total_monthly():
    # 關鍵：額外費用要計入 total_monthly，否則比價會失真
    r = _by_id(_load(), "21814834")
    assert r["extra_fee"] == 1580
    assert r["price"] == 35000
    assert r["total_monthly"] == 36580
    assert r["district"] == "板橋區"


def test_fee_included_parsed():
    r = _by_id(_load(), "21817212")
    assert r["extra_fee"] == 0
    assert r["fee_included"] == ["管理費"]


def test_relative_days_converted_to_absolute_date():
    # '5天前更新' 相對 2026-08-12 -> 2026-08-07
    r = _by_id(_load(), "21793269")
    assert r["updated_rel"] == "5天前更新"
    assert r["posted_at"] == "2026-08-07"


def test_within_a_day_uses_fetch_date():
    # '小時內更新' 視為抓取當日
    r = _by_id(_load(), "21817212")
    assert r["posted_at"] == "2026-08-12"
