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
from .text import SIZE_TOKEN_RE, Size, fold, parse_size, rule_text, size_codes, tokens


class Matcher:
    def __init__(self, cfg: dict):
        self.synonyms = {fold(k): fold(v) for k, v in (cfg.get("synonyms") or {}).items()}
        self.stop = {fold(w) for w in cfg.get("stopwords") or []}
        self.conflicts = {fold(w) for w in cfg.get("conflicts") or []}
        self.min_sim = float(cfg.get("min_similarity", 0.34))
        self.filler = {self.synonyms.get(fold(w), fold(w)) for w in cfg.get("filler") or []}
        self.generic_first = {fold(w) for w in cfg.get("not_brands") or []}
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
        t = size_codes(t)
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
        w = self.words(o.name, b)
        if re.search(r"\d\s*\+\s*\d|\bfree\b|bedava|hediye|\bal\s*\d\s*ode", fold(o.name)):
            w.add("multibuy")   # "1+1", "3 al 2 ode", "+1 free" deals are not the single product
        return Key(brand=b, size=parse_size(o.name), words=w)

    def score(self, a: "Key", b: "Key") -> float:
        if not a.brand or a.brand != b.brand or not a.size or not a.size.same_as(b.size, tol=0.01):
            return 0.0
        diff = a.words ^ b.words
        if diff & self.conflicts or "multibuy" in diff or any(re.fullmatch(r"sz\d+", w) for w in diff):
            return 0.0
        ca, cb = a.words - self.filler, b.words - self.filler
        if not ca or not cb:
            return 0.6   # e.g. "Twix 50g Twin" vs "TWIX CIKOLATA 50 G"
        a, b = Key(a.brand, a.size, ca), Key(b.brand, b.size, cb)
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

    # brands not in the list: a first word that starts product names on both sides
    first_s = {tokens(o.name)[0] for o in south if tokens(o.name)}
    first_n = {tokens(o.name)[0] for o in north if tokens(o.name)}
    known = {a for a, _ in m.brand_aliases}
    for w in sorted((first_s & first_n) - known - m.generic_first - set(m.synonyms) - m.stop):
        if len(w) >= 3 and not w.isdigit():
            m.brand_aliases.append((w, w.title()))
    m.brand_aliases.sort(key=lambda x: -len(x[0]))

    # one anchor per e-kalathi product (all its chains together)
    anchors: dict[str, list[Offer]] = defaultdict(list)
    for o in south:
        anchors[o.product_id or o.name].append(o)
    akeys = {pid: m.key(offs[0]) for pid, offs in anchors.items()}

    # the same product listed by e-kalathi and by another South source -> one item
    ek = [pid for pid, offs in anchors.items() if offs[0].source == "ekalathi"]
    ek_by_brand = defaultdict(list)
    for pid in ek:
        if akeys[pid].brand and akeys[pid].size:
            ek_by_brand[akeys[pid].brand].append(pid)
    for pid in [p for p, offs in anchors.items() if offs[0].source != "ekalathi"]:
        k = akeys[pid]
        best = max(((m.score(k, akeys[e]), e) for e in ek_by_brand.get(k.brand, [])), default=(0, None))
        if best[0] >= 0.8:
            anchors[best[1]].extend(anchors.pop(pid))
            akeys.pop(pid)
    barcodes = {pid: {o.barcode for o in offs if o.barcode} for pid, offs in anchors.items()}
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
            if o.barcode and barcodes.get(pid):
                if o.barcode not in barcodes[pid]:
                    continue          # both sides have barcodes and they differ: not the same product
                s = 2.0               # same barcode: certain match
            else:
                s = m.score(k, akeys[pid])
            if s > best_s:
                best, best_s = pid, s
        if best:
            joined[best].append(o)

    groups = []
    # second pass: same product, different pack size -> compare per kg / litre / piece
    if cfg.get("pack_size_pass", True):
        min_sim = float(cfg.get("pack_size_min_similarity", 0.7))
        north_by_brand: dict[str, list] = defaultdict(list)
        for o in north:
            kn = m.key(o)
            if kn.brand and kn.size:
                north_by_brand[kn.brand].append((o, kn))
        for pid, s_offers in anchors.items():
            if pid in joined:
                continue
            ka = akeys[pid]
            if not ka.brand or not ka.size:
                continue
            best, best_s = [], 0.0
            for o, kn in north_by_brand.get(ka.brand, []):
                if kn.size.unit != ka.size.unit:
                    continue
                ratio = kn.size.total / ka.size.total
                if not 0.2 <= ratio <= 5 or (o.url, pid) in banned:
                    continue
                if ("can" in ka.words) != ("can" in kn.words):
                    continue   # cans vs bottles are priced differently per litre
                ca, cn = ka.words - m.filler, kn.words - m.filler
                if not (ca <= cn or cn <= ca) or len(ca ^ cn) > 1:
                    continue   # same descriptive words, at most one extra (e.g. "Danish")
                sc = m.score(Key(kn.brand, ka.size, kn.words), ka)   # compare names as if same size
                if sc >= min_sim:
                    if sc > best_s + 1e-9:
                        best, best_s = [o], sc
                    elif abs(sc - best_s) < 1e-9:
                        best.append(o)
            if best:
                per = {"g": "kg", "ml": "l", "pc": "1 pc"}[ka.size.unit]
                conv = lambda offs: [c for c in (_as_per_unit(x, per) for x in offs) if c]  # noqa: E731
                n_c, s_c = conv(best), conv(s_offers)
                if n_c and s_c:
                    label = {"kg": "per kg", "l": "per litre", "1 pc": "per item"}[per]
                    groups.append(Group(
                        id=f"ps-{pid}", name=_base_name(s_offers[0].name), unit=f"price {label} · pack sizes differ",
                        category=s_offers[0].category, north=n_c, south=s_c,
                        image=s_offers[0].image, kind="generic",
                        note=f"Same brand and product sold in different pack sizes, so compared {label}. "
                             "Shelf pack shown under each store."))

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


