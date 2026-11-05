"""South Cyprus: Fetch (fetch.com.cy), a delivery marketplace for hundreds of South shops.

Fetch lists ~290,000 product pages in its sitemap. Reading them all daily is not
practical, so this reader:
  1. downloads the sitemap (product names are readable in the addresses,
     e.g. /p/pringles-original-165g),
  2. keeps only addresses whose brand and pack size match a product sold in the
     North (from data/raw), so only likely pairs are read,
  3. reads those product pages; each has schema.org Product data with the price,
     the seller and the barcode (GTIN).
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from urllib.parse import quote_plus

from ..match import Matcher
from ..models import Offer
from ..net import Http
from ..text import tokens
from .shop_html import soup

log = logging.getLogger(__name__)
SITE = "https://fetch.com.cy"


def product_urls(http: Http) -> list[str]:
    idx = http.text(f"{SITE}/sitemap.xml")
    maps = [u for u in re.findall(r"<loc>([^<]+)</loc>", idx) if "sitemap-products" in u]
    urls: list[str] = []
    for m in maps:
        try:
            urls += [u for u in re.findall(r"<loc>([^<]+)</loc>", http.text(m)) if "/p/" in u]
        except Exception as e:  # noqa: BLE001
            log.warning("fetch: sitemap %s failed: %s", m, e)
    return urls


def slug_name(url: str) -> str:
    return url.rstrip("/").rsplit("/p/", 1)[-1].replace("-", " ")


def candidates(urls: list[str], north: list[Offer], mcfg: dict, limit: int) -> list[str]:
    """Product pages whose name has the same brand and pack size as a North product."""
    m = Matcher(mcfg)
    first_n = defaultdict(int)
    for o in north:
        t = tokens(o.name)
        if t:
            first_n[t[0]] += 1
    known = {a for a, _ in m.brand_aliases}
    for w, n in first_n.items():   # brands not in the list: first words common in North names
        if n >= 3 and len(w) >= 3 and not w.isdigit() and w not in known | m.generic_first | set(m.synonyms) | m.stop:
            m.brand_aliases.append((w, w.title()))
    m.brand_aliases.sort(key=lambda x: -len(x[0]))

    by_brand = defaultdict(list)
    for o in north:
        k = m.key(o)
        if k.brand and k.size:
            by_brand[k.brand].append(k)
    from ..match import Key
    scored = []
    for u in urls:
        k = m.key(Offer(source="", side="S", store="", name=slug_name(u), price=0, currency="EUR"))
        if not k.brand or not k.size or not k.size.total or k.brand not in by_brand:
            continue
        best = max((m.score(nk, k) for nk in by_brand[k.brand]), default=0)
        if best > 0:
            scored.append((2 + best, u))          # same pack size: read first
            continue
        # similar pack size (compared per kg / litre on the site)
        for nk in by_brand[k.brand]:
            if nk.size.unit != k.size.unit or not 0.4 <= nk.size.total / k.size.total <= 2.5:
                continue
            ca, cn = k.words - m.filler, nk.words - m.filler
            if (ca <= cn or cn <= ca) and len(ca ^ cn) <= 1 and m.score(Key(nk.brand, k.size, nk.words), k) >= 0.7:
                scored.append((1, u))
                break
    scored.sort(key=lambda x: -x[0])
    log.info("fetch: %d of %d product pages look like North products", len(scored), len(urls))
    return [u for _, u in scored[:limit]]


def read_product(http: Http, url: str) -> list[Offer]:
    page = soup(http.text(url))
    out = []
    category = ""
    for s in page.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
        except (ValueError, TypeError):
            continue
        for d in data if isinstance(data, list) else [data]:
            if isinstance(d, dict) and d.get("@type") == "BreadcrumbList":
                names = [x.get("name", "") for x in d.get("itemListElement") or []]
                category = names[-2] if len(names) >= 3 else (names[-1] if names else "")
                continue
            if not isinstance(d, dict) or d.get("@type") != "Product":
                continue
            offers = d.get("offers") or []
            offers = offers if isinstance(offers, list) else [offers]
            if offers and offers[0].get("@type") == "AggregateOffer":
                offers = offers[0].get("offers") or [{"price": offers[0].get("lowPrice"), **offers[0]}]
            img = d.get("image")
            img = img[0] if isinstance(img, list) and img else (img if isinstance(img, str) else "")
            gtin = str(d.get("gtin13") or d.get("gtin") or d.get("sku") or "")
            for of in offers:
                price = of.get("price")
                if price in (None, "") or str(of.get("priceCurrency", "EUR")).upper() != "EUR":
                    continue
                if "OutOfStock" in str(of.get("availability", "")):
                    continue
                seller = (of.get("seller") or {}).get("name") or "Fetch"
                out.append(Offer(
                    source="fetch", side="S", store=seller, name=d.get("name", ""), price=float(price),
                    currency="EUR", url=of.get("url") or url, image=img, barcode=gtin if gtin.isdigit() else "",
                    category=category,
                    product_id=f"gtin-{gtin}" if gtin.isdigit() else url, town="Cyprus (Fetch delivery)",
                    maps="https://www.google.com/maps/search/?api=1&query=" + quote_plus(f"{seller} Cyprus"),
                ))
    return out


def scrape(http: Http, cfg: dict) -> list[Offer]:
    north = cfg.get("_north") or []
    if not north:
        log.warning("fetch: no North products available to pick candidates from")
        return []
    urls = product_urls(http)
    picks = candidates(urls, north, cfg.get("_matching", {}), int(cfg.get("max_products", 2500)))
    offers: list[Offer] = []
    for i, u in enumerate(picks, 1):
        try:
            offers += read_product(http, u)
        except Exception as e:  # noqa: BLE001
            log.warning("fetch: %s failed: %s", u, e)
        if i % 250 == 0:
            log.info("  fetch: %d / %d pages, %d prices", i, len(picks), len(offers))
    return offers
