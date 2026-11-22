"""One-off check of possible new price sources: what robots.txt allows and how prices are published.
Run by .github/workflows/probe.yml (manual). Reads only a handful of pages per site."""
import re, sys, json
from urllib.parse import urljoin, urlparse
from urllib import robotparser
import requests
from scraper.net import USER_AGENT

SITES = sys.argv[1:] or ["https://www.e-kofini.gov.cy/", "https://girince.com/", "https://www.yildirimsanalmarket.com/", "https://kibrisonlinemarket.com/"]
S = requests.Session(); S.headers["User-Agent"] = USER_AGENT

def show(url, n=1800):
    try:
        r = S.get(url, timeout=25)
    except Exception as e:
        print("   GET", url, "->", e); return None
    print(f"   GET {url} -> {r.status_code} {r.headers.get('content-type','')} {len(r.content)} bytes")
    return r

for site in SITES:
    base = f"{urlparse(site).scheme}://{urlparse(site).netloc}/"
    print("=" * 100); print(site)
    rp = robotparser.RobotFileParser(); r = show(urljoin(base, "robots.txt"))
    if r is not None and r.ok:
        print("   robots.txt:\n      " + "\n      ".join(r.text.strip().splitlines()[:40]))
        rp.parse(r.text.splitlines())
    else:
        rp.parse([])
    r = show(site) if rp.can_fetch(USER_AGENT, site) else print("   homepage disallowed by robots")
    if r is not None and r.ok:
        t = r.text
        print("   generator:", re.findall(r'<meta[^>]+generator[^>]+>', t)[:2])
        print("   platform hints:", sorted({k for k in ["shopify", "woocommerce", "wp-content", "opencart", "route=product", "__NEXT_DATA__", "nuxt", "react", "angular", "vue", "ideasoft", "ticimax", "magento", "prestashop", "wix", "api/"] if k in t.lower()}))
        print("   scripts:", re.findall(r'<script[^>]+src="([^"]+)"', t)[:12])
        links = sorted(set(re.findall(r'href="([^"#]+)"', t)))
        print("   links:", len(links), [l for l in links if re.search(r'kateg|categor|urun|product|fiyat|price|api|json|xls|csv|pdf|sitemap', l, re.I)][:40])
        print("   api-looking strings:", sorted(set(re.findall(r'["\'](/?(?:api|wp-json|graphql|_next/data)[^"\']{0,80})["\']', t)))[:20])
        print("   text sample:", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style).*?</\1>", " ", t)))[:1200])
    for path in ["sitemap.xml", "sitemap_index.xml", "products.json?limit=1", "wp-json/wc/store/v1/products?per_page=1"]:
        u = urljoin(base, path)
        if not rp.can_fetch(USER_AGENT, u):
            print("   disallowed:", u); continue
        r = show(u)
        if r is not None and r.ok:
            print("      ", re.sub(r"\s+", " ", r.text[:700]))
