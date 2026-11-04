"""Generic reader for online-shop listing pages.

Instead of depending on one site's CSS class names (which change), it:
  1. reads schema.org Product data (JSON-LD) when a page has it, and
  2. otherwise finds every link to a product page, walks up to the smallest
     box around it that also contains a price, and reads name/price/photo there.
Each shop can still pin exact CSS selectors in config/shops.yaml if needed.
"""
from __future__ import annotations

import json
import logging
import re
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

from bs4 import BeautifulSoup, Tag

from ..models import Offer
from ..net import Blocked, Http
from ..text import find_prices

log = logging.getLogger(__name__)

PLACEHOLDER_IMG = re.compile(r"loader|placeholder|blank|spacer|lazy|no-?image|default", re.I)
IMG_ATTRS = ("data-src", "data-original", "data-lazy", "data-lazy-src", "data-srcset", "srcset", "src")


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _img(el: Tag, base: str) -> str:
    for img in el.find_all(["img", "source"]):
        for a in IMG_ATTRS:
            v = (img.get(a) or "").strip()
            if not v:
                continue
            v = v.split(",")[-1].strip().split(" ")[0] if "srcset" in a else v
            if v.startswith("data:") or PLACEHOLDER_IMG.search(v):
                continue
            return urljoin(base, v)
    return ""


def jsonld_products(page: BeautifulSoup, base: str) -> list[dict]:
    out = []

    def walk(o):
        if isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            t = o.get("@type")
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                offers = o.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = offers.get("price") or offers.get("lowPrice")
                img = o.get("image")
                if isinstance(img, list):
                    img = img[0] if img else ""
                if isinstance(img, dict):
                    img = img.get("url", "")
                if o.get("name") and price:
                    out.append({"name": o["name"], "price": float(str(price).replace(",", ".")),
                                "url": urljoin(base, o.get("url") or ""), "image": img or "",
                                "barcode": str(o.get("gtin13") or o.get("gtin") or "")})
            for v in o.values():
                if isinstance(v, (list, dict)):
                    walk(v)

    for s in page.find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(s.string or ""))
        except (ValueError, TypeError):
            continue
    return out


def cards(page: BeautifulSoup, base: str, product_link: str, selectors: dict | None = None) -> list[dict]:
    """Find product cards on a listing page."""
    selectors = selectors or {}
    link_re = re.compile(product_link)
    found: dict[str, dict] = {}

    if selectors.get("card"):
        boxes = page.select(selectors["card"])
        for box in boxes:
            a = box.find("a", href=link_re)
            if a:
                _read_box(box, a, base, found, selectors)
        return list(found.values())

    for a in page.find_all("a", href=link_re):
        href = urljoin(base, a["href"]).split("#")[0]
        if href in found:
            continue
        box = a
        for _ in range(7):
            parent = box.parent
            if not isinstance(parent, Tag) or parent.name in ("body", "html"):
                break
            other = {urljoin(base, x["href"]).split("#")[0] for x in parent.find_all("a", href=link_re)}
            if len(other) > 1:
                break  # parent holds several products -> box is the card
            box = parent
            if find_prices(box.get_text(" ", strip=True)):
                break
        _read_box(box, a, base, found, selectors)
    return list(found.values())


def _read_box(box: Tag, a: Tag, base: str, found: dict, sel: dict):
    href = urljoin(base, a["href"]).split("#")[0]
    if sel.get("price"):
        ptxt = " ".join(e.get_text(" ", strip=True) for e in box.select(sel["price"]))
    else:
        # ignore "basket", "points" and per-kg unit-price lines
        ptxt = box.get_text(" ", strip=True)
    prices = find_prices(ptxt)
    if not prices:
        return
    if sel.get("name") and box.select_one(sel["name"]):
        name = box.select_one(sel["name"]).get_text(" ", strip=True)
    else:
        cands = [a.get("title"), a.get_text(" ", strip=True)]
        cands += [x.get("title") or x.get_text(" ", strip=True) for x in box.find_all("a", href=a["href"])]
        img = box.find("img", alt=True)
        cands.append(img["alt"] if img else "")
        cands = [c.strip() for c in cands if c and c.strip() and not find_prices(c)]
        name = max(cands, key=len) if cands else ""
    if not name or len(name) < 3:
        return
    found[href] = {"name": re.sub(r"\s+", " ", name), "price": min(prices), "url": href,
                   "image": _img(box, base), "barcode": ""}


