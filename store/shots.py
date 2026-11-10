"""Play Store graphics from the live site (run by .github/workflows/store-assets.yml)."""
from pathlib import Path
from playwright.sync_api import sync_playwright

SITE = "https://43134gc4b4y-star.github.io/Cypcomp/"
OUT = Path(__file__).parent / "graphics"
OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1024, "height": 500})
    pg.goto((Path(__file__).parent / "feature.html").resolve().as_uri()); pg.wait_for_timeout(2500)
    pg.screenshot(path=str(OUT / "feature-graphic-1024x500.png"))
    for scheme in ("dark", "light"):
        ctx = b.new_context(viewport={"width": 400, "height": 800}, device_scale_factor=2.7, color_scheme=scheme,
                            is_mobile=True, has_touch=True)
        pg = ctx.new_page(); pg.goto(SITE); pg.wait_for_timeout(4000)
        pg.evaluate("document.getElementById('install') && (document.getElementById('install').hidden = true)")
        pg.screenshot(path=str(OUT / f"phone-1-home-{scheme}.png"))
        pg.evaluate("window.scrollTo(0, document.querySelector('.listhead').offsetTop - 70)"); pg.wait_for_timeout(500)
        pg.screenshot(path=str(OUT / f"phone-2-prices-{scheme}.png"))
        pg.fill("#q", "coffee"); pg.wait_for_timeout(800); pg.evaluate("window.scrollTo(0, document.querySelector('#out').offsetTop - 80)"); pg.wait_for_timeout(400)
        pg.screenshot(path=str(OUT / f"phone-3-search-{scheme}.png"))
        pg.fill("#q", ""); pg.click(".tabbar a[data-view=wanted]"); pg.wait_for_timeout(600)
        pg.screenshot(path=str(OUT / f"phone-4-wanted-{scheme}.png"))
        ctx.close()
    b.close()
print("done")
