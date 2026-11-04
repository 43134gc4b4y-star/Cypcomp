"""Shops built on Shopify (e.g. Nesdersan).

Every Shopify shop publishes its catalogue at /products.json (250 per page),
so no HTML guessing is needed.
"""
from __future__ import annotations

import logging

from ..models import Offer
from . import shop_html

log = logging.getLogger(__name__)


def scrape(http, cfg: dict) -> list[Offer]:
    base = cfg["base_url"].rstrip("/")
    out: dict[str, Offer] = {}
    for page in range(1, int(cfg.get("max_pages", 400)) + 1):
        data = http.json(f"{base}/products.json?limit=250&page={page}")
        products = data.get("products") or []
        if not products:
            break
        for p in products:
            o = _offer(cfg, base, p)
            if o:
                out[o.url] = o
        if len(products) < 250:
            break
    log.info("%s: %d products via products.json", cfg["id"], len(out))
    return list(out.values())


def _offer(cfg: dict, base: str, p: dict) -> Offer | None:
    variants = [v for v in p.get("variants") or [] if v.get("available", True)]
    if not variants:
        return None
    v = min(variants, key=lambda x: float(x.get("price") or 1e9))
    price = float(v.get("price") or 0)
    if price <= 0:
        return None
    title = p.get("title", "")
    if len(p.get("variants") or []) > 1 and v.get("title") not in (None, "", "Default Title"):
        title = f"{title} {v['title']}"
    name, barcode = shop_html.split_barcode(title)
    imgs = p.get("images") or []
    return Offer(
        source=cfg["id"], side=cfg["side"], store=cfg["store"], name=name, price=price,
        currency=cfg.get("currency", "TRY"), url=f"{base}/products/{p.get('handle', '')}",
        image=imgs[0].get("src", "") if imgs else "", category=p.get("product_type", "") or "",
        barcode=barcode or (str(v.get("barcode") or "") if str(v.get("barcode") or "").isdigit() else ""),
        town=cfg.get("town", ""), maps=cfg.get("maps", ""),
    )
