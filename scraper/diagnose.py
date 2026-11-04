"""Check one shop quickly and save what the scraper saw.

    python -m scraper.diagnose starling
    python -m scraper.diagnose starling https://www.starlingsupermarket.com/kategori/sut

Prints the first products it can read from one listing page and saves the
page to debug/<shop>.html, so a broken shop can be fixed from that file.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .net import Http
from .run import ROOT, load_yaml
from .sources import shop_html


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    sid = sys.argv[1]
    cfg = {**load_yaml("shops.yaml")[sid], "id": sid}
    http = Http(delay=0.5)
    if cfg["type"] == "ekalathi":
        from .sources import ekalathi
        print("chains:", ekalathi.companies(http)[:20])
        first = next(ekalathi.product_pages(http, 5), None)
        print("first product:", first)
        return
    url = sys.argv[2] if len(sys.argv) > 2 else None
    if not url:
        cats = shop_html.discover_categories(http, cfg)
        print(f"{len(cats)} listing pages found, e.g.:", *cats[:5], sep="\n  ")
        url = cats[0] if cats else cfg["start_url"]
    html = http.text(url)
    dbg = ROOT / "debug"
    dbg.mkdir(exist_ok=True)
    (dbg / f"{sid}.html").write_text(html, encoding="utf-8")
    page = shop_html.soup(html)
    found = shop_html.jsonld_products(page, url) or shop_html.cards(page, url, cfg["product_link"], cfg.get("selectors"))
    print(f"\n{url}\n{len(found)} products read. First 10:")
    for f in found[:10]:
        print(f"  {f['price']:>10.2f}  {f['name'][:60]:<60}  img={'yes' if f['image'] else 'no'}")
    print(f"\nPage saved to {Path('debug') / (sid + '.html')}")


if __name__ == "__main__":
    main()