def _base_name(name: str) -> str:
    """'Doritos Nacho Cheese 180g' -> 'Doritos Nacho Cheese' (pack size removed)."""
    t = re.sub(r"\s*\(?\d+(?:[.,]\d+)?\s*(?:kg|g|gr|ml|l|lt|cl|pcs|pieces)\b\)?(\s*[x×]\s*\d+)?", "", name, flags=re.I)
    t = re.sub(r"\b\d+\s*[x×]\s*\d+(?:[.,]\d+)?\s*(?:g|ml|l)?\b", "", t, flags=re.I)
    return re.sub(r"\s{2,}", " ", t).strip(" -,") or name


def _as_per_unit(o: Offer, per: str) -> Offer | None:
    pu = per_unit(o, per)
    if not pu:
        return None
    c = Offer(**{**o.to_dict(), "price": round(pu, 2)})
    c.extra = {**o.extra, "shelf_price": o.price, "shelf_name": o.name}
    return c


# ---------------------------------------------------------------- generic items

_COUNT_RE = re.compile(r"\b(\d{1,3})\s*(?:li|lu|adet|ad|pcs|pc|pieces|tem|temachia|eggs|avga|rolls?|rulo|r|yaprak|wipes)\b"
                       r"|\bx\s*(\d{1,3})\b|\b(\d{1,3})\s*x\b")


def _pieces(name: str) -> float | None:
    t = fold(name)
    mult = 1
    m3 = re.search(r"\b(\d)\s*[x*]\s*(\d{1,3})\b", t)          # 3 x 72 wipes, 3*52 li
    if m3:
        return int(m3.group(1)) * int(m3.group(2))
    m = _COUNT_RE.search(t)
    if m:
        n = int(next(g for g in m.groups() if g))
        return n * mult if 1 <= n <= 400 else None
    return None


def per_unit(o: Offer, per: str, min_pieces: int = 1) -> float | None:
    """Price for `per` of the product: "kg", "l", "100 g", "15 pc", "1 pc"."""
    pm = re.match(r"^\s*(\d+(?:\.\d+)?)?\s*(kg|g|l|ml|pc)\s*$", per)
    if not pm:
        return None
    qty, unit = float(pm.group(1) or 1), pm.group(2)
    size = parse_size(o.name)
    if unit in ("kg", "g"):
        grams = qty * (1000 if unit == "kg" else 1)
        if size and size.unit == "g" and size.total:
            return o.price / size.total * grams
        if size is None and re.search(r"\b(kg|kilo|kgr)\b", fold(o.name)):
            return o.price / 1000 * grams
        return None
    if unit in ("l", "ml"):
        ml = qty * (1000 if unit == "l" else 1)
        return o.price / size.total * ml if size and size.unit == "ml" and size.total else None
    n = size.total if size and size.unit == "pc" else _pieces(o.name)
    return o.price / n * qty if n and n >= min_pieces else None


def _rule_ok(o: Offer, rule: dict) -> bool:
    t = rule_text(o.name)
    has = lambda w: (" " + fold(w).strip() + (" " if w.endswith(" ") else "")) in t  # noqa: E731
    if rule.get("cat") and not any(fold(c) in fold(o.category) for c in rule["cat"]):
        return False
    if rule.get("any") and not any(has(w) for w in rule["any"]):
        return False
    if any(not any(has(w) for w in group) for group in rule.get("all", [])):
        return False
    return not any(has(w) for w in rule.get("not", []))


def drop_outliers(offers: list[Offer], factor: float = 0.35) -> list[Offer]:
    """Remove per-unit prices far below the rest (almost always a misread size or price)."""
    if len(offers) < 3:
        return offers
    ps = sorted(o.price for o in offers)
    median = ps[len(ps) // 2]
    return [o for o in offers if o.price >= factor * median]


def generic(north: list[Offer], south: list[Offer], items: list[dict]) -> list[Group]:
    out = []
    for it in items:
        per = it.get("per", "kg")
        sides = {}
        for side, offers in (("north", north), ("south", south)):
            picked = []
            for o in offers:
                if not _rule_ok(o, it.get(side) or {}):
                    continue
                pu = per_unit(o, per, int(it.get("min_pieces", 1)))
                if pu and pu > 0:
                    c = Offer(**{**o.to_dict(), "price": round(pu, 2)})
                    c.extra = {**o.extra, "shelf_price": o.price, "shelf_name": o.name}
                    picked.append(c)
            sides[side] = drop_outliers(picked, 0.25) if side == "north" else picked   # misread labels come from North pages
        if sides["north"] and sides["south"]:
            label = per if re.match(r"^\d", per) else f"1 {per}"
            out.append(Group(id=f"gen-{it['id']}", name=it["name"], unit=f"price per {label.replace(' pc', '')}",
                             category=it.get("category", ""), north=sides["north"], south=sides["south"],
                             kind="generic",
                             note=f"Cheapest of any brand, worked out per {label.replace(' pc', ' item' if label.startswith('1 ') else ' items')}. "
                                  "Shelf product shown under each store."))
    return out
