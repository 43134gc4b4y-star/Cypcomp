"""Second look at the most promising candidates (manual, a few pages each)."""
import re, json, collections
from urllib import robotparser
import requests
from scraper.net import USER_AGENT
S = requests.Session(); S.headers["User-Agent"] = USER_AGENT
print("our user agent:", USER_AGENT)

def get(u):
    r = S.get(u, timeout=30); print(f"GET {u} -> {r.status_code} {r.headers.get('content-type','')} {len(r.content)}"); return r

def strip(t): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style).*?</\1>", " ", t)))

print("=" * 90, "\nGIRINCE")
rb = get("https://girince.com/robots.txt").text
print(rb)
rp = robotparser.RobotFileParser(); rp.parse(rb.splitlines())
sm = get("https://girince.com/sitemap.xml").text
parts = re.findall(r"<loc>([^<]+)</loc>", sm); print(len(parts), parts)
urls = []
for p in parts:
    if "products" in p:
        t = get(p.replace("&amp;", "&")).text; u = re.findall(r"<loc>([^<]+)</loc>", t); urls += u; print("   ", len(u))
print("product urls:", len(urls))
kw = collections.Counter()
for u in urls:
    for w in ["nivea", "dove", "colgate", "gillette", "pantene", "loreal", "garnier", "rexona", "head-shoulders", "nescafe", "johnson", "pampers", "sampuan", "deodorant", "dis-macunu", "sabun", "deterjan", "sut", "kahve", "cikolata"]:
        if w in u: kw[w] += 1
print(kw.most_common())
grocery = [u for u in urls if any(w in u for w in ["nivea", "dove", "colgate", "nescafe", "sampuan"])][:3]
for u in grocery:
    print("can fetch:", rp.can_fetch(USER_AGENT, u))
    t = get(u).text
    print("   ld+json:", [x[:900] for x in re.findall(r'(?s)<script type="application/ld\+json">(.*?)</script>', t)][:2])
    print("   seller hints:", re.findall(r'(?i)(satıcı|mağaza|seller)[^<]{0,80}', t)[:5])
    print("   türkiye'den:", "Türkiye" in t, re.findall(r"(?i)türkiye'?den[^<]{0,60}", t)[:3])

print("=" * 90, "\nKIBRIS ONLINE MARKET")
t = get("https://kibrisonlinemarket.com/sitemap.xml").text
locs = re.findall(r"<loc>([^<]+)</loc>", t); print("urls:", len(locs))
pat = collections.Counter(re.sub(r"https://kibrisonlinemarket.com/([^/]+)/?.*", r"\1", u) for u in locs); print(pat.most_common(15))
samp = [u for u in locs if "/urun/" in u or "/p/" in u][:2] or locs[100:102]
for u in samp + ["https://kibrisonlinemarket.com/fiyatlar"]:
    r = get(u); tx = r.text
    print("   ld+json:", [x[:700] for x in re.findall(r'(?s)<script type="application/ld\+json">(.*?)</script>', tx)][:2])
    print("   text:", strip(tx)[:900])

print("=" * 90, "\nMOA e-KOFINI")
for u in ["https://www.moa.gov.cy/moa/da/da.nsf/ekofini_en/ekofini_en?opendocument", "https://www.moa.gov.cy/ekofini", "https://e-kofini.gov.cy/"]:
    try:
        r = get(u); tx = r.text
        print("   links:", [l for l in re.findall(r'href="([^"]+)"', tx) if re.search(r"(?i)pdf|xls|csv|kofini|price|τιμ", l)][:30])
        print("   text:", strip(tx)[:1200])
    except Exception as e:
        print("   ", e)
