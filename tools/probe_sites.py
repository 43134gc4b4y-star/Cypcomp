"""Temporary: identify shop platforms, robots rules and product feeds."""
import re, json, sys, urllib.robotparser
import requests
UA = "Mozilla/5.0 (compatible; CompareCyprusBot/1.0)"
S = requests.Session(); S.headers["User-Agent"] = UA
SITES = sys.argv[1:]
for base in SITES:
    print("\n=====", base)
    try:
        r = S.get(base, timeout=25); html = r.text
        print("home", r.status_code, len(html), "final", r.url)
    except Exception as e:
        print("home ERR", e); continue
    gen = re.findall(r'<meta name="generator" content="([^"]+)"', html)
    hints = [k for k in ("shopify", "woocommerce", "wp-content", "ideasoft", "/idea/", "ticimax", "opencart", "magento", "prestashop", "nopcommerce", "__NEXT_DATA__", "nuxt", "vtex", "salesforce", "angular", "react") if k.lower() in html.lower()]
    print("generator", gen[:2], "hints", hints)
    links = re.findall(r'href="([^"#]+)"', html)
    pat = {}
    for l in links:
        m = re.match(r'(?:https?://[^/]+)?(/[^/?]+/)', l)
        if m: pat[m.group(1)] = pat.get(m.group(1), 0) + 1
    print("top paths", sorted(pat.items(), key=lambda x: -x[1])[:12])
    print("prices on home", len(re.findall(r'\d+[.,]\d{2}\s*(?:₺|TL|€)|€\s*\d+[.,]\d{2}', html)))
    try:
        rb = S.get(base.rstrip('/') + '/robots.txt', timeout=15)
        rp = urllib.robotparser.RobotFileParser(); rp.parse(rb.text.splitlines())
        print("robots", rb.status_code, "| disallow lines:", [l for l in rb.text.splitlines() if l.lower().startswith('disallow')][:10])
    except Exception as e:
        rp = None; print("robots ERR", e)
    for path in ("/products.json?limit=3", "/wp-json/wc/store/v1/products?per_page=2", "/sitemap.xml", "/sitemap_index.xml"):
        u = base.rstrip('/') + path
        ok = rp.can_fetch(UA, u) if rp else True
        try:
            r = S.get(u, timeout=20)
            body = r.text[:400].replace("\n", " ")
            print(f"{path} allowed={ok} {r.status_code} {len(r.text)} :: {body[:300]}")
        except Exception as e:
            print(path, "ERR", e)

# extra: list all internal links of the two sites to spot shop/campaign pages
for base in SITES:
    try:
        html = S.get(base, timeout=25).text
    except Exception:
        continue
    links = sorted(set(re.findall(r'href="([^"#]+)"', html)))
    print("\n--- links on", base, len(links))
    for l in links[:120]:
        print("  ", l)
