"""The "Wanted" list: products of brands sold on both sides that have a price on
only one side, so shoppers know which shelves to photograph."""
from __future__ import annotations

import re

from .text import fold, parse_size


def _brand_re(brands):
    out = []
    for b in brands:
        k = re.sub(r"[^a-z0-9& ]", "", fold(b).replace("-", " ")).strip()
        out.append((b, re.compile(r"(?<![a-z])" + re.escape(k).replace(r"\ ", r"[\s\-']*") + r"(?![a-z])")))
    return out


def build(north, south, groups, cfg: dict, rate: float) -> dict:
    used = {(o.store, fold(o.name)) for g in groups for o in list(g.north) + list(g.south)}
    used |= {(o.store, fold(o.extra.get("shelf_name", ""))) for g in groups for o in list(g.north) + list(g.south)}
    brands = _brand_re(cfg.get("brands") or [])
    order = {b: i for i, (b, _) in enumerate(brands)}
    cap = int(cfg.get("per_side", 400))
    out = {}
    for have, offers, need in (("N", north, "S"), ("S", south, "N")):
        best = {}
        for o in offers:
            if (o.store, fold(o.name)) in used or o.price <= 0:
                continue
            size = parse_size(o.name)
            if not size:
                continue
            n = re.sub(r"[^a-z0-9&' ]", " ", fold(o.name))
            brand = next((b for b, rx in brands if rx.search(n)), None)
            if not brand:
                continue
            key = (brand, re.sub(r"\s+", " ", n).strip())
            eur = o.price if o.currency == "EUR" else o.price / rate
            if key not in best or eur < best[key]["eur"]:
                best[key] = {"brand": brand, "name": o.name, "size": size.label(), "store": o.store,
                             "eur": round(eur, 2), "try": round(eur * rate, 2), "barcode": o.barcode or ""}
        rows = sorted(best.values(), key=lambda r: (order[r["brand"]], r["name"].lower()))
        per_brand, keep = {}, []
        for r in rows:                       # a spread of brands, not 400 Nivea lotions
            per_brand[r["brand"]] = per_brand.get(r["brand"], 0) + 1
            if per_brand[r["brand"]] <= int(cfg.get("per_brand", 30)):
                keep.append(r)
        out[need] = keep[:cap]
    return {"need_south": out["S"], "need_north": out["N"],
            "counts": {"need_south": len(out["S"]), "need_north": len(out["N"])}}
