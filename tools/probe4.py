"""e-kofini daily retail prices page (my.e-kofini.gov.cy)."""
import re
import requests
from scraper.net import USER_AGENT
S = requests.Session(); S.headers["User-Agent"] = USER_AGENT
def get(u):
    r = S.get(u, timeout=30); print(f"GET {u} -> {r.status_code} {r.headers.get('content-type','')} {len(r.content)}"); return r
def strip(t): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style).*?</\1>", " ", t)))
for lang in ["en", "el"]:
    t = get(f"https://my.e-kofini.gov.cy/{lang}").text
    links = sorted(set(re.findall(r'href="(https://my\.e-kofini\.gov\.cy[^"]*|/[^"]*)"', t)))
    print(links)
t = get("https://my.e-kofini.gov.cy/en").text
for u in sorted(set(re.findall(r'href="(https://my\.e-kofini\.gov\.cy/en/[^"]+)"', t)))[:8]:
    r = get(u); tx = r.text
    print("   tables:", len(re.findall(r"<table", tx)), "selects:", re.findall(r'(?s)<select[^>]*>(.*?)</select>', tx)[:1][:1] and len(re.findall(r"<option", tx)))
    print("   wire:", sorted(set(re.findall(r'wire:(?:model|click|change)[^=]*="([^"]+)"', tx)))[:15])
    print("   text:", strip(tx)[:2500])
    rows = re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", tx)
    for row in rows[:25]:
        print("     ROW:", strip(row)[:200])
