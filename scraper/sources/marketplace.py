"""Online marketplaces whose product pages carry schema.org Product data (JSON-LD):
name, price, currency, seller and often the barcode.

Used for North Cyprus marketplaces such as Kıbrıs Online Market (several local
supermarkets on one site) and Girince. Their sitemaps list every product page.
There are too many pages to read in one day, so, like the Fetch reader, this keeps
what it has read in data/raw/<shop id>_cache.json and reads up to `pages_per_day`
pages a day: new pages first, then the oldest prices again after `refresh_days`.

Settings (config/shops.yaml):
  sitemap        sitemap or sitemap index address
  url_include    regex an address must match (e.g. "/m/" or "^https://girince.com/urun/")
  url_exclude    regex for addresses to skip
  other_side_brands: true
                 only read pages whose address contains a brand sold on the other side
                 (worth it on big general marketplaces: only those can be compared)
  currency       TRY or EUR
  seller_include / seller_exclude   regex on the seller name
  store_from_path  regex with one group taking the shop name out of the address
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from ..match import Matcher
from ..models import Offer
from ..net import Http
from ..text import fold, tokens
from .shop_html import soup

log = logging.getLogger(__name__)
RAW = Path(__file__).resolve().parents[2] / "data" / "raw"


def sitemap_urls(http: Http, url: str, depth: int = 0) -> list[str]:
    """All page addresses in a sitemap, following sitemap indexes."""
    xml = http.text(url)
    locs = [l.replace("&amp;", "&").strip() for l in re.findall(r"<loc>([^<]+)</loc>", xml)]
    if "<sitemapindex" in xml and depth < 2:
        out = []
        for sm in locs:
            try:
                out += sitemap_urls(http, sm, depth + 1)
            except Exception as e:  # noqa: BLE001
                log.warning("sitemap %s failed: %s", sm, e)
        return out
    return locs


def _title(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.replace("-", " ").split())


def parse_page(html: str, url: str, cfg: dict) -> list[Offer]:
    """Offers from one product page's JSON-LD."""
    page = soup(html)
    sid, side, cur = cfg.get("id", "marketplace"), cfg.get("side", "N"), str(cfg.get("currency", "TRY")).upper()
    category, out = "", []
    store_rx = cfg.get("store_from_path")
    path_store = ""
    if store_rx:
        m = re.search(store_rx, url)
        path_store = _title(m.group(1)) if m else ""
    for s in page.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
        except (ValueError, TypeError):
            continue
        items = data if isinstance(data, list) else (data.get("@graph") if isinstance(data, dict) and "@graph" in data else [data])
        for d in items:
            if isinstance(d, dict) and d.get("@type") == "BreadcrumbList":
                names = [x.get("name", "") for x in d.get("itemListElement") or []]
                category = names[-2] if len(names) >= 3 else category
                continue
            if not isinstance(d, dict) or d.get("@type") != "Product":
                continue
            category = d.get("category") or category
            offers = d.get("offers") or []
            offers = offers if isinstance(offers, list) else [offers]
            if offers and offers[0].get("@type") == "AggregateOffer":
                offers = offers[0].get("offers") or [{"price": offers[0].get("lowPrice"), **offers[0]}]
            img = d.get("image")
            img = img[0] if isinstance(img, list) and img else (img if isinstance(img, str) else "")
            gtin = str(d.get("gtin13") or d.get("gtin") or "")
            for of in offers:
                price = of.get("price")
                if price in (None, "") or str(of.get("priceCurrency", cur)).upper() != cur:
                    continue
                if "OutOfStock" in str(of.get("availability", "")):
                    continue
                seller = (of.get("seller") or {}).get("name") or path_store or cfg.get("store", sid)
                try:
                    p = float(price)
                except (TypeError, ValueError):
                    continue
                if p <= 0:
                    continue
                town = ""
                desc = d.get("description") or ""
                m = re.search(r"—\s*[^,.]+,\s*([^.]+)\.", desc)       # "… — Hapcı Market, Girne. Online sipariş…"
                if m:
                    town = m.group(1).strip()
                out.append(Offer(
                    source=sid, side=side, store=seller, name=(d.get("name") or "").strip(), price=p, currency=cur,
                    url=of.get("url") or url, image=img, barcode=gtin if gtin.isdigit() else "", category=category,
                    product_id=url, town=town or cfg.get("town", ""),
                    maps="https://www.google.com/maps/search/?api=1&query=" + quote_plus(f"{seller} {town} Cyprus"),
                ))
    return out


