"""The daily job: read every shop, pair products, write the website's data.

    python -m scraper.run                 # everything
    python -m scraper.run --only starling # one shop (others reuse saved data)
    python -m scraper.run --offline       # rebuild the website data from saved shop data

Each shop's products are saved in data/raw/<shop>.json. If a shop fails, or
suddenly returns far fewer products (usually a site redesign), yesterday's
file is kept so the website never goes empty.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import contrib, fx, wanted
from .match import Group, generic, match
from .models import Offer
from .net import Http
from .sources import ekalathi, fetchcy, shop_html, shopify, woocommerce, observatory

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SITE_DATA = ROOT / "site" / "data"
SCRAPERS = {"ekalathi": ekalathi.scrape, "shopify": shopify.scrape, "observatory": observatory.scrape,
    "fetchcy": fetchcy.scrape, "shop_html": shop_html.scrape, "woocommerce": woocommerce.scrape}

log = logging.getLogger("compare-cyprus")


def load_yaml(name: str):
    with open(ROOT / "config" / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def read_raw(sid: str) -> dict | None:
    p = RAW / f"{sid}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def scrape_shop(http: Http, sid: str, cfg: dict) -> dict:
    """Run one shop's scraper; returns a status line for the report."""
    prev = read_raw(sid)
    prev_n = len(prev["offers"]) if prev else 0
    started = datetime.now(timezone.utc)
    try:
        offers = SCRAPERS[cfg["type"]](http, {**cfg, "id": sid})
        err = None
    except Exception as e:  # noqa: BLE001
        log.exception("%s failed", sid)
        offers, err = [], f"{type(e).__name__}: {e}"
    n = len(offers)
    secs = round((datetime.now(timezone.utc) - started).total_seconds())
    if n and (not prev_n or n >= 0.4 * prev_n):
        RAW.mkdir(parents=True, exist_ok=True)
        (RAW / f"{sid}.json").write_text(json.dumps({
            "source": sid, "fetched_at": started.isoformat(timespec="seconds"),
            "offers": [o.to_dict() for o in offers]}, ensure_ascii=False, indent=0), encoding="utf-8")
        return {"shop": sid, "status": "ok", "products": n, "seconds": secs}
    reason = err or (f"only {n} products (was {prev_n}) - kept previous data" if n else "no products found")
    return {"shop": sid, "status": "kept old data" if prev_n else "failed", "products": n,
            "previous": prev_n, "error": reason, "seconds": secs}


def manual_groups(path: Path) -> list[Group]:
    if not path.exists():
        return []
    rows = [r for r in csv.DictReader(path.open(encoding="utf-8")) if (r.get("price") or "").strip()]
    by_item: dict[str, dict] = {}
    for r in rows:
        g = by_item.setdefault(r["item"], {"north": [], "south": [], "category": r.get("category", ""), "unit": r.get("unit", "")})
        q = " ".join(x for x in (r.get("store"), r.get("address"), r.get("town")) if x)
        o = Offer(source="manual", side=r["side"].strip().upper(), store=r.get("store", ""), name=r["item"],
                  price=float(r["price"]), currency=r.get("currency", "EUR").strip().upper(),
                  town=r.get("town", ""),
                  maps="https://www.google.com/maps/search/?api=1&query=" + q.replace(" ", "+") if q else "",
                  extra={"date": r.get("date", ""), "source": r.get("source", "")})
        g["north" if o.side == "N" else "south"].append(o)
    return [Group(id="man-" + "".join(c if c.isalnum() else "-" for c in item.lower()), name=item,
                  unit=g["unit"], category=g["category"], north=g["north"], south=g["south"],
                  kind="manual", note="Entered by hand")
            for item, g in by_item.items() if g["north"] and g["south"]]


