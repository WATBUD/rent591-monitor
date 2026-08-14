"""物件內頁抓取：目前僅取經緯度座標（供距離篩選用）。

CLAUDE.md 實測：內頁純 HTTP 可抓，且頁內嵌有物件座標，格式為
    ...,"<地址>","<lat>","<lng>","距房屋約N公尺",...
整頁只有這一組「地址→座標」，其餘 25.x/121.x 多為附近地標，故以地址為錨最穩。
"""
from __future__ import annotations

import logging
import re
import time

import httpx

import config
from scraper.list_scraper import _build_ssl_context, fetch_list_html

log = logging.getLogger(__name__)

# 台灣本島經緯度範圍：lat 21–25、lng 119–122（過濾雜訊用）
_LAT = r"2[0-5]\.\d{3,}"
_LNG = r"1(?:19|2[0-2])\.\d{3,}"


def make_client() -> httpx.Client:
    """與列表抓取相同設定的 HTTP client（UA／語系／放寬憑證嚴格模式）。"""
    return httpx.Client(
        headers={
            "User-Agent": config.USER_AGENT,
            "Accept-Language": "zh-TW,zh;q=0.9",
        },
        follow_redirects=True,
        verify=_build_ssl_context(),
    )


def extract_coords(html: str, address_hint: str | None = None) -> tuple[float, float] | None:
    """從內頁 HTML 取 (lat, lng)；抓不到回 None。

    優先以物件地址為錨（最準）；退而求其次用「座標後緊接『距房屋約』」的位置特徵；
    再不行才取頁內第一組帶引號的台灣座標。
    """
    if address_hint:
        m = re.search(rf'"{re.escape(address_hint)}"\s*,\s*"({_LAT})"\s*,\s*"({_LNG})"', html)
        if m:
            return float(m.group(1)), float(m.group(2))
    # 物件座標後方緊接「距房屋約…」的地標距離清單，可據此鎖定物件本身座標
    m = re.search(rf'"({_LAT})"\s*,\s*"({_LNG})"\s*,\s*"距房屋約', html)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(rf'"({_LAT})"\s*,\s*"({_LNG})"', html)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


def fetch_coords(
    listing_id: str, client: httpx.Client, address_hint: str | None = None
) -> tuple[float, float] | None:
    """抓單一物件內頁並解析座標；失敗回 None（不拋出）。"""
    url = f"{config.BASE_URL}/{listing_id}"
    html = fetch_list_html(url, client)  # 同樣的重試／退避邏輯，回 None 代表放棄
    if not html:
        return None
    return extract_coords(html, address_hint)


def _addr_hint(rec: dict) -> str | None:
    """用資料裡的 district+street 組出內頁地址字串（如「松山區富錦街359巷3弄1號」）。"""
    d = (rec.get("district") or "").strip()
    s = (rec.get("street") or "").strip()
    hint = f"{d}{s}"
    return hint or None


def enrich_coords(
    rows: list[dict],
    existing: dict[str, tuple[float, float]] | None = None,
    interval_sec: float | None = None,
    client: httpx.Client | None = None,
    max_fetch: int | None = None,
) -> int:
    """就地為 rows 補上 lat/lng。

    - existing：已知座標 {listing_id: (lat, lng)}（來自上輪快照），直接沿用不重抓。
    - 只對「沒有座標且不在 existing」的物件抓內頁，請求間隔 interval_sec。
    - max_fetch：本輪最多抓幾筆內頁（None=不限）。超過的留待下輪，避免排程單輪過久。
    回傳這次「實際抓內頁」的次數。
    """
    existing = existing or {}
    interval = config.REQUEST_INTERVAL_SEC if interval_sec is None else interval_sec
    own = client is None
    if own:
        client = make_client()

    fetched = 0
    try:
        # 先用既有座標填滿，統計還缺哪些
        todo = []
        for r in rows:
            lid = r["listing_id"]
            if r.get("lat") is not None and r.get("lng") is not None:
                continue
            if lid in existing:
                r["lat"], r["lng"] = existing[lid]
            else:
                todo.append(r)

        if max_fetch is not None and len(todo) > max_fetch:
            log.info("本輪待補 %d 筆，超過上限 %d，先補 %d 筆，其餘留待下輪",
                     len(todo), max_fetch, max_fetch)
            todo = todo[:max_fetch]

        for i, r in enumerate(todo):
            if fetched:  # 已抓過至少一次才需要間隔
                time.sleep(interval)
            coords = fetch_coords(r["listing_id"], client, _addr_hint(r))
            fetched += 1
            if coords:
                r["lat"], r["lng"] = coords
            else:
                r["lat"], r["lng"] = None, None
                log.warning("內頁座標抓不到：%s", r["listing_id"])
            log.info("座標補齊 %d/%d：%s → %s", i + 1, len(todo), r["listing_id"], coords)
    finally:
        if own:
            client.close()
    return fetched
