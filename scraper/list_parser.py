"""把 591 列表頁 HTML 解析成物件 dict 清單。

純解析、無網路 I/O，方便用固定 fixture 做單元測試。
選擇器對照實抓的 SSR DOM（見 tests/fixtures/list_sample.html）：
主列表卡片為 `div.item[data-id]`，欄位分佈於數個 `.item-info-txt`。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from selectolax.parser import HTMLParser, Node

# 刊登者身分前綴（用於拆出 poster_type / poster_name）
POSTER_TYPES = ("屋主", "代理人", "仲介", "房東", "委託", "建商", "代管")


def _text(node: Node | None) -> str:
    return node.text(strip=True) if node else ""


def _parse_money(text: str) -> int | None:
    """'35,000' -> 35000。"""
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def _parse_extra(text: str) -> tuple[int, list[str]]:
    """解析 extra-text 區塊。

    - '(額外費用 1,580元/月)' -> (1580, [])
    - '(租金含管理費)' / '(租金含管理費/車位)' -> (0, ['管理費', '車位'])
    - 空 -> (0, [])
    """
    if not text:
        return 0, []
    t = text.strip().strip("()（）")
    if "額外費用" in t:
        return (_parse_money(t) or 0), []
    if "含" in t:
        after = t.split("含", 1)[1]
        fees = [x for x in re.split(r"[/、,]", after) if x.strip()]
        return 0, [f.strip() for f in fees]
    return 0, []


def _parse_layout(text: str) -> tuple[int | None, int | None, int | None]:
    """'4房2廳' / '4房2廳1衛' -> (rooms, halls, baths)。缺項為 None。"""
    def grab(unit: str) -> int | None:
        m = re.search(rf"(\d+)\s*{unit}", text)
        return int(m.group(1)) if m else None
    return grab("房"), grab("廳"), grab("衛")


def _parse_size(text: str) -> float | None:
    """'57坪' / '43.5坪' -> 57.0 / 43.5。"""
    m = re.search(r"(\d+(?:\.\d+)?)\s*坪", text)
    return float(m.group(1)) if m else None


def _parse_floor(text: str) -> tuple[str | None, str | None]:
    """'2F/7F' -> ('2F','7F')；'7F~8F/8F' -> ('7F~8F','8F')。以最後一個 '/' 分隔。"""
    if not text or "/" not in text:
        return (text or None), None
    floor, _, total = text.rpartition("/")
    return floor or None, total or None


def _parse_poster(text: str) -> tuple[str | None, str | None]:
    """'屋主廖小姐' -> ('屋主','廖小姐')；'代理人陳先生' -> ('代理人','陳先生')。"""
    for p in POSTER_TYPES:
        if text.startswith(p):
            return p, (text[len(p):].strip() or None)
    return None, (text or None)


def _rel_to_date(rel: str, fetched_at: datetime) -> str | None:
    """相對時間換算成絕對日期字串（YYYY-MM-DD），誤差約一天內。

    支援 'N天前更新' / 'N小時內更新' / 'N分鐘前' / '剛剛'。
    """
    if not rel:
        return None
    if "剛剛" in rel or "分鐘" in rel or "小時" in rel:
        # 一天內：以抓取當日計
        return fetched_at.date().isoformat()
    m = re.search(r"(\d+)\s*天", rel)
    if m:
        return (fetched_at - timedelta(days=int(m.group(1)))).date().isoformat()
    return fetched_at.date().isoformat()


def parse_list_html(html: str, fetched_at: datetime | None = None) -> list[dict]:
    """列表頁 HTML -> 物件 dict 清單。

    fetched_at 供相對時間換算；預設為呼叫當下（測試時請傳固定值以求可重現）。
    """
    if fetched_at is None:
        fetched_at = datetime.now()
    fetched_iso = fetched_at.date().isoformat()

    tree = HTMLParser(html)
    results: list[dict] = []

    for item in tree.css("div.item"):
        listing_id = item.attributes.get("data-id")
        if not listing_id:
            continue  # 略過非主列表卡片（如推薦區塊）

        link = item.css_first(".item-info-title a")
        title = _text(link) or (link.attributes.get("title") if link else "") or None
        url = link.attributes.get("href") if link else None

        img = item.css_first(".item-img img")
        image = None
        if img:
            image = img.attributes.get("data-src") or img.attributes.get("src")

        tags = [t.text(strip=True) for t in item.css(".item-info-tag span.tag")]

        txts = item.css(".item-info-txt")

        # txt[0] 的 span 數量依類型而異，不能靠固定位置取值：
        #   整層住家：[類型, 格局(X房X廳), 坪數, 樓層]
        #   套房/雅房：[類型, 坪數, 樓層]        ← 沒有格局欄，少一格
        #   車位　　：[類型, 車位型式, 坪數]
        # 舊版寫死「坪數在第 3 格」會把套房/雅房的坪數錯讀成樓層而變 None，
        # 改為依內容特徵各自比對。
        kind_name = layout_txt = size_txt = floor_txt = ""
        if txts:
            spans = [s.text(strip=True) for s in txts[0].css("span") if s.text(strip=True)]
            if spans:
                kind_name = spans[0]
                rest = spans[1:]
                layout_txt = next((s for s in rest if re.search(r"\d+\s*[房廳衛]", s)), "")
                size_txt = next((s for s in rest if "坪" in s), "")
                floor_txt = next((s for s in rest if ("F" in s or "樓" in s) and "坪" not in s), "")

        rooms, halls, baths = _parse_layout(layout_txt)
        size_ping = _parse_size(size_txt)
        floor, total_floor = _parse_floor(floor_txt)

        # 找地點列（含「區-」）與刊登者列（role-name）
        community = district = street = None
        poster_type = poster_name = updated_rel = None
        for t in txts:
            classes = t.attributes.get("class", "")
            spans = [s.text(strip=True) for s in t.css("span") if s.text(strip=True)]
            joined = t.text(strip=True)
            if "role-name" in classes:
                poster_type, poster_name = _parse_poster(spans[0] if spans else "")
                for s in spans[1:]:
                    if "更新" in s or "前" in s:
                        updated_rel = s
                        break
            elif "區-" in joined or re.search(r"\S+區-", joined):
                # 形如：['社區名', '板橋區-金門街']；有時只有地址
                addr = next((s for s in spans if "區" in s and "-" in s), None)
                if addr is None:
                    addr = joined
                else:
                    others = [s for s in spans if s != addr]
                    community = others[0] if others else None
                d, _, st = addr.partition("-")
                district = d.strip() or None
                street = st.strip() or None

        price_node = item.css_first(".item-info-price strong")
        price = _parse_money(_text(price_node))
        extra_fee, fee_included = _parse_extra(_text(item.css_first(".item-info-price .extra-text")))
        total_monthly = (price + extra_fee) if price is not None else None

        posted_at = _rel_to_date(updated_rel or "", fetched_at)

        results.append({
            "listing_id": listing_id,
            "title": title,
            "url": url or (f"https://rent.591.com.tw/{listing_id}"),
            "image": image,
            "district": district,
            "street": street,
            "community": community,
            "kind_name": kind_name or None,
            "rooms": rooms,
            "halls": halls,
            "baths": baths,
            "size_ping": size_ping,
            "floor": floor,
            "total_floor": total_floor,
            "price": price,
            "extra_fee": extra_fee,
            "fee_included": fee_included,
            "total_monthly": total_monthly,
            "tags": tags,
            "poster_type": poster_type,
            "poster_name": poster_name,
            "updated_rel": updated_rel,
            "posted_at": posted_at,
            "first_seen": fetched_iso,
            "last_seen": fetched_iso,
            "status": "active",
        })

    return results
