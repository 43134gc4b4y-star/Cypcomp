"""Pair North products with South products.

Rule: same brand + same pack size + similar remaining words, and no
"conflict" word (zero, light, lactose-free...) on only one side.
Each South product (an e-kalathi product, priced at many chains) is an
anchor; every North product joins the anchor it matches best.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from .models import Offer
from .text import SIZE_TOKEN_RE, Size, fold, parse_size, tokens


class Matcher:
    def __init__(self, cfg: dict):
        self.synonyms = {fold(k): fold(v) for k, v in (cfg.get("synonyms") or {}).items()}
        self.stop = {fold(w) for w in cfg.get("stopwords") or []}
        self.conflicts = {fold(w) for w in cfg.get("conflicts") or []}
        self.min_sim = float(cfg.get("min_similarity", 0.34))
        # brand aliases, longest first so "coca cola zero" doesn't hit "cola"
        self.brand_aliases = sorted(
            ((" ".join(tokens(a)), name) for name, al in (cfg.get("brands") or {}).items()
             for a in [name, *al]),
            key=lambda x: -len(x[0]),
        )

    def brand(self, name: str) -> str | None:
        t = " " + " ".join(tokens(name)) + " "
        for alias, canon in self.brand_aliases:
            if alias and f" {alias} " in t:
                return canon
        return None

    def words(self, name: str, brand: str | None) -> set[str]:
        t = " ".join(tokens(name))
        # nappy / clothing sizes: "S3", "size 3", "3 numara", "no 3", "beden 3" -> "sz3"
        t = re.sub(r"\b(?:s|size|no|numara|beden|n)\s?(\d{1,2})\b|\b(\d{1,2})\s?(?:numara|no|beden)\b",
                   lambda mm: f" sz{mm.group(1) or mm.group(2)} ", t)
        # drop pack sizes: "8x330 ml", "330ml x8", "1 lt", "12 li", "x8"
        t = re.sub(r"\b\d+\s*x\s*\d+\b|\bx\s*\d+\b|\b\d+\s*x\b", " ", t)
        t = re.sub(r"\b\d+\s*(?:kgr|kg|grams|gram|grm|gr|gm|g|ml|cl|ltr|lt|l|li|lu|adet|pcs|tem|temachia)?\b", " ", t)
        t = re.sub(r"\b(?:kgr|kg|grams|gram|grm|gr|gm|g|ml|cl|ltr|lt|l)\b", " ", t)
        if brand:
            for alias, canon in self.brand_aliases:
                if canon == brand:
                    t = re.sub(rf"\b{re.escape(alias)}\b", " ", t)
        out = set()
        for w in t.split():
            if SIZE_TOKEN_RE.match(w) or w in self.stop or len(w) < 2 and not w.isdigit():
                continue
            out.add(self.synonyms.get(w, w))
        return out

    def key(self, o: Offer) -> "Key":
        b = self.brand(o.name)
        return Key(brand=b, size=parse_size(o.name), words=self.words(o.name, b))

    def score(self, a: "Key", b: "Key") -> float:
        if not a.brand or a.brand != b.brand or not a.size or not a.size.same_as(b.size):
            return 0.0
        diff = a.words ^ b.words
        if diff & self.conflicts or any(re.fullmatch(r"sz\d+", w) for w in diff):
            return 0.0
        if not a.words and not b.words:
            return 1.0
        inter = len(a.words & b.words)
        union = len(a.words | b.words) or 1
        sim = inter / union
        # a short name fully contained in a longer one is a good sign
        small = min(len(a.words), len(b.words))
        if small and inter == small:
            sim = max(sim, 0.5 + 0.1 * small)
        return min(sim, 1.0) if sim >= self.min_sim else 0.0


@dataclass
class Key:
    brand: str | None
    size: Size | None
    words: set[str] = field(default_factory=set)


@dataclass
class Group:
    id: str
    name: str
    unit: str
    category: str
    north: list[Offer]
    south: list[Offer]
    image: str = ""
    kind: str = "exact"   # exact | generic | manual
    note: str = ""


def match(north: list[Offer], south: list[Offer], cfg: dict, overrides: dict | None = None) -> list[Group]:
    m = Matcher(cfg)
    overrides = overrides or {}
    forced = {str(x["north"]): str(x["south"]) for x in overrides.get("same", [])}
    banned = {(str(x["north"]), str(x["south"])) for x in overrides.get("different", [])}

    # one anchor per e-kalathi product (all its chains together)
    anchors: dict[str, list[Offer]] = defaultdict(list)
    for o in south:
        anchors[o.product_id or o.name].append(o)
    akeys = {pid: m.key(offs[0]) for pid, offs in anchors.items()}
    by_brand: dict[str, list[str]] = defaultdict(list)
    for pid, k in akeys.items():
        if k.brand and k.size:
            by_brand[k.brand].append(pid)

    joined: dict[str, list[Offer]] = defaultdict(list)
    for o in north:
        if o.url in forced and forced[o.url] in anchors:
            joined[forced[o.url]].append(o)
            continue
        k = m.key(o)
        best, best_s = None, 0.0
        for pid in by_brand.get(k.brand, []):
            if (o.url, pid) in banned:
                continue
            s = m.score(k, akeys[pid])
            if s > best_s:
                best, best_s = pid, s
        if best:
            joined[best].append(o)

    groups = []
    for pid, north_offers in joined.items():
        s_offers = anchors[pid]
        first = s_offers[0]
        k = akeys[pid]
        img = first.image or next((x.image for x in north_offers if x.image), "")
        groups.append(Group(
            id=f"ek-{pid}", name=first.name, unit=k.size.label() if k.size else "",
            category=first.category or north_offers[0].category, north=north_offers, south=s_offers,
            image=img,
        ))
    return groups


# ---------------------------------------------------------------- generic items

def _per_unit(o: Offer, per: str) -> float | None:
    """Price for the item's `per` amount (kg / litre / N pieces)."""
    size = parse_size(o.name)
    pm = re.match(r"^\s*(\d+(?:\.\d+)?)?\s*(kg|l|litre|pc)\s*$", per)
    if not pm:
        return None
    qty, unit = float(pm.group(1) or 1), pm.group(2)
    if unit == "kg":
        if size is None:
            return o.price if re.search(r"\b(kg|kilo|kgr)\b", fold(o.name)) else None
        return o.price / (size.total / 1000) * qty if size.unit == "g" and size.total else None
    if unit in ("l", "litre"):
        return o.price / (size.total / 1000) * qty if size and size.unit == "ml" and size.total else None
    if unit == "pc":
        n = re.search(r"\b(\d+)\s*'?\s*(?:li|lu|adet|pcs|pieces|tem|temachia|eggs|avga)?\b", fold(o.name))
        if size and size.unit == "pc":
            return o.price / size.total * qty
        if n and 2 <= int(n.group(1)) <= 60:
            return o.price / int(n.group(1)) * qty
    return None


def generic(north: list[Offer], south: list[Offer], items: list[dict]) -> list[Group]:
    out = []
    for it in items:
        sides = {}
        for side, offers in (("north", north), ("south", south)):
            rule = it.get(side) or {}
            anyw = [fold(w) for w in rule.get("any", [])]
            notw = [fold(w) for w in rule.get("not", [])]
            picked = []
            for o in offers:
                t = " " + " ".join(tokens(o.name)) + " "
                if any(f" {w}" in t for w in anyw) and not any(f" {w}" in t for w in notw):
                    pu = _per_unit(o, it.get("per", "kg"))
                    if pu:
                        c = Offer(**{**o.to_dict(), "price": round(pu, 2)})
                        c.extra = {**o.extra, "shelf_price": o.price, "shelf_name": o.name}
                        picked.append(c)
            sides[side] = picked
        if sides["north"] and sides["south"]:
            out.append(Group(id=f"gen-{it['id']}", name=it["name"], unit=f"per {it.get('per', 'kg')}",
                             category=it.get("category", ""), north=sides["north"], south=sides["south"],
                             kind="generic",
                             note="Cheapest of any brand/variety, worked out per " + it.get("per", "kg")))
    return out
