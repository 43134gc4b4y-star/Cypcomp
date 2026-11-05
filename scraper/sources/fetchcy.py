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
import time
from datetime import date, datetime, timezone
from pathlib import Path
from collections import defaultdict
from urllib.parse import quote_plus

from ..match import Key, Matcher
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
    """Product pages whose name has the same brand and pack size as a North product (best first)."""
    scored = _scored(urls, north, mcfg)
    scored.sort(key=lambda x: -x[0])
    log.info("fetch: %d of %d product pages look like North products", len(scored), len(urls))
    return [u for _, u in scored[:limit]]


def _matcher(mcfg: dict, north: list[Offer]) -> Matcher:
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
    return m


def _scored(urls: list[str], north: list[Offer], mcfg: dict) -> list[tuple[float, str]]:
    m = _matcher(mcfg, north)
    by_brand = defaultdict(list)
    for o in north:
        k = m.key(o)
        if k.brand and k.size:
            by_brand[k.brand].append(k)
    scored = []
    for u in urls:
        k = m.key(Offer(source="", side="S", store="", name=slug_name(u), price=0, currency="EUR"))
        if not k.brand or not k.size or not k.size.total or k.brand not in by_brand:
            continue
        best = max((m.score(nk, k) for nk in by_brand[k.brand]), default=0)
        if best > 0:
            scored.append((2 + best, u))          # same pack size in the address
            continue
        # close pack size in the address: often the page itself shows the same size as the North product
        for nk in by_brand[k.brand]:
            if nk.size.unit != k.size.unit or not 0.4 <= nk.size.total / k.size.total <= 2.5:
                continue
            ca, cn = k.words - m.filler, nk.words - m.filler
            if (ca <= cn or cn <= ca) and len(ca ^ cn) <= 1 and m.score(Key(nk.brand, k.size, nk.words), k) >= 0.7:
                scored.append((1, u))
                break
    return scored


def brand_urls(urls: list[str], north: list[Offer], mcfg: dict) -> list[str]:
    """Wider net: any page whose name starts with / contains a North brand, whatever its size.
    Many Fetch addresses leave out the pack size, which is only on the page itself."""
    m = _matcher(mcfg, north)
    brands = {m.key(o).brand for o in north} - {None, ""}
    out = []
    for u in urls:
        k = m.key(Offer(source="", side="S", store="", name=slug_name(u), price=0, currency="EUR"))
        if k.brand in brands:
            out.append(u)
    return out



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


def staple_urls(urls: list[str], words: list[str], per_word: int) -> list[str]:
    """Pages for everyday any-brand items, e.g. every '/p/...-white-sugar-...' address (capped per word)."""
    out: list[str] = []
    for w in words:
        hits = [u for u in urls if f"-{w}-" in "-" + u.rsplit("/p/", 1)[-1].strip("/") + "-"]
        out += sorted(hits, key=len)[:per_word]
    return list(dict.fromkeys(out))


CACHE = Path(__file__).resolve().parents[2] / "data" / "raw" / "fetch_cache.json"


def _seller_ok(cfg: dict):
    inc = re.compile(cfg.get("seller_include") or ".", re.I)
    exc = re.compile(cfg["seller_exclude"], re.I) if cfg.get("seller_exclude") else None
    return lambda name: bool(inc.search(name)) and not (exc and exc.search(name))


def plan(cache: dict, likely: list[str], staples: list[str], wide: list[str], today: date, cfg: dict) -> list[str]:
    """Which pages to read today, most useful first:
    1. likely pairs (same brand + size) and staples never read yet,
    2. pages that had a supermarket price, once they are `refresh_days` old,
    3. the wider net (any page of a North brand), oldest first, re-checked every `recheck_days`."""
    refresh, recheck = int(cfg.get("refresh_days", 3)), int(cfg.get("recheck_days", 21))
    age = lambda u: (today - date.fromisoformat(cache[u]["t"])).days if u in cache else 10**6  # noqa: E731
    first = [u for u in dict.fromkeys(likely + staples) if u not in cache]
    stale = sorted((u for u, c in cache.items() if c["offers"] and age(u) >= refresh), key=age, reverse=True)
    wide = sorted((u for u in dict.fromkeys(likely + staples + wide)
                   if u not in cache or (not cache[u]["offers"] and age(u) >= recheck)), key=age, reverse=True)
    return list(dict.fromkeys(first + stale + wide))


def scrape(http: Http, cfg: dict) -> list[Offer]:
    """Reads up to `pages_per_day` pages (or `max_minutes`), keeping what it learns in
    data/raw/fetch_cache.json, so the number of products grows day by day."""
    north = cfg.get("_north") or []
    if not north:
        log.warning("fetch: no North products available to pick candidates from")
        return []
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    urls = product_urls(http)
    # (the sitemap is sometimes incomplete, so pages missing from it are kept; old prices expire via keep_days)
    prev_raw = CACHE.parent / "fetch.json"
    known_good = [d["url"] for d in json.loads(prev_raw.read_text(encoding="utf-8"))["offers"]] if prev_raw.exists() else []
    mcfg = cfg.get("_matching", {})
    likely = candidates(urls, north, mcfg, 10**9)
    staples = staple_urls(urls, cfg.get("staples") or [], int(cfg.get("staples_per_word", 40)))
    wide = brand_urls(urls, north, mcfg)
    today = datetime.now(timezone.utc).date()
    todo = plan(cache, list(dict.fromkeys(known_good + likely)), staples, wide, today, cfg)
    budget, stop_at = int(cfg.get("pages_per_day", 6000)), time.monotonic() + 60 * float(cfg.get("max_minutes", 180))
    log.info("fetch: %d likely, %d staple, %d brand pages; %d in cache; %d to read, reading up to %d",
             len(likely), len(staples), len(wide), len(cache), len(todo), budget)
    ok = _seller_ok(cfg)
    read = 0
    progress = cfg.get("_progress")
    every = 60 * float(cfg.get("publish_every_minutes", 10))
    next_publish = time.monotonic() + every

    def in_use():
        return [Offer.from_dict(d) for c in cache.values()
                if (today - date.fromisoformat(c["t"])).days <= int(cfg.get("keep_days", 10)) for d in c["offers"]]

    for u in todo[:budget]:
        if time.monotonic() > stop_at:
            log.info("fetch: time limit reached")
            break
        try:
            offers = [o for o in read_product(http, u) if ok(o.store)]
        except Exception as e:  # noqa: BLE001
            log.warning("fetch: %s failed: %s", u, e)
            continue
        cache[u] = {"t": today.isoformat(), "offers": [o.to_dict() for o in offers]}
        read += 1
        if read % 500 == 0:
            log.info("  fetch: %d pages read", read)
        if progress and time.monotonic() >= next_publish:     # put what was found so far on the site
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            try:
                progress(in_use())
            except Exception as e:  # noqa: BLE001
                log.warning("fetch: publishing part-way failed: %s", e)
            next_publish = time.monotonic() + every
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    out = in_use()
    log.info("fetch: read %d pages today; %d supermarket prices on %d products in use",
             read, len(out), sum(1 for c in cache.values() if c["offers"]))
    return out
