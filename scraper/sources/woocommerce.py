"""Shops built on WordPress + WooCommerce (e.g. Sarper Market).

WooCommerce has a public "Store API" that the shop's own pages use:
  /wp-json/wc/store/v1/products?per_page=100&page=N
It returns clean JSON, so no HTML guessing is needed. If a shop has switched
it off, we fall back to reading its category pages like any other shop.
"""
from __future__ import annotations

import html
import logging

from ..models import Offer
from . import shop_html

log = logging.getLogger(__name__)


def scrape(http, cfg: dict) -> list[Offer]:
    base = cfg["base_url"].rstrip("/")
    out: dict[str, Offer] = {}
    try:
        for page in range(1, int(cfg.get("max_pages", 200)) + 1):
            data = http.json(f"{base}/wp-json/wc/store/v1/products?per_page=100&page={page}")
            if not data:
                break
            for p in data:
                o = _offer(cfg, p)
                if o:
                    out[o.url] = o
            if len(data) < 100:
                break
        log.info("%s: %d products via Store API", cfg["id"], len(out))
        if out:
            return list(out.values())
    except Exception as e:  # noqa: BLE001
        log.warning("%s: Store API unavailable (%s); reading pages instead", cfg["id"], e)
    return shop_html.scrape(http, cfg)


def _offer(cfg: dict, p: dict) -> Offer | None:
    if p.get("is_in_stock") is False and not cfg.get("include_out_of_stock"):
        return None
    pr = p.get("prices") or {}
    raw = pr.get("price") or pr.get("sale_price") or pr.get("regular_price")
    if not raw:
        return None
    minor = int(pr.get("currency_minor_unit", 2))
    price = int(raw) / (10 ** minor)
    if price <= 0:
        return None
    name, barcode = shop_html.split_barcode(html.unescape(p.get("name", "")))
    imgs = p.get("images") or []
    cats = p.get("categories") or []
    return Offer(
        source=cfg["id"], side=cfg["side"], store=cfg["store"], name=name, price=price,
        currency=pr.get("currency_code") or cfg.get("currency", "TRY"), url=p.get("permalink", ""),
        image=(imgs[0].get("src") if imgs else "") or "", category=cats[0].get("name", "") if cats else "",
        barcode=barcode or (p.get("sku") if str(p.get("sku", "")).isdigit() and len(str(p.get("sku"))) == 13 else ""),
        town=cfg.get("town", ""), maps=cfg.get("maps", ""),
    )
