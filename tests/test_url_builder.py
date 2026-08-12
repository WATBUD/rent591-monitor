"""驗證 url_builder 產出的網址符合 591 已驗證的參數規格。

為何重要：URL 只要有一個參數格式錯（例如 price 少了 `$`、section 沒逗號串接），
591 會靜默回傳「錯的搜尋結果」而不是報錯，整套監控就抓錯物件。
因此這裡直接比對 CLAUDE.md 內實測過的範例網址。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.url_builder import build_list_url, _range_param  # noqa: E402

# CLAUDE.md「591 URL 參數規格（已驗證）」中的實測範例網址
EXPECTED_SUB001 = (
    "https://rent.591.com.tw/list?"
    "region=3&sort=posttime_desc&section=43,47,44,26&kind=1&shape=2"
    "&price=0$_40000$&layout=4&acreage=30$_$"
)


def _load_sub001() -> dict:
    path = Path(__file__).resolve().parent.parent / "subscriptions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["subscriptions"][0]


def test_sub001_matches_verified_example():
    assert build_list_url(_load_sub001()) == EXPECTED_SUB001


def test_sort_override_for_multi_sort_union():
    # 多排序聯集：同一訂閱換 sort 應只改 sort，其餘參數不動
    url = build_list_url(_load_sub001(), sort="money_asc")
    assert "sort=money_asc" in url
    assert "posttime_desc" not in url
    assert "section=43,47,44,26" in url


def test_open_upper_bound_uses_dollar_only():
    # 30 坪以上（上限開放）→ 30$_$
    assert _range_param(30, None) == "30$_$"


def test_open_lower_bound_fills_zero():
    # 低限空 → 補 0，對齊 591 格式
    assert _range_param(None, 40000) == "0$_40000$"


def test_both_bounds_none_omits_param():
    assert _range_param(None, None) is None


def test_empty_multi_selects_are_omitted():
    sub = {"region": "1", "sections": [], "shape": [], "layout": []}
    url = build_list_url(sub)
    assert url == "https://rent.591.com.tw/list?region=1&sort=posttime_desc"