def offer_json(o: Offer, rate: float) -> dict:
    eur = o.price if o.currency == "EUR" else o.price / rate
    tl = o.price if o.currency == "TRY" else o.price * rate
    d = {"store": o.store, "town": o.town, "eur": round(eur, 2), "try": round(tl, 2),
         "currency": o.currency, "url": o.url, "maps": o.maps, "name": o.name}
    if o.barcode:
        d["barcode"] = o.barcode
    if o.extra.get("shelf_price"):
        sp = o.extra["shelf_price"]
        d["shelf"] = {"name": o.extra["shelf_name"], "price": sp,
                      "eur": round(sp if o.currency == "EUR" else sp / rate, 2),
                      "try": round(sp if o.currency == "TRY" else sp * rate, 2)}
    if o.extra.get("date"):
        d["date"] = o.extra["date"]
    return d


def _cheapest_per_store(offers: list[dict]) -> list[dict]:
    seen, out = set(), []
    for o in offers:
        if o["store"] not in seen:
            seen.add(o["store"])
            out.append(o)
    return out


# e-kalathi categories -> the site's categories
CATEGORY_MAP = [
    (("MILK", "YOGURT", "EGGS", "BUTTER", "MARGA"), "Milk & dairy"), (("CHEESE", "HALLOUMI"), "Cheese"),
    (("COFFEE",), "Coffee"), (("CEREAL", "MUSLI"), "Breakfast"),
    (("CHOCOLATE", "BUSCUIT", "BISCUIT", "CHIPS", "ICE CREAM"), "Snacks"),
    (("SOFT DRINK", "WATER", "JUICE"), "Drinks"), (("FROZEN",), "Frozen"), (("COLD CUTS",), "Cold cuts"),
    (("BABY", "WET WIPES"), "Baby"), (("ANIMAL",), "Pets"), (("NUTS", "DRY FRUIT"), "Nuts & dried fruit"),
    (("LAUNDRY", "FABRIC", "CLEANING"), "Cleaning"), (("TOILET", "NAPKIN"), "Paper & tissues"),
    (("SHAMPOO", "SOAP", "SANITARY", "ADULT"), "Personal care"),
    (("PASTA", "RICE", "FLOUR", "OIL", "SAUCE", "CANNED"), "Pantry"),
]


SITE_CATEGORIES = {name for _, name in CATEGORY_MAP} | {"Coffee", "Snacks", "Personal care", "Other"}


def tidy_category(c: str) -> str:
    if not c:
        return "Other"
    if c in SITE_CATEGORIES:
        return c
    up = c.upper()
    for keys, name in CATEGORY_MAP + [(("DAIRY", "BEVERAGE", "DRINK"), "Drinks"), (("SWEET", "CRISP", "SNACK"), "Snacks"),
                                      (("HOUSEHOLD", "DETERGENT"), "Cleaning"), (("BEAUTY", "HEALTH", "HYGIENE"), "Personal care"),
                                      (("PET",), "Pets"), (("MEAT", "DELI"), "Cold cuts"), (("GROCER", "PANTRY", "FOOD"), "Pantry")]:
        if any(k in up for k in keys):
            return name
    return c.title() if c.isupper() else c


PINNED: list[str] = []


def _with_pinned(offers: list[dict], pinned: list[str], top: int = 5) -> list[dict]:
    """First `top` cheapest stores, plus any pinned chains (e.g. Lidl, AlphaMega) further down."""
    out = offers[:top]
    for o in offers[top:]:
        if o["store"] in pinned:
            out.append(o)
    return out


def _shelf(o: dict) -> float:
    return (o.get("shelf") or o)["eur"]


def _photo(g: Group, win: str) -> str:
    """A photo for an any-brand item: the cheapest product on the cheaper side, else the nearest one that has a photo."""
    first, second = (g.north, g.south) if win == "N" else (g.south, g.north)
    for offers in (first, second):
        for o in sorted(offers, key=lambda o: o.price):
            if o.image:
                return o.image
    return ""


