"""South Cyprus: the government's e-kalathi price observatory.

e-kalathi has a public JSON API (the one its own website uses):
  /fetch-product-list?page=&size=                     -> every product (name, category, photo, lowest price)
  /retail/fetch-retail-branch-list?productId=&sort=   -> the stores selling one product, cheapest first,
                                                         with address, GPS position and price
Note: /fetch-product-list ignores any store filter, so per-store prices must come
from the branch list. Each branch record embeds the chain's logo (~50 KB), so only
the cheapest few branches per product are fetched.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus, urljoin

from ..models import Offer
from ..net import Http

log = logging.getLogger(__name__)

SITE = "https://www.e-kalathi.gov.cy"
API = SITE + "/ekalathi-website-server/api"

# Greek chain names -> how English speakers know them
CHAIN_NAMES = {
    "ΣΚΛΑΒΕΝΙΤΗΣ": "Sklavenitis", "ΑΛΦΑΜΕΓΑ": "AlphaMega", "ΠΑΠΑΣ": "Papas", "ΚΚΟΛΙΑΣ": "Kkolias",
    "ΙΩΑΝΝΙΔΗΣ": "Ioannides", "ΣΤΕΛΙΟΣ": "Stelios", "ΚΟΚΚΙΝΟΣ": "Kokkinos", "ΠΑΠΑΓΙΑΝΝΗΣ": "Papagiannis",
    "ΑΘΗΑΙΝΙΤΗΣ": "Athienitis", "ΣΥΠΑΛ": "Sypal", "ΑΝΔΡΕΑΣ & ΑΥΓΟΥΣΤΗΣ": "Andreas & Avgoustis",
    "Ο ΚΗΠΟΣ ΤΗΣ ΕΔΕΜ": "O Kipos tis Edem", "ΤΟ ΑΛΕΤΡΙ": "To Aletri", "ΚΥΡΙΑΚΟΣ": "Kyriakos",
}


def chain_name(name: str) -> str:
    name = re.sub(r"&nbsp;|\s+", " ", name or "").strip()
    for gr, en in sorted(CHAIN_NAMES.items(), key=lambda x: -len(x[0])):
        if gr in name:
            name = name.replace(gr, en)
    return name.title() if name.isupper() else name


def dms_to_decimal(s: str) -> float | None:
    """'34°41'44.3"N' -> 34.69564; also accepts plain decimals."""
    if not s:
        return None
    s = str(s).strip()
    try:
        return float(s)
    except ValueError:
        pass
    m = re.match(r"(\d+)[°\s]+(\d+)['′\s]+([\d.]+)[\"″\s]*([NSEW])?", s)
    if not m:
        return None
    v = int(m.group(1)) + int(m.group(2)) / 60 + float(m.group(3)) / 3600
    return -v if m.group(4) in ("S", "W") else v


def maps_link(branch: dict) -> str:
    lat, lng = dms_to_decimal(branch.get("branchLatitude")), dms_to_decimal(branch.get("branchLongitude"))
    if lat and lng and 34 < lat < 36 and 32 < lng < 35:
        return f"https://www.google.com/maps/search/?api=1&query={lat:.6f},{lng:.6f}"
    q = branch.get("postalAddress") or f"{branch.get('companyName', '')} Cyprus"
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(q)


def _pick(d: dict, *keys, default=None):
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return default


def product_pages(http: Http, page_size: int, max_pages: int = 100):
    for page in range(max_pages):
        data = http.json(f"{API}/fetch-product-list?page={page}&size={page_size}&productName=")
        content = data.get("content") or []
        yield from content
        if data.get("last") or len(content) < page_size:
            break


def companies(http: Http):
    return http.json(f"{API}/fetch-companies")


def cheapest_branches(http: Http, pid, n: int) -> list[dict]:
    data = http.json(f"{API}/retail/fetch-retail-branch-list?productId={pid}&page=0&size={n}&sort=PRICE,ASC")
    rows = [b for b in (data.get("content") or []) if b.get("retailerProductPrice")]
    for b in rows:
        b.pop("companyPhotoFile", None)  # embedded logo, not needed
    return rows


def scrape(http: Http, cfg: dict) -> list[Offer]:
    page_size = int(cfg.get("page_size", 100))
    branches_per_product = int(cfg.get("branches_per_product", 8))
    skip = {s.lower() for s in cfg.get("skip_chains", [])}

    catalogue = {p["productMasterId"]: p for p in product_pages(http, page_size) if p.get("productMasterId") is not None}
    log.info("e-kalathi: %d products in catalogue", len(catalogue))

    offers: list[Offer] = []
    unsorted = 0
    for i, (pid, p) in enumerate(catalogue.items(), 1):
        try:
            rows = cheapest_branches(http, pid, branches_per_product)
        except Exception as e:  # noqa: BLE001
            log.warning("e-kalathi: product %s failed: %s", pid, e)
            continue
        prices = [b["retailerProductPrice"] for b in rows]
        if prices != sorted(prices):
            unsorted += 1
        thumb = _pick(p, "productThumbnailUrl", "productMainPhotoUrl", default="")
        for b in rows:
            store = chain_name(b.get("companyName", ""))
            if store.lower() in skip:
                continue
            offers.append(Offer(
                source="ekalathi", side="S", store=store, name=p.get("name", ""),
                price=float(b["retailerProductPrice"]), currency="EUR",
                url=f"{SITE}/product-information/{pid}",
                image=urljoin(SITE + "/", thumb) if thumb else "",
                category=p.get("productCategoryNameEnglish", ""), product_id=str(pid),
                town=chain_name(b.get("name", "")), maps=maps_link(b),
                extra={"address": b.get("postalAddress", ""), "offer": bool(b.get("isInOfferOrDiscount"))},
            ))
        if i % 50 == 0:
            log.info("  e-kalathi: %d / %d products", i, len(catalogue))
    if unsorted:
        log.warning("e-kalathi: %d products came back not sorted by price - "
                    "'cheapest' may be missed; raise branches_per_product", unsorted)
    return offers
