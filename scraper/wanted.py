"""The "Wanted" list: products of brands sold on both sides that have a price on only one
side, so shoppers know which shelves to photograph.

- Every brand found on both sides counts (not just a fixed list); the brands in
  config/wanted.yaml are the best known ones and rank a little higher.
- Products are ranked by how likely a shopper is to find them: sold in several shops on
  its side, from a brand the other side stocks widely, and from the well-known brands.
- The real totals are reported; only the `per_side` most wanted are listed on the site.
- data/wanted_history.json remembers when each product joined the list, so the site can
  mark new ones, and which products left it because a price for the other side was found.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path

from .match import Matcher
from .text import fold, parse_size

FOUND_DAYS = 30          # how long a found product stays in the "recently found" list


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9&' ]", " ", fold(name))).strip()


def build(north, south, groups, cfg: dict, rate: float, history_path: Path | None = None, today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    m = Matcher(cfg.get("_matching") or {})
    known = {fold(b) for b in cfg.get("brands") or []}
    used = {(o.store, fold(o.name)) for g in groups for o in list(g.north) + list(g.south)}
    used |= {(o.store, fold(o.extra.get("shelf_name", ""))) for g in groups for o in list(g.north) + list(g.south)}
    group_of = {_norm(o.extra.get("shelf_name") or o.name): g.id for g in groups for o in list(g.north) + list(g.south)}

    # brands on each side, and how many products each side has of them
    count = {"N": {}, "S": {}}
    brand_of = {}
    for side, offers in (("N", north), ("S", south)):
        for o in offers:
            b = m.brand(o.name)
            brand_of[id(o)] = b
            if b:
                count[side][b] = count[side].get(b, 0) + 1
    shared = set(count["N"]) & set(count["S"])

    history, first_run = {}, not (history_path and history_path.exists())
    if not first_run:
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except ValueError:
            history = {}
    first_seen = history.get("first_seen", {})
    found = [f for f in history.get("found", []) if (today - date.fromisoformat(f["date"])).days <= FOUND_DAYS]

    out, totals, keys_now = {}, {}, set()
    for have, offers, need in (("N", north, "S"), ("S", south, "N")):
        best, shops = {}, {}
        for o in offers:
            b = brand_of.get(id(o))
            if not b or b not in shared or o.price <= 0 or (o.store, fold(o.name)) in used:
                continue
            size = parse_size(o.name)
            if not size:
                continue
            key = (b, _norm(o.name))
            shops.setdefault(key, set()).add(o.store.split("|")[0].strip())
            eur = o.price if o.currency == "EUR" else o.price / rate
            if key not in best or eur < best[key]["eur"]:
                best[key] = {"brand": b, "name": o.name, "size": size.label(), "store": o.store,
                             "eur": round(eur, 2), "try": round(eur * rate, 2), "barcode": o.barcode or ""}
        rows = []
        for key, r in best.items():
            n = len(shops[key])
            # sold in several shops = a popular product; a brand the other side stocks a lot of = likely on its shelves
            r["shops"] = n
            r["score"] = round(3 * min(n, 4) + math.log1p(count[need].get(r["brand"], 0)) + (2 if fold(r["brand"]) in known else 0), 2)
            hk = f"{need}:{r['brand']}:{key[1]}"
            keys_now.add(hk)
            if hk not in first_seen:          # the very first list isn't "new"; later additions are
                first_seen[hk] = {"d": "2000-01-01" if first_run else today.isoformat(), "n": r["name"]}
            r["since"] = first_seen[hk]["d"]
            rows.append(r)
        totals[need] = len(rows)
        rows.sort(key=lambda r: (-r["score"], r["brand"].lower(), r["name"].lower()))
        per_brand, keep = {}, []
        for r in rows:                       # a spread of brands, not 400 Nivea lotions
            per_brand[r["brand"]] = per_brand.get(r["brand"], 0) + 1
            if per_brand[r["brand"]] <= int(cfg.get("per_brand", 30)):
                keep.append(r)
        out[need] = keep[: int(cfg.get("per_side", 400))]

    # products that left the list because they are now compared
    for hk in list(first_seen):
        if hk in keys_now:
            continue
        need, brand, norm = hk.split(":", 2)
        gid = group_of.get(norm)
        if gid and not any(f["key"] == hk for f in found):
            found.append({"key": hk, "need": need, "brand": brand, "name": first_seen[hk]["n"], "id": gid, "date": today.isoformat()})
        del first_seen[hk]
    found.sort(key=lambda f: f["date"], reverse=True)

    if history_path:
        history_path.write_text(json.dumps({"first_seen": first_seen, "found": found}, ensure_ascii=False,
                                           separators=(",", ":"), sort_keys=True), encoding="utf-8")
    return {"updated": today.isoformat(),
            "need_south": out["S"], "need_north": out["N"],
            "counts": {"need_south": totals["S"], "need_north": totals["N"]},
            "found": [{k: f[k] for k in ("need", "brand", "name", "id", "date")} for f in found[:40]]}
