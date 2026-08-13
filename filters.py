"""依訂閱條件過濾列表物件。

實測（2026-08）：591 列表頁 SSR 只大致按 region/section 回傳，並未套用
房數(layout)、坪數(acreage)等篩選（那些由前端 JS 處理）。純 HTTP 抓下來
必須在程式端自行過濾，否則會混入不符條件的物件（例如查台北中正 4 房，
SSR 卻回一堆 2 房/13 坪）。

註：型態(shape，如電梯大樓)列表頁沒有可靠欄位，故不在此過濾。
"""
from __future__ import annotations

import config


def _layout_ok(rooms: int | None, layout: list | None) -> bool:
    """房數是否符合。layout 值 '4' 代表「4 房以上」，其餘為精確房數。"""
    if not layout:
        return True
    if rooms is None:
        return False  # 無房數（如開放式/工作室）不算符合 X 房
    for l in layout:
        l = int(l)
        if l >= 4 and rooms >= 4:
            return True
        if l < 4 and rooms == l:
            return True
    return False


def _range_ok(value, low, high) -> bool:
    if value is None:
        return low is None
    if low is not None and value < low:
        return False
    if high is not None and value > high:
        return False
    return True


def _kind_ok(kind_name: str | None, kind) -> bool:
    """類型是否符合。

    kind 可為：
    - 空（None/""/[]）→ 不過濾（放行全部，含車位/店面）。
    - 單一代碼（如 "2"）→ 需精確等於該類型名稱。
    - 代碼清單（如 ["1","2","3","4"]）→ 白名單，kind_name 須為其中之一；
      這是排除「車位/店面/其他」等非住宅的作法。
    """
    if not kind:
        return True
    if isinstance(kind, (list, tuple)):
        allowed = {config.KIND_NAMES.get(str(k)) for k in kind}
        return kind_name in allowed
    return kind_name == config.KIND_NAMES.get(str(kind))


def matches(listing: dict, sub: dict) -> bool:
    """物件是否符合訂閱條件（房數、租金、坪數、類型）。"""
    return (
        _layout_ok(listing.get("rooms"), sub.get("layout"))
        and _range_ok(listing.get("price"), sub.get("price_min"), sub.get("price_max"))
        and _range_ok(listing.get("size_ping"), sub.get("acreage_min"), sub.get("acreage_max"))
        and _kind_ok(listing.get("kind_name"), sub.get("kind"))
    )
