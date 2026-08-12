"""列表頁抓取：多排序聯集法。

CLAUDE.md 實測：列表頁是 JS 動態渲染，純 HTTP 只拿得到 SSR 首頁約 30 筆、
page 參數無效。折衷做法為同一條件用多種 sort 各抓一次，以 listing_id 取聯集，
結果 < 60 筆時通常能湊齊。

反爬：請求間隔 ≥ 3 秒、帶正常 UA、失敗重試後跳過（不中斷整輪）。
"""
from __future__ import annotations

import logging
import ssl
import time
from datetime import datetime

import certifi
import httpx

import config
from scraper.list_parser import parse_list_html
from scraper.url_builder import build_list_url

log = logging.getLogger(__name__)


def _build_ssl_context() -> ssl.SSLContext:
    """完整驗證憑證鏈與主機名，但關閉 OpenSSL 3.6+ 預設的 X509_STRICT。

    591 的憑證鏈缺 Subject Key Identifier 擴充，會被嚴格模式拒絕；
    此處僅放寬該 RFC 5280 擴充檢查，不影響鏈結與主機名驗證。
    """
    ctx = ssl.create_default_context(cafile=certifi.where())
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx


def fetch_list_html(url: str, client: httpx.Client) -> str | None:
    """抓單一列表頁 HTML；失敗重試 config.MAX_RETRIES 次後回 None（不拋出）。"""
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            resp = client.get(url, timeout=config.REQUEST_TIMEOUT_SEC)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # noqa: BLE001 — 任何失敗都應可跳過重試
            if attempt < config.MAX_RETRIES:
                backoff = config.REQUEST_INTERVAL_SEC * (attempt + 1)  # 遞增退避 3→6→9…
                log.warning("抓取失敗（第 %d 次重試，等 %ds）：%s", attempt + 1, backoff, exc)
                time.sleep(backoff)
                continue
            log.error("抓取放棄：%s（%s）", url, exc)
            return None


def merge_listings(sub: dict, batches: list[list[dict]], region_name: str | None) -> list[dict]:
    """把多次抓取的結果以 listing_id 取聯集去重，並補上訂閱/城市資訊。

    純函式，方便測試。先出現者為準（保留較早排序批次的欄位）。
    """
    merged: dict[str, dict] = {}
    for rows in batches:
        for row in rows:
            lid = row["listing_id"]
            if lid in merged:
                continue
            row = {**row, "subscription_id": sub["id"], "region": region_name}
            merged[lid] = row
    return list(merged.values())


def scrape_subscription(
    sub: dict,
    sorts: list[str] | None = None,
    fetched_at: datetime | None = None,
    client: httpx.Client | None = None,
) -> list[dict]:
    """抓取單一訂閱（多排序聯集），回傳去重後的物件清單。

    每次請求之間間隔 config.REQUEST_INTERVAL_SEC 秒。
    可注入 httpx.Client（測試用）；未提供則自建。
    """
    sorts = sorts or config.SORTS
    fetched_at = fetched_at or datetime.now()
    region_name = config.REGION_NAMES.get(str(sub["region"]))

    own_client = client is None
    if own_client:
        client = httpx.Client(
            headers={
                "User-Agent": config.USER_AGENT,
                "Accept-Language": "zh-TW,zh;q=0.9",
            },
            follow_redirects=True,
            verify=_build_ssl_context(),
        )

    batches: list[list[dict]] = []
    try:
        for i, sort in enumerate(sorts):
            if i > 0:
                time.sleep(config.REQUEST_INTERVAL_SEC)
            url = build_list_url(sub, sort=sort)
            html = fetch_list_html(url, client)
            if not html:
                continue
            rows = parse_list_html(html, fetched_at=fetched_at)
            if not rows:
                # 200 但解析不到物件：多半是反爬頁／機房 IP 被擋，記標題方便診斷
                import re as _re
                m = _re.search(r"<title>([^<]*)</title>", html)
                log.warning(
                    "[%s] sort=%s → 0 筆（HTML %d bytes，title=%r）疑似反爬",
                    sub["id"], sort, len(html), (m.group(1) if m else "?"),
                )
            batches.append(rows)
            running = merge_listings(sub, batches, region_name)
            log.info(
                "[%s] sort=%s → 本次 %d 筆（聯集累計 %d）",
                sub["id"], sort, len(rows), len(running),
            )
    finally:
        if own_client:
            client.close()

    merged = merge_listings(sub, batches, region_name)
    log.info("[%s] 完成，聯集共 %d 筆", sub["id"], len(merged))
    return merged