def build_items(groups: list[Group], rate: float) -> list[dict]:
    items = []
    for g in groups:
        n = sorted((offer_json(o, rate) for o in g.north), key=lambda x: x["eur"])
        s = sorted((offer_json(o, rate) for o in g.south), key=lambda x: x["eur"])
        # one line per store: its cheapest price (lists are already cheapest-first)
        n = _cheapest_per_store(n)
        s = _cheapest_per_store(s)
        bn, bs = n[0], s[0]
        # same product can't honestly cost 4x more on one side: almost always a misread
        # pack (a box of 24 sold as "34 g"), so leave it out rather than show a fake saving
        lo, hi = sorted((_shelf(bn), _shelf(bs)))
        if lo > 0 and hi / lo > (6 if g.unit == "per kg" else 4):
            continue
        diff = bs["eur"] - bn["eur"]
        win = "N" if diff > 0.005 else "S" if diff < -0.005 else "="
        pct = abs(diff) / max(bn["eur"], bs["eur"]) * 100 if win != "=" else 0
        items.append({
            "id": g.id, "name": g.name, "unit": g.unit, "category": tidy_category(g.category),
            "kind": g.kind, "note": g.note, "image": g.image or _photo(g, win), "cheaper": win, "saving_pct": round(pct, 1),
            "north": n[:5], "south": _with_pinned(s, PINNED), "north_count": len(n), "south_count": len(s),
        })
    items.sort(key=lambda x: -x["saving_pct"])
    return items


