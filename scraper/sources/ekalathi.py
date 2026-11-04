"""South Cyprus: the government's e-kalathi price observatory.

e-kalathi has a public JSON API (the one its own website uses):
  /fetch-companies                         -> list of supermarket chains
  /fetch-product-list?page=&size=          -> every product, with the lowest price
  /fetch-product-list?...&companyIds=ID    -> the same list, priced at one chain
So: one pass for the catalogue, then one pass per chain for its prices.
"""
from __future__ import annotations

import logging
from urllib.parse import quote_plus, urljoin

from ..models import Offer
from ..net import Http

log = logging.getLogger(__name__)

SITE = "https://www.e-kalathi.gov.cy"
API = SITE + "/ekalathi-website-server/api"

# Used only if /fetch-companies cannot be read. IDs as published by the API.
FALLBACK_CHAINS = [
    (453, "Lidl"), (463, "Metro"), (471, "AlphaMega"), (479, "Papantoniou"), (480, "Sklavenitis"),
    (541, "Kyriacos"), (452, "Alpha Sigma"), (477, "Lysiotis"), (466, "Plus Discount"),
    (469, "Athinaitis"), (475, "Kokkinos"), (465, "Philippos"), (497, "MAS"), (467, "Poplife"),
    (468, "Super Discount Store"),
]


def _pick(d: dict, *keys, default=None):
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return default


def companies(http: Http) -> list[tuple[int, str]]:
    try:
        data = http.json(f"{API}/fetch-companies")
    except Exception as e:  # noqa: BLE001
        log.warning("e-kalathi: fetch-companies failed (%s); using built-in chain list", e)
        return FALLBACK_CHAINS
    if isinstance(data, dict):
        data = _pick(data, "content", "companies", "data", default=[])
    out = []
    for c in data or []:
        cid = _pick(c, "id", "companyId", "companyMasterId")
        name = _pick(c, "nameEnglish", "companyNameEnglish", "name", "companyName", "title")
        if cid is not None and name:
            out.append((int(cid), str(name).strip()))
    return out or FALLBACK_CHAINS


def product_pages(http: Http, page_size: int, company_id: int | None = None, max_pages: int = 100):
    for page in range(max_pages):
        url = f"{API}/fetch-product-list?page={page}&size={page_size}&productName="
        if company_id is not None:
            url += f"&companyIds={company_id}"
        data = http.json(url)
        content = data.get("content") or []
        yield from content
        if data.get("last") or len(content) < page_size:
            break


def scrape(http: Http, cfg: dict) -> list[Offer]:
    page_size = int(cfg.get("page_size", 100))
    only = {s.lower() for s in cfg.get("only_chains", [])}
    skip = {s.lower() for s in cfg.get("skip_chains", [])}

    # 1. catalogue: names, categories, photos
    catalogue = {}
    for p in product_pages(http, page_size):
        pid = p.get("productMasterId")
        if pid is not None:
            catalogue[pid] = p
    log.info("e-kalathi: %d products in catalogue", len(catalogue))

    # 2. prices at each chain
    chains = [(i, n) for i, n in companies(http)
              if (not only or n.lower() in only) and n.lower() not in skip]
    log.info("e-kalathi: %d chains", len(chains))
    offers: list[Offer] = []
    for cid, cname in chains:
        n = 0
        try:
            for p in product_pages(http, page_size, cid):
                price = p.get("startPrice")
                pid = p.get("productMasterId")
                if not price or pid is None:
                    continue
                base = catalogue.get(pid, p)
                thumb = _pick(base, "productThumbnailUrl", "thumbnailUrl", "imageUrl", default="")
                offers.append(Offer(
                    source="ekalathi", side="S", store=cname,
                    name=_pick(base, "name", "productNameEnglish", default=""),
                    price=float(price), currency="EUR",
                    url=f"{SITE}/product-information/{pid}",
                    image=urljoin(SITE + "/", thumb) if thumb else "",
                    category=_pick(base, "productCategoryNameEnglish", "categoryName", default=""),
                    product_id=str(pid), town="Cyprus",
                    maps="https://www.google.com/maps/search/?api=1&query=" + quote_plus(f"{cname} supermarket Cyprus"),
                ))
                n += 1
        except Exception as e:  # noqa: BLE001  one chain failing shouldn't stop the rest
            log.warning("e-kalathi: chain %s (%s) failed: %s", cname, cid, e)
        log.info("  %-24s %4d prices", cname, n)
    return offers
