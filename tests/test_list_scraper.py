"""驗證 list_scraper 的聯集去重與抓取流程（離線，用 MockTransport）。

為何重要：多排序聯集的正確性在於「同一物件不論在哪個排序出現，只算一次」，
且每筆都要補上 subscription_id / region 供後續 diff 與分組。
用 httpx.MockTransport 餵固定 fixture，避免真連網、保持可重現。
"""
import sys
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from scraper.list_scraper import merge_listings, scrape_subscription  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "list_sample.html"
FETCHED_AT = datetime(2026, 8, 12, 14, 0, 0)
SUB = {"id": "sub-001", "region": "3", "sections": ["26"]}


def test_merge_dedups_by_listing_id_and_enriches():
    b1 = [{"listing_id": "A", "price": 100}, {"listing_id": "B", "price": 200}]
    b2 = [{"listing_id": "B", "price": 200}, {"listing_id": "C", "price": 300}]
    merged = merge_listings(SUB, [b1, b2], "新北市")
    ids = sorted(r["listing_id"] for r in merged)
    assert ids == ["A", "B", "C"]  # B 只出現一次
    assert all(r["subscription_id"] == "sub-001" for r in merged)
    assert all(r["region"] == "新北市" for r in merged)


def test_scrape_subscription_unions_across_sorts(monkeypatch):
    monkeypatch.setattr(config, "REQUEST_INTERVAL_SEC", 0)  # 測試不等待
    html = FIXTURE.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    rows = scrape_subscription(
        SUB, sorts=["posttime_desc", "money_asc"], fetched_at=FETCHED_AT, client=client
    )
    # 兩個排序都回同一份 30 筆 → 聯集仍為 30
    assert len(rows) == 30
    assert all(r["subscription_id"] == "sub-001" for r in rows)
    assert all(r["region"] == "新北市" for r in rows)


def test_fetch_returns_none_on_persistent_failure(monkeypatch):
    monkeypatch.setattr(config, "REQUEST_INTERVAL_SEC", 0)
    from scraper.list_scraper import fetch_list_html

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    # 連續失敗應回 None 而非拋出（整輪不中斷）
    assert fetch_list_html("https://rent.591.com.tw/list?x=1", client) is None
