"""Prices sent in by shoppers through the site's "Add a price" form.

The form posts to a Google Form owned by the site owner; Google saves answers
in a Google Sheet. That sheet is published as CSV (File > Share > Publish to web).
Each run:
  * every row is checked (price, barcode check digit, already on the site?,
    price close to other prices for the same product?) and listed in
    data/contributions_review.md,
  * only rows with "yes" in the sheet's Approved column are used on the site.
"""
from __future__ import annotations

import csv
import io
import logging
import re
from pathlib import Path

from .models import Offer
from .net import Http
from .text import fold, parse_number, parse_size

log = logging.getLogger(__name__)
YES = {"yes", "y", "evet", "ok", "true", "1", "approved", "✓", "✔"}
NO = {"no", "n", "hayir", "false", "0", "rejected", "reject", "✗"}


def ean_ok(code: str) -> bool:
    """Check digit of an EAN-8 / UPC-A / EAN-13 / EAN-14 barcode."""
    if not code.isdigit() or len(code) not in (8, 12, 13, 14):
        return False
    digits = [int(c) for c in code]
    total = sum(d * (1 if i % 2 else 3) for i, d in enumerate(reversed(digits[:-1])))
    return (10 - total % 10) % 10 == digits[-1]


def _col(row: dict, *names):
    low = {fold(k).strip(): v for k, v in row.items() if k}
    for n in names:
        v = low.get(fold(n))
        if v not in (None, ""):
            return str(v).strip()
    return ""


def read_rows(http: Http, url: str) -> list[dict]:
    text = Http(delay=0, obey_robots=False).text(url) if url else ""   # the owner's own sheet
    return list(csv.DictReader(io.StringIO(text))) if text else []


def to_offer(row: dict) -> Offer | None:
    side = _col(row, "Side", "Taraf").upper()[:1]
    side = {"K": "N", "G": "S"}.get(side, side)             # Kuzey / Güney
    price = parse_number(re.sub(r"[^\d.,]", "", _col(row, "Price", "Fiyat")) or "")
    product = _col(row, "Product", "Ürün")
    if side not in ("N", "S") or not price or price <= 0 or not product:
        return None
    size = _col(row, "Pack size", "Size")
    name = product if not size or parse_size(product) else f"{product} {size}"
    cur = _col(row, "Currency").upper()
    cur = "TRY" if cur.startswith(("T", "₺", "L")) else "EUR" if cur.startswith(("E", "€")) else ("TRY" if side == "N" else "EUR")
    code = re.sub(r"\D", "", _col(row, "Barcode", "Barkod"))
    shop = _col(row, "Shop", "Store", "Market") or "Shop (shopper report)"
    town = _col(row, "Town", "City")
    date = _col(row, "Timestamp", "Date")[:10]
    return Offer(source="contrib", side=side, store=shop, name=name, price=price, currency=cur,
                 barcode=code if ean_ok(code) else "",
                 product_id=f"gtin-{code}" if side == "S" and ean_ok(code) else "",
                 town=(town + " · " if town else "") + "added by a shopper",
                 maps="https://www.google.com/maps/search/?api=1&query=" + "+".join((shop + " " + town).split()),
                 extra={"date": date, "contributed": True})


def load(http: Http, cfg: dict, known: dict, root: Path) -> list[Offer]:
    """Approved shopper prices. `known` maps barcode -> (item name, {side: [eur prices]}) for checks."""
    url = (cfg or {}).get("csv_url", "")
    if not url:
        return []
    try:
        rows = read_rows(http, url)
    except Exception as e:  # noqa: BLE001
        log.warning("contributions: could not read the sheet (%s)", e)
        return []
    approved, lines = [], []
    for i, row in enumerate(rows, start=2):   # row 1 is the header in the sheet
        status = fold(_col(row, "Approved", "Onay"))
        o = to_offer(row)
        if status in YES and o:
            approved.append(o)
            continue
        if status in NO:
            continue
        lines.append(review_line(i, row, o, known))
    report = ["# Shopper prices waiting for review", "",
              "Type **yes** in the *Approved* column of the sheet to publish a row, **no** to hide it.", ""]
    report += lines or ["Nothing waiting."]
    (root / "data" / "contributions_review.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    log.info("contributions: %d approved, %d waiting for review", len(approved), len(lines))
    return approved


def review_line(rownum: int, row: dict, o: Offer | None, known: dict) -> str:
    who = f"Row {rownum}: {_col(row, 'Product')!r} at {_col(row, 'Shop')!r} ({_col(row, 'Side')}) " \
          f"{_col(row, 'Price')} {_col(row, 'Currency')}"
    if not o:
        return f"- {who} - ❌ incomplete (needs side, product and a price)"
    notes = []
    code = re.sub(r"\D", "", _col(row, "Barcode", "Barkod"))
    if code and not ean_ok(code):
        notes.append("⚠️ barcode check digit is wrong (mistyped?)")
    if o.barcode and o.barcode in known:
        name, prices = known[o.barcode]
        notes.append(f"✅ same barcode as '{name}' on the site")
        same = prices.get(o.side) or []
        if same:
            eur = o.price if o.currency == "EUR" else None
            if eur is not None:
                lo, hi = min(same), max(same)
                ok = 0.5 * lo <= eur <= 2 * hi
                notes.append(("✅" if ok else "⚠️") + f" other {o.side} prices €{lo:.2f}-€{hi:.2f}")
    elif o.barcode:
        notes.append("ℹ️ new product (barcode not on the site yet) - only shows once the other side has it too")
    else:
        notes.append("ℹ️ no barcode - will be paired by name")
    return f"- {who} - " + "; ".join(notes)
