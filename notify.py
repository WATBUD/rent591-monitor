"""通知：Telegram Bot 推播。

Token 與 chat_id 從環境變數讀取（GitHub Actions 以 Secrets 注入），
不寫進 repo。format_report 為純函式，方便測試排版。
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict

import httpx

log = logging.getLogger(__name__)

TG_API = "https://api.telegram.org/bot{token}/sendMessage"
TG_MAX_CHARS = 3800  # Telegram 上限 4096，留餘裕


def _fmt_listing(r: dict) -> str:
    spec = []
    if r.get("rooms"):
        spec.append(f"{r['rooms']}房")
    if r.get("size_ping"):
        spec.append(f"{r['size_ping']}坪")
    if r.get("floor"):
        spec.append(str(r["floor"]))
    spec_txt = "／".join(spec)
    return f"· {r.get('title', '')} ${r.get('total_monthly')}／月（{spec_txt}）\n  {r.get('url', '')}"


def _group_by_district(rows: list[dict]) -> dict[str, list[dict]]:
    g: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        g[r.get("district") or "其他"].append(r)
    return g


def format_report(report: dict, header: str = "591 租屋監控") -> str | None:
    """把 diff 報告排成通知文字；無任何變動時回 None（代表不需通知）。"""
    new, drop, removed = report["new"], report["price_drop"], report["removed"]
    if not (new or drop or removed):
        return None

    lines = [f"🔔 {header}", f"🆕 新增 {len(new)}｜💰 降價 {len(drop)}｜❌ 下架 {len(removed)}"]

    if new:
        lines.append("\n🆕 新增")
        for district, rows in _group_by_district(new).items():
            lines.append(f"📍{district}")
            lines.extend(_fmt_listing(r) for r in rows)

    if drop:
        lines.append("\n💰 降價")
        for district, rows in _group_by_district(drop).items():
            lines.append(f"📍{district}")
            for r in rows:
                lines.append(
                    f"· {r.get('title', '')} ${r['old_price']}→${r['new_price']}"
                    f"（↓{r['drop_pct']}%）\n  {r.get('url', '')}"
                )

    if removed:
        lines.append("\n❌ 下架")
        for district, rows in _group_by_district(removed).items():
            lines.append(f"📍{district}")
            lines.extend(f"· {r.get('title', '')}" for r in rows)

    return "\n".join(lines)


def _chunk(text: str, limit: int = TG_MAX_CHARS) -> list[str]:
    """依行切成不超過 limit 的訊息塊，避免超過 Telegram 上限。"""
    chunks, buf = [], ""
    for line in text.split("\n"):
        if len(buf) + len(line) + 1 > limit and buf:
            chunks.append(buf)
            buf = ""
        buf += line + "\n"
    if buf.strip():
        chunks.append(buf)
    return chunks


def send(text: str | None) -> bool:
    """把通知文字送到 Telegram。未設定 token/chat_id 或無內容則略過並回 False。"""
    if not text:
        log.info("本輪無變動，不發送通知。")
        return False
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.warning("未設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID，略過推播。以下為內容預覽：\n%s", text)
        return False

    ok = True
    with httpx.Client(timeout=20) as client:
        for chunk in _chunk(text):
            try:
                resp = client.post(
                    TG_API.format(token=token),
                    json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
                )
                resp.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                log.error("Telegram 推播失敗：%s", exc)
                ok = False
    return ok