def _brand_words(other: list[Offer], mcfg: dict) -> set[str]:
    """Brands sold on the other side, as they appear in web addresses (lower case, hyphenated)."""
    m = Matcher(mcfg)
    words = set()
    for o in other:
        b = m.brand(o.name)
        if b:
            words.add(re.sub(r"[^a-z0-9]+", "-", fold(b)).strip("-"))
    return {w for w in words if len(w) >= 3}


def pick(urls: list[str], cfg: dict, brands: set[str] | None) -> list[str]:
    inc = re.compile(cfg.get("url_include", "."))
    exc = re.compile(cfg["url_exclude"]) if cfg.get("url_exclude") else None
    out = [u for u in urls if inc.search(u) and not (exc and exc.search(u))]
    if brands:
        def has_brand(u: str) -> bool:
            slug = "-" + u.rstrip("/").rsplit("/", 1)[-1].lower() + "-"
            return any(f"-{b}-" in slug for b in brands)
        out = [u for u in out if has_brand(u)]
    return out


def plan(cache: dict, urls: list[str], today: date, cfg: dict) -> list[str]:
    """New pages first, then pages whose price is `refresh_days` old (oldest first),
    then pages with nothing useful, after `recheck_days`."""
    refresh, recheck = int(cfg.get("refresh_days", 4)), int(cfg.get("recheck_days", 30))
    age = lambda u: (today - date.fromisoformat(cache[u]["t"])).days  # noqa: E731
    new = [u for u in urls if u not in cache]
    stale = sorted((u for u in urls if u in cache and cache[u]["offers"] and age(u) >= refresh), key=age, reverse=True)
    empty = sorted((u for u in urls if u in cache and not cache[u]["offers"] and age(u) >= recheck), key=age, reverse=True)
    return new + stale + empty


def scrape(http: Http, cfg: dict) -> list[Offer]:
    sid = cfg.get("id", "marketplace")
    cache_path = RAW / f"{sid}_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    urls = list(dict.fromkeys(sitemap_urls(http, cfg["sitemap"])))
    brands = _brand_words(cfg.get("_other") or [], cfg.get("_matching") or {}) if cfg.get("other_side_brands") else None
    if cfg.get("other_side_brands") and not brands:
        log.warning("%s: no products from the other side to choose pages by; reading cached pages only", sid)
    wanted = pick(urls, cfg, brands) if brands is not None or not cfg.get("other_side_brands") else [u for u in cache]
    today = datetime.now(timezone.utc).date()
    todo = plan(cache, wanted, today, cfg)
    budget, stop_at = int(cfg.get("pages_per_day", 3000)), time.monotonic() + 60 * float(cfg.get("max_minutes", 60))
    log.info("%s: %d pages in sitemap, %d wanted, %d in cache, %d to read, reading up to %d",
             sid, len(urls), len(wanted), len(cache), len(todo), budget)
    read = 0
    for u in todo:
        if read >= budget or time.monotonic() > stop_at:
            break
        try:
            offers = parse_page(http.text(u), u, cfg)
        except Exception as e:  # noqa: BLE001
            log.debug("%s: %s failed: %s", sid, u, e)
            continue
        read += 1
        cache[u] = {"t": today.isoformat(), "offers": [o.to_dict() for o in offers]}
        if read % 500 == 0:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            log.info("%s: %d pages read", sid, read)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    keep = int(cfg.get("keep_days", 12))
    inc = re.compile(cfg.get("seller_include", "."), re.I)
    exc = re.compile(cfg["seller_exclude"], re.I) if cfg.get("seller_exclude") else None
    out = []
    for u, c in cache.items():
        if (today - date.fromisoformat(c["t"])).days > keep:
            continue
        for d in c["offers"]:
            o = Offer.from_dict(d)
            if inc.search(o.store) and not (exc and exc.search(o.store)):
                out.append(o)
    log.info("%s: read %d pages today; %d prices in use from %d cached pages", sid, read, len(out), len(cache))
    return out
