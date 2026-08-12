"""把一筆訂閱條件組成 591 列表頁網址。

純函式、無 I/O。591 的 price / acreage 參數使用字面 `$` 與 `,`，
故手動組 query string，不做 URL encode（591 就是吃這種格式）。
"""
from __future__ import annotations


def _range_param(low, high) -> str | None:
    """把數值範圍組成 591 的 `min$_max$` 格式。

    開放上限用 `min$_$`；上下限皆空則回傳 None（代表不帶此參數）。
    低限空時以 0 補上，對齊 CLAUDE.md 範例 `0$_40000$`。
    """
    if low is None and high is None:
        return None
    low_part = 0 if low is None else low
    high_part = f"{high}$" if high is not None else "$"
    return f"{low_part}$_{high_part}"


def build_list_url(sub: dict, sort: str | None = None) -> str:
    """訂閱 dict → 591 列表頁完整網址。

    參數順序刻意對齊 CLAUDE.md 的範例，方便人工核對。
    `sort` 可覆寫訂閱自身的排序（多排序聯集抓取時會用到）。
    """
    params: list[tuple[str, str]] = []

    params.append(("region", str(sub["region"])))
    params.append(("sort", sort or sub.get("sort") or "posttime_desc"))

    sections = sub.get("sections") or []
    if sections:
        params.append(("section", ",".join(str(s) for s in sections)))

    if sub.get("kind"):
        params.append(("kind", str(sub["kind"])))

    shape = sub.get("shape") or []
    if shape:
        params.append(("shape", ",".join(str(s) for s in shape)))

    price = _range_param(sub.get("price_min"), sub.get("price_max"))
    if price is not None:
        params.append(("price", price))

    layout = sub.get("layout") or []
    if layout:
        params.append(("layout", ",".join(str(s) for s in layout)))

    acreage = _range_param(sub.get("acreage_min"), sub.get("acreage_max"))
    if acreage is not None:
        params.append(("acreage", acreage))

    query = "&".join(f"{k}={v}" for k, v in params)
    return f"https://rent.591.com.tw/list?{query}"