def publish_progress(sid: str, offers: list) -> None:
    """Part-way through a long shop (Fetch): save what was found, rebuild the site data,
    and - on GitHub - publish it if the list of items or prices changed."""
    prev = read_raw(sid)
    if prev and len(offers) < 0.4 * len(prev["offers"]):
        return
    (RAW / f"{sid}.json").write_text(json.dumps({
        "source": sid, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "offers": [o.to_dict() for o in offers]}, ensure_ascii=False, indent=0), encoding="utf-8")
    page = SITE_DATA / "prices.json"
    old_text = page.read_text(encoding="utf-8") if page.exists() else ""
    before = json.loads(old_text)["items"] if old_text else None
    subprocess.run([sys.executable, "-m", "scraper.run", "--offline"], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    after = json.loads(page.read_text(encoding="utf-8"))
    if before and after["count"] < 0.9 * len(before):      # still catching up: don't show fewer items
        page.write_text(old_text, encoding="utf-8")
        log.info("  progress: only %d items so far (site has %d) - not published yet", after["count"], len(before))
        return
    if after["items"] == before:
        log.info("  progress: nothing new to publish")
        return
    log.info("  progress: %d items - publishing", after["count"])
    script = ROOT / ".github" / "publish.sh"
    if os.environ.get("PUBLISH_PROGRESS") and script.exists():
        subprocess.run(["bash", str(script), f"{after['count']} items"], cwd=ROOT, check=False)


def stamp_assets() -> None:
    """Add ?v=<hash> to the site's CSS/JS links so phones load the new files after a change."""
    import hashlib
    page = ROOT / "site" / "index.html"
    html = page.read_text(encoding="utf-8")
    new = html
    for f in ("style.css", "app.js", "contribute.js", "wanted.js", "install.js"):
        p = ROOT / "site" / f
        if p.exists():
            v = hashlib.sha1(p.read_bytes()).hexdigest()[:8]
            new = re.sub(re.escape(f) + r"(\?v=[0-9a-z]*)?(?=[\"'])", f"{f}?v={v}", new)
    if new != html:
        page.write_text(new, encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="only scrape these shop ids")
    ap.add_argument("--offline", action="store_true", help="don't scrape, rebuild from data/raw")
    ap.add_argument("--delay", type=float, default=float(os.environ.get("SCRAPE_DELAY", 1.0)))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    shops = load_yaml("shops.yaml")
    http = Http(delay=args.delay)
    report = []
    if not args.offline:
        for sid, cfg in shops.items():
            if not cfg.get("enabled", True) or (args.only and sid not in args.only):
                continue
            log.info("=== %s ===", sid)
            if cfg["type"] == "fetchcy":   # needs today's North products to pick candidates
                cfg = {**cfg, "_matching": load_yaml("matching.yaml"),
                       "_north": [Offer.from_dict(d) for s2, c2 in shops.items()
                                  if c2.get("side") == "N" and c2.get("enabled", True) and read_raw(s2)
                                  for d in read_raw(s2)["offers"]],
                       "_progress": lambda offers, sid=sid: publish_progress(sid, offers)}
            report.append(scrape_shop(http, sid, cfg))

    north, south, stamps = [], [], {}
    for sid, cfg in shops.items():
        raw = read_raw(sid)
        if not raw or not cfg.get("enabled", True):
            continue
        offers = [Offer.from_dict(d) for d in raw["offers"]]
        if cfg.get("seller_include") or cfg.get("seller_exclude"):
            inc = re.compile(cfg.get("seller_include", "."), re.I)
            exc = re.compile(cfg.get("seller_exclude", "$^"), re.I)
            offers = [o for o in offers if inc.search(o.store) and not exc.search(o.store)]
        stamps[sid] = {"store": cfg.get("store", "e-kalathi (South supermarkets)"), "side": cfg["side"],
                       "fetched_at": raw["fetched_at"], "products": len(offers)}
        (north if cfg["side"] == "N" else south).extend(offers)

    prev = {}
    if (SITE_DATA / "prices.json").exists():
        prev = json.loads((SITE_DATA / "prices.json").read_text(encoding="utf-8")).get("fx", {})
    rate_info = fx.eur_try(http, prev) if not args.offline else (prev or fx.eur_try(http))
    rate = rate_info["eur_try"]

    PINNED[:] = shops.get("ekalathi", {}).get("pinned_stores", [])
    # approved shopper prices (and a review list of new ones)
    known = {}
    for o in north + south:
        if o.barcode:
            name, prices = known.setdefault(o.barcode, (o.name, {"N": [], "S": []}))
            if o.currency == "EUR":
                prices[o.side].append(o.price)
    contributed = contrib.load(http, load_yaml("contributions.yaml") if (ROOT / "config" / "contributions.yaml").exists() else {},
                               known, ROOT)
    contributed += contrib.reported(ROOT)
    for o in contributed:
        (north if o.side == "N" else south).append(o)
    if contributed:
        stamps["contrib"] = {"store": "Reported prices (shoppers / app screenshots)", "side": "N+S",
                             "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "products": len(contributed)}

    overrides = load_yaml("overrides.yaml") if (ROOT / "config" / "overrides.yaml").exists() else {}
    groups = match(north, south, load_yaml("matching.yaml"), overrides)
    groups += generic(north, south, load_yaml("generic_items.yaml") or [])
    groups += manual_groups(ROOT / "data" / "manual_prices.csv")
    items = build_items(groups, rate)

    SITE_DATA.mkdir(parents=True, exist_ok=True)
    out = {"updated": datetime.now(timezone.utc).isoformat(timespec="minutes"), "fx": rate_info,
           "sources": stamps, "count": len(items),
           "cheaper_north": sum(i["cheaper"] == "N" for i in items),
           "cheaper_south": sum(i["cheaper"] == "S" for i in items), "items": items}
    (SITE_DATA / "prices.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    if (ROOT / "config" / "wanted.yaml").exists():
        w = wanted.build(north, south, groups, load_yaml("wanted.yaml"), rate)
        (SITE_DATA / "wanted.json").write_text(json.dumps(w, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    stamp_assets()
    write_report(report, out, len(north), len(south), http.count)
    if report and all(r["status"] == "failed" for r in report):
        sys.exit(1)


def write_report(report, out, n_north, n_south, requests_made):
    lines = ["# Compare Cyprus - daily run", "",
             f"- Updated: {out['updated']}", f"- 1 EUR = {out['fx']['eur_try']} TRY ({out['fx'].get('date')})",
             f"- North products read: {n_north}, South prices read: {n_south}",
             f"- **Compared items on the website: {out['count']}** "
             f"(cheaper in North: {out['cheaper_north']}, South: {out['cheaper_south']})",
             f"- Web requests: {requests_made}", ""]
    if report:
        lines += ["| Shop | Result | Products | Note |", "|---|---|---|---|"]
        for r in report:
            lines.append(f"| {r['shop']} | {r['status']} | {r['products']} | {r.get('error', '')} |")
    text = "\n".join(lines) + "\n"
    (ROOT / "data" / "report.md").write_text(text, encoding="utf-8")
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
