"""South Cyprus fresh produce and meat: the Consumer Protection Service's monthly
price observatory (weighted average price of ~250 products in ~400 shops).
The report is a PDF linked from an announcement on consumer.gov.cy. Only the
per-kg fresh items are used (shown as "South Cyprus average")."""
from __future__ import annotations

import io
from urllib.parse import urljoin
import logging
import re
from datetime import date

from ..models import Offer
from ..net import Http

log = logging.getLogger(__name__)
BASE = "https://consumer.gov.cy"
TITLE = "Παρατηρητήριο Τιμών Βασικών Καταναλωτικών Προϊόντων"
MONTHS = {"Ιανουάριος": 1, "Φεβρουάριος": 2, "Μάρτιος": 3, "Απρίλιος": 4, "Μάιος": 5, "Μαίος": 5, "Ιούνιος": 6,
          "Ιούλιος": 7, "Αύγουστος": 8, "Σεπτέμβριος": 9, "Οκτώβριος": 10, "Νοέμβριος": 11, "Δεκέμβριος": 12}
EN_MONTH = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Greek report name (start of the line, accents removed, lower case) -> English name used for matching
NAMES = [
    ("ντοματες", "Tomatoes"), ("πατατες", "Potatoes"), ("αγγουρακια θερμοκηπιου", "Cucumbers (greenhouse)"),
    ("αγγουρακια χωραφιου", "Cucumbers"), ("κρεμμυδια", "Onions"), ("καροτα", "Carrots"), ("λεμονια", "Lemons"),
    ("μπανανες", "Bananas"), ("μηλα", "Apples"), ("πορτοκαλια", "Oranges"), ("μανταρινια", "Mandarins"),
    ("αχλαδια", "Pears"), ("σταφυλια", "Grapes"), ("ακτινιδια", "Kiwi"), ("κολοκυθακια", "Courgettes"),
    ("μελιτζανες", "Aubergines"), ("πιπεριες", "Peppers"), ("μανιταρια", "Mushrooms"), ("λαχανο", "Cabbage"),
    ("κουνουπιδι", "Cauliflower"), ("μπροκολο", "Broccoli"), ("παντζαρια", "Beetroot"),
    ("βοδινος κιμας", "Beef mince"), ("βοδινο", "Beef (boneless)"), ("κοτοπουλο ολοκληρο", "Whole chicken"),
    ("κοτοπουλο στηθος", "Chicken breast fillet"), ("κοτοπουλο μπουτι", "Chicken legs"),
    ("χοιρινος κιμας", "Pork mince"), ("χοιρινη μπριζολα", "Pork chops"), ("αμνοεριφια", "Lamb"),
    ("συκωτι", "Chicken liver"),
]


def _plain(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def find_report(http: Http, today: date, months_back: int = 4) -> tuple[str, str] | None:
    """(pdf url, 'Sep 2026') of the newest monthly observatory."""
    best = None
    y, m = today.year, today.month
    for _ in range(months_back):
        listing = f"{BASE}/en/press-room/announcements/?archive={m}-{y}"   # (the site counts months from 0)
        page = http.text(listing)
        for href in dict.fromkeys(re.findall(r'href="([^"]*/announcements/\d+/\?ctype=ar)"', page)):
            href = urljoin(listing, href)
            art = http.text(href)
            t = re.search(TITLE + r"\s*-\s*(\w+)\s+(\d{4})", art)
            pdf = re.search(r'href="([^"]+\.pdf)"', art)
            if not (t and pdf) or t.group(1) not in MONTHS:
                continue
            key = (int(t.group(2)), MONTHS[t.group(1)])
            if not best or key > best[0]:
                url = urljoin(href, pdf.group(1))
                best = (key, url, f"{EN_MONTH[key[1]]} {key[0]}")
        if best:
            break
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return (best[1], best[2]) if best else None


ROW = re.compile(r"^\s*\d+\s+(.+?)\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})\s*$")


def parse_rows(text: str) -> list[tuple[str, float, float, float]]:
    """(english name, highest, lowest, weighted average) for per-kg fresh rows."""
    out = []
    for line in text.splitlines():
        m = ROW.match(line)
        if not m or "(kg)" not in m.group(1).lower():
            continue
        g = _plain(m.group(1))
        eng = next((e for k, e in NAMES if g.startswith(k)), None)
        if eng:
            hi, lo, avg = (float(x.replace(",", ".")) for x in m.groups()[1:])
            out.append((eng, hi, lo, avg))
    return out


def scrape(http: Http, cfg: dict) -> list[Offer]:
    found = find_report(http, date.today())
    if not found:
        log.warning("observatory: no monthly report found")
        return []
    url, month = found
    import pdfplumber
    data = http.get(url).content
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    rows = parse_rows(text)
    log.info("observatory: %s, %d fresh per-kg rows", month, len(rows))
    seen = set()
    offers = []
    for eng, hi, lo, avg in rows:
        if eng in seen:
            continue
        seen.add(eng)
        offers.append(Offer(source="observatory", side="S", store="South Cyprus average (gov. price report)",
                            name=f"{eng} 1 kg", price=avg, currency="EUR", url=url,
                            town=f"Average of ~400 shops, {month} (lowest €{lo:.2f})", category="Fresh",
                            extra={"lowest": lo, "highest": hi}))
    return offers