def with_page(url: str, param: str, n: int) -> str:
    if "{n}" in param:  # path style, e.g. "page/{n}/"
        return url.rstrip("/") + "/" + param.format(n=n)
    parts = urlsplit(url)
    q = dict(parse_qsl(parts.query))
    q[param] = str(n)
    return urlunsplit(parts._replace(query=urlencode(q)))


def discover_categories(http: Http, cfg: dict) -> list[str]:
    base = cfg["base_url"]
    urls = list(cfg.get("category_urls") or [])
    pattern = cfg.get("category_link")
    if pattern:
        try:
            page = soup(http.text(cfg.get("start_url", base)))
            rx = re.compile(pattern)
            for a in page.find_all("a", href=rx):
                urls.append(urljoin(base, a["href"]).split("#")[0])
        except Exception as e:  # noqa: BLE001
            log.warning("%s: could not read menu (%s)", cfg["id"], e)
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[: int(cfg.get("max_categories", 400))]


def scrape(http: Http, cfg: dict) -> list[Offer]:
    base = cfg["base_url"]
    page_param = cfg.get("page_param", "page")
    max_pages = int(cfg.get("max_pages", 60))
    items: dict[str, dict] = {}
    cats = discover_categories(http, cfg)
    log.info("%s: %d listing pages to read", cfg["id"], len(cats))
    for cat_url in cats:
        cat_name = urlsplit(cat_url).path.rstrip("/").split("/")[-1]
        seen_on_cat: set[str] = set()
        for n in range(1, max_pages + 1):
            url = cat_url if n == 1 else with_page(cat_url, page_param, n)
            try:
                page = soup(http.text(url))
            except Blocked as e:
                log.warning("%s: %s", cfg["id"], e)
                break
            except Exception as e:  # noqa: BLE001
                status = getattr(getattr(e, "response", None), "status_code", None)
                if not (n > 1 and status == 404):   # 404 after page 1 = past the last page
                    log.warning("%s: %s failed: %s", cfg["id"], url, e)
                break
            found = jsonld_products(page, url) or cards(page, url, cfg["product_link"], cfg.get("selectors"))
            new = [f for f in found if f["url"] not in seen_on_cat]
            if not new:
                break  # page past the end, or the site ignores the page number
            for f in new:
                seen_on_cat.add(f["url"])
                f.setdefault("category", cat_name)
                items.setdefault(f["url"], f)
            if cfg.get("single_page"):
                break
    log.info("%s: %d products", cfg["id"], len(items))
    return [to_offer(cfg, f) for f in items.values()]


def to_offer(cfg: dict, f: dict) -> Offer:
    name, barcode = split_barcode(f["name"])
    return Offer(source=cfg["id"], side=cfg["side"], store=cfg["store"], name=name,
                 price=float(f["price"]), currency=cfg.get("currency", "TRY"), url=f["url"],
                 image=f.get("image", ""), category=f.get("category", ""),
                 barcode=f.get("barcode") or barcode, town=cfg.get("town", ""),
                 maps=cfg.get("maps", ""))


def split_barcode(name: str) -> tuple[str, str]:
    """Some shops put the barcode in front of the name: '8692005190019 KOOP SÜT 1 LT'."""
    m = re.match(r"^\s*(\d{6,14})\s+(.+)$", name)
    if m:
        return m.group(2).strip(), m.group(1) if len(m.group(1)) in (8, 12, 13, 14) else ""
    return name.strip(), ""
