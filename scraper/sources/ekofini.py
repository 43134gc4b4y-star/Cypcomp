"""South Cyprus: e-kofini, the Department of Agriculture's fruit and vegetable price observatory.

Officers record prices twice a week; the "Daily price" report on my.e-kofini.gov.cy is a plain
HTML table with the average producer price and the average supermarket (retail) price per kg
for about 25 local fruits and vegetables. Only the retail price is used.
robots.txt allows everything; one page is read per day.
"""
from __future__ import annotations

import logging
import re

from ..models import Offer
from ..net import Http
from .shop_html import soup

log = logging.getLogger(__name__)
URL = "https://my.e-kofini.gov.cy/reports/daily-price"

# e-kofini's English name -> the name the per-kg "any brand" rules look for (config/generic_items.yaml)
NAMES = {
    "tomatoes": "Tomatoes", "potatoes": "Potatoes", "cucumber": "Cucumbers", "onions (fresh bulb)": "Onions",
    "carrots": "Carrots", "bananas (local produce)": "Bananas", "zucchini (dark green)": "Courgettes",
    "eggplants (black)": "Aubergines", "cabbage (white)": "Cabbage", "cauliflower": "Cauliflower", "broccoli": "Broccoli",
    "avocado": "Avocados", "peppers (green)": "Green peppers", "sweet potato": "Sweet potatoes", "beans (fresh)": "Green beans",
    "cherry tomatoes": "Cherry tomatoes", "peaches": "Peaches", "nectarines": "Nectarines", "melons": "Melons",
    "watermelons": "Watermelons", "apricots": "Apricots", "cherries": "Cherries", "plums (black)": "Plums",
    "strawberries (lowland produce)": "Strawberries", "lemons": "Lemons", "oranges": "Oranges", "mandarins": "Mandarins",
    "grapes": "Grapes", "apples": "Apples", "pears": "Pears",
}


def _eur(s: str) -> float | None:
    m = re.search(r"€\s*([\d.,]+)", s)
    return float(m.group(1).replace(",", "")) if m else None


def parse(html: str) -> list[Offer]:
    page = soup(html)
    text = page.get_text(" ")
    m = re.search(r"\((?:€|&euro;)/kg\)\s*(\d{2}/\d{2}/\d{4})", text) or re.search(r"(\d{2}/\d{2}/\d{4})", text)
    day = m.group(1) if m else ""
    out = []
    for tr in page.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 3 or "€" not in cells[-1]:
            continue
        label = cells[0]
        en = label.split(" - ", 1)[-1].replace("*", "").strip()
        name = NAMES.get(en.lower())
        retail = _eur(cells[-1])
        if not name or not retail:
            continue
        out.append(Offer(
            source="ekofini", side="S", store="South supermarkets average (e-kofini, gov.)", name=f"{name} 1 kg",
            price=retail, currency="EUR", url=URL, category="Fresh",
            town=f"Average supermarket price, {day}" if day else "Average supermarket price",
            extra={"producer_price": _eur(cells[1]) if len(cells) > 2 else None, "greek": label.split(" - ", 1)[0]},
        ))
    return out


def scrape(http: Http, cfg: dict) -> list[Offer]:
    offers = parse(http.text(cfg.get("url", URL)))
    log.info("ekofini: %d fruit and vegetable prices", len(offers))
    return offers
