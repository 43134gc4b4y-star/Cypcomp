"""Where e-kofini (Cyprus Dept. of Agriculture fruit & veg price observatory) publishes its prices."""
import re
from urllib import robotparser
import requests
from scraper.net import USER_AGENT
S = requests.Session(); S.headers["User-Agent"] = USER_AGENT

def get(u):
    r = S.get(u, timeout=30); print(f"GET {u} -> {r.status_code} {r.headers.get('content-type','')} {len(r.content)}"); return r
def strip(t): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style).*?</\1>", " ", t)))

for host in ["https://e-kofini.gov.cy", "https://my.e-kofini.gov.cy"]:
    try:
        print(get(host + "/robots.txt").text[:600])
    except Exception as e:
        print(e)
home = get("https://e-kofini.gov.cy/en/").text
links = sorted(set(re.findall(r'href="([^"]+)"', home)))
print([l for l in links if "e-kofini" in l][:60])
for u in [l for l in links if re.search(r"(?i)data|report|dedomena|ekth|δεδομ", l)][:4]:
    t = get(u).text
    print("  links:", sorted(set(l for l in re.findall(r'href="([^"]+)"', t) if re.search(r"(?i)\.pdf|\.xls|\.csv|uploads|my\.e-kofini|api", l)))[:40])
    print("  text:", strip(t)[:1500])
try:
    pages = get("https://e-kofini.gov.cy/wp-json/wp/v2/pages?per_page=50&_fields=id,slug,link,title").json()
    for p in pages: print("   page", p.get("slug"), p.get("link"))
    media = get("https://e-kofini.gov.cy/wp-json/wp/v2/media?per_page=20&_fields=source_url,date,mime_type").json()
    for m in media: print("   media", m.get("date"), m.get("mime_type"), m.get("source_url"))
except Exception as e:
    print("wp-json:", e)
t = get("https://my.e-kofini.gov.cy/el").text
print("  my scripts:", re.findall(r'<script[^>]+src="([^"]+)"', t)[:10])
print("  my api strings:", sorted(set(re.findall(r'["\'](/?api[^"\']{0,80}|https://[^"\']*api[^"\']{0,80})["\']', t)))[:20])
print("  my text:", strip(t)[:1200])
t = get("https://www.moa.gov.cy/moa/da/da.nsf/ekofini_products_table_en/ekofini_products_table_en?Openform").text
print("  moa table text:", strip(t)[-3000:])
