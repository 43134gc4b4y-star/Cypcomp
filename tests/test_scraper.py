import json
from pathlib import Path

import pytest

from scraper import run
from scraper.match import generic, match
from scraper.models import Offer
from scraper.sources import ekalathi, shop_html, woocommerce
from scraper.text import Size, find_prices, parse_number, parse_size

FIX = Path(__file__).parent / "fixtures"


# ----------------------------------------------------------- text parsing

@pytest.mark.parametrize("s,v", [("1.050,00", 1050.0), ("49,90", 49.9), ("10.25", 10.25), ("1,050.00", 1050.0),
                                 ("1050", 1050.0), ("1.050", 1050.0), ("0,5", 0.5)])
def test_parse_number(s, v):
    assert parse_number(s) == v


def test_find_prices():
    assert find_prices("Eski 349,90 TL Yeni 295,20 TL Sepete Ekle") == [349.9, 295.2]
    assert find_prices("CEMER SU 0.5LT. 10.25 ₺") == [10.25]
    assert find_prices("€1.37") == [1.37]
    assert find_prices("PINAR 700 G") == []
    assert find_prices("1097.25 TL") == [1097.25]
    assert find_prices("12345,90 ₺") == [12345.9]
    assert find_prices("<b>1.</b> 007,25 TL".replace("<b>", "").replace("</b>", "")) == [1007.25]


@pytest.mark.parametrize("name,size", [
    ("PINAR DOYUM SALAM HINDI 700 G", Size("g", 700)),
    ("COCA COLA KUTU 8X330 ML", Size("ml", 330, 8)),
    ("Coca Cola Can 330ml x8", Size("ml", 330, 8)),
    ("Coca-Cola 2X1L", Size("ml", 1000, 2)),
    ("GULGUN UHT YAGLI SUT 1000 ML", Size("ml", 1000)),
    ("Lanitis Milk 1L", Size("ml", 1000)),
    ("PINAR PREMIUM SU KALIN PET SISE 0.4 LT", Size("ml", 400)),
    ("NIKIFOROU EGGS (L) 12 ΤΕΜΑΧΙΑ", Size("pc", 12)),
    ("SELPAK TUVALET KAGIDI 4 LU", Size("pc", 4)),
    ("Nescafe Classic 200gr", Size("g", 200)),
    ("Halloumi 1kg", Size("g", 1000)),
    ("DOMATES KG", None),
    ("Valio Edam 24% Slices 400g+80g FREE", Size("g", 400)),
    ("SUTAS UCGEN PEYNIR 16 LI 200 G", Size("g", 200)),
    ("SPRITE GAZOZ 1 LT 12 LI", Size("ml", 1000)),
    ("SOFF YUMUSATICI 1400 LT", Size("ml", 1400)),
    ("GULGUN GUNLUK SUT 1000 CL", Size("ml", 1000)),
])
def test_parse_size(name, size):
    got = parse_size(name)
    if size is None:
        assert got is None
    else:
        assert got is not None and got.unit == size.unit and got.count == size.count and got.each == pytest.approx(size.each)


# ----------------------------------------------------------- shop pages

def test_starling_cards():
    page = shop_html.soup((FIX / "starling_category.html").read_text(encoding="utf-8"))
    found = shop_html.cards(page, "https://www.starlingsupermarket.com/kategori/salam", "/urun/")
    by_name = {f["name"]: f for f in found}
    assert len(found) == 5
    salam = by_name["PINAR DOYUM SALAM HINDI 700 G"]
    assert salam["price"] == 286.9
    assert salam["image"].endswith("pinar-doyum-salam-hindi-700-g-8548_min.png")  # not the loader.gif
    assert by_name["COCA COLA KUTU 8X330 ML"]["price"] == 295.2  # discounted price, not the old one
    assert by_name["NESCAFE KLASIK 100 G"]["price"] == 1050.0


class FakeHttp:
    """Answers requests from a dict of url -> data, like a tiny internet."""
    def __init__(self, routes):
        self.routes = routes
        self.count = 0

    def _find(self, url):
        self.count += 1
        for key, val in self.routes.items():
            if key in url:
                return val(url) if callable(val) else val
        raise RuntimeError(f"404 {url}")

    def json(self, url, **kw):
        return self._find(url)

    def text(self, url, **kw):
        return self._find(url)


def test_shop_html_pagination_stops_when_pages_repeat():
    html = (FIX / "starling_category.html").read_text(encoding="utf-8")
    http = FakeHttp({"starlingsupermarket.com": html})  # every page returns the same items
    cfg = {"id": "starling", "side": "N", "store": "Starling", "base_url": "https://www.starlingsupermarket.com",
           "start_url": "https://www.starlingsupermarket.com/", "category_link": "/kategori/",
           "product_link": "/urun/", "page_param": "sayfa", "max_pages": 10}
    offers = shop_html.scrape(http, cfg)
    assert len(offers) == 5
    assert http.count <= 1 + 3 * 2  # menu + (page 1 and page 2) per category, then stop


def test_woocommerce_store_api():
    products = [{"name": "8692005190019 KOOP S&Uuml;T 1 LT", "permalink": "https://www.sarpermarket.com/urunler/koop-sut-1-lt/",
                 "is_in_stock": True, "prices": {"price": "7550", "currency_code": "TRY", "currency_minor_unit": 2},
                 "images": [{"src": "https://www.sarpermarket.com/wp-content/uploads/koop.jpg"}],
                 "categories": [{"name": "Süt"}]}]
    http = FakeHttp({"wc/store/v1/products?per_page=100&page=1": products})
    offers = woocommerce.scrape(http, {"id": "sarper", "side": "N", "store": "Sarper Market",
                                       "base_url": "https://www.sarpermarket.com"})
    assert len(offers) == 1
    o = offers[0]
    assert o.price == 75.5 and o.currency == "TRY" and o.barcode == "8692005190019" and o.name == "KOOP SÜT 1 LT"


def ekalathi_routes():
    catalogue = [
        {"productMasterId": 2194, "name": "Coca Cola 330ml x8 Can", "startPrice": 4.35,
         "productCategoryNameEnglish": "Soft drinks", "productThumbnailUrl": "/img/2194.png"},
        {"productMasterId": 2195, "name": "Coca Cola Zero 330ml x8 Can", "startPrice": 4.45,
         "productCategoryNameEnglish": "Soft drinks"},
        {"productMasterId": 2312, "name": "Nescafe Classic 100g", "startPrice": 4.19,
         "productCategoryNameEnglish": "Coffee"},
        {"productMasterId": 7, "name": "Charalambides Fresh Milk 1L", "startPrice": 1.37},
    ]
    prices = {2194: [("ΣΚΛΑΒΕΝΙΤΗΣ", 4.35), ("LIDL", 4.65)], 2195: [("ΣΚΛΑΒΕΝΙΤΗΣ", 4.45), ("LIDL", 4.65)],
              2312: [("LIDL", 4.19), ("ΣΚΛΑΒΕΝΙΤΗΣ", 4.49)], 7: [("LIDL", 1.37)]}

    def branches(url):
        pid = int(url.split("productId=")[1].split("&")[0])
        if "companyIds=" in url:
            return {"content": []}
        return {"content": [{"companyName": c, "name": c + " Λεμεσός", "retailerProductPrice": p,
                             "postalAddress": "Street 1, Limassol", "branchLatitude": "34°41'44.3\"N",
                             "branchLongitude": "33°04'49.6\"E", "companyPhotoFile": "xxxx"} for c, p in prices[pid]]}

    return {"retail/fetch-retail-branch-list": branches,
            "fetch-product-list": {"content": catalogue, "last": True}}


def test_ekalathi_prices_per_branch():
    offers = ekalathi.scrape(FakeHttp(ekalathi_routes()), {})
    cola = [o for o in offers if o.product_id == "2194"]
    assert [(o.store, o.price) for o in cola] == [("Sklavenitis", 4.35), ("Lidl", 4.65)]
    assert cola[0].image == "https://www.e-kalathi.gov.cy/img/2194.png"
    assert cola[0].url.endswith("/product-information/2194")
    assert cola[0].maps.endswith("query=34.695639,33.080444")   # exact branch location


# ----------------------------------------------------------- matching

def N(name, price, store="Starling", url=None):
    return Offer(source="t", side="N", store=store, name=name, price=price, currency="TRY", url=url or name)


def S(name, price, pid, store="Lidl", cat=""):
    return Offer(source="ekalathi", side="S", store=store, name=name, price=price, currency="EUR", product_id=str(pid),
                 category=cat)


@pytest.fixture
def mcfg():
    return run.load_yaml("matching.yaml")


def test_match_same_brand_and_size(mcfg):
    north = [N("COCA COLA KUTU 8X330 ML", 295.2), N("COCA COLA ZERO KUTU 8X330 ML", 295.2),
             N("NESCAFE KLASIK 100 G", 223.9), N("NESCAFE KLASIK 200 G", 366.9), N("PINAR SUT 1 LT", 50)]
    south = [S("Coca Cola 330ml x8 Can", 4.65, 2194), S("Coca Cola Zero 330ml x8 Can", 4.65, 2195),
             S("Nescafe Classic 100g", 4.19, 2312), S("Charalambides Fresh Milk 1L", 1.37, 7)]
    groups = {g.id: [o.name for o in g.north] for g in match(north, south, mcfg)}
    assert groups == {"ek-2194": ["COCA COLA KUTU 8X330 ML"],
                      "ek-2195": ["COCA COLA ZERO KUTU 8X330 ML"],
                      "ek-2312": ["NESCAFE KLASIK 100 G"]}   # 200 g has no South twin, Pinar no brand twin


def test_conflict_word_blocks_match(mcfg):
    north = [N("COCA COLA ZERO KUTU 8X330 ML", 295.2)]
    south = [S("Coca Cola 330ml x8 Can", 4.65, 2194)]
    assert match(north, south, mcfg) == []


def test_nappy_sizes_must_agree(mcfg):
    south = [S("Pampers Premium Care Jumbo S3 60 pieces", 10.49, 4), S("Pampers Premium Care Jumbo S4 60 pieces", 11.49, 5)]
    north = [N("PAMPERS PREMIUM CARE JUMBO 3 NUMARA 60 ADET", 899.9), N("PAMPERS PREMIUM CARE JUMBO NO 4 60 ADET", 949.9)]
    groups = {g.id: [o.name for o in g.north] for g in match(north, south, mcfg)}
    assert groups == {"ek-4": [north[0].name], "ek-5": [north[1].name]}


def test_overrides(mcfg):
    north = [N("PINAR SUT 1 LT", 50, url="u1"), N("COCA COLA KUTU 8X330 ML", 295.2, url="u2")]
    south = [S("Charalambides Fresh Milk 1L", 1.37, 7), S("Coca Cola 330ml x8 Can", 4.65, 2194)]
    ov = {"same": [{"north": "u1", "south": 7}], "different": [{"north": "u2", "south": 2194}]}
    assert [g.id for g in match(north, south, mcfg, ov)] == ["ek-7"]


def test_generic_milk_per_litre():
    items = run.load_yaml("generic_items.yaml")
    north = [N("GULGUN UHT YAGLI SUT 1000 ML", 63.9), N("PINAR CIKOLATALI SUT 200 ML", 20), N("SUTAS AYRAN 1 LT", 40)]
    south = [S("Alambra Fresh Cyprus Milk Full Fat (Blue) 2L", 2.70, 1, cat="FRESH MILK"),
             S("Lanitis Chocolate Milk 1L", 1.5, 2, cat="FRESH MILK")]
    g = [x for x in generic(north, south, items) if x.id == "gen-milk"][0]
    assert [(o.name, o.price) for o in g.north] == [("GULGUN UHT YAGLI SUT 1000 ML", 63.9)]
    assert [(o.name, o.price) for o in g.south] == [("Alambra Fresh Cyprus Milk Full Fat (Blue) 2L", 1.35)]  # per litre


def test_cheapest_store_comes_first():
    offers = [{"store": "A", "eur": 1.0}, {"store": "B", "eur": 2.0}, {"store": "B", "eur": 3.0}, {"store": "A", "eur": 4.0}]
    assert run._cheapest_per_store(offers) == [{"store": "A", "eur": 1.0}, {"store": "B", "eur": 2.0}]


def test_brand_plus_size_with_filler_words(mcfg):
    north = [N("TWIX CIKOLATA 50 G", 30), N("PRINGLES SALT&VINEGAR 165 G", 120)]
    south = [S("Twix 50g Twin", 0.9, 10), S("Pringles Original 165g", 2.5, 11)]
    assert {g.id for g in match(north, south, mcfg)} == {"ek-10"}   # flavour differs for Pringles


# ----------------------------------------------------------- whole run

def test_end_to_end(tmp_path, monkeypatch):
    html = (FIX / "starling_category.html").read_text(encoding="utf-8")
    routes = {**ekalathi_routes(), "starlingsupermarket.com": html,
              "frankfurter": {"rates": {"TRY": 50.0}, "date": "2026-11-03"}}
    monkeypatch.setattr(run, "RAW", tmp_path / "raw")
    monkeypatch.setattr(run, "SITE_DATA", tmp_path / "site")
    monkeypatch.setattr(run, "ROOT", run.ROOT)
    monkeypatch.setattr(run, "Http", lambda delay: FakeHttp(routes))
    shops = {"ekalathi": {"type": "ekalathi", "side": "S"},
             "starling": {"type": "shop_html", "side": "N", "store": "Starling Supermarket",
                          "base_url": "https://www.starlingsupermarket.com",
                          "start_url": "https://www.starlingsupermarket.com/", "category_link": "/kategori/",
                          "product_link": "/urun/", "page_param": "sayfa", "max_pages": 3, "maps": "m"}}
    real_load = run.load_yaml
    monkeypatch.setattr(run, "load_yaml", lambda n: shops if n == "shops.yaml" else real_load(n))
    monkeypatch.setattr(run, "write_report", lambda *a, **k: None)
    run.main([])
    out = json.loads((tmp_path / "site" / "prices.json").read_text())
    by = {i["id"]: i for i in out["items"]}
    assert out["fx"]["eur_try"] == 50.0
    cola = by["ek-2194"]
    # North 295.20 TL = 5.90 EUR; South cheapest is Sklavenitis 4.35 -> South cheaper
    assert cola["cheaper"] == "S" and cola["south"][0]["store"] == "Sklavenitis"
    assert cola["north"][0]["eur"] == 5.9 and cola["north"][0]["try"] == 295.2
    assert "ek-2195" in by  # zero matched with zero


def test_pack_size_pass(mcfg):
    north = [N("KERRYGOLD TEREYAGI TUZSUZ FOLYO 200 G", 275), N("NESCAFE GOLD BLEND ALTA RICA SISE 95 G", 495)]
    south = [S("Kerrygold Butter Unsalted 250g Foil", 3.65, 20), S("Nescafé Gold Blend 190g Jar", 6.48, 21)]
    groups = {g.id: g for g in match(north, south, mcfg)}
    assert set(groups) == {"ps-20"}                       # Alta Rica is a different coffee
    g = groups["ps-20"]
    assert g.north[0].price == 1375.0 and g.south[0].price == 14.6   # both per kg
    assert "pack sizes differ" in g.unit


def test_ekalathi_pinned_chain_added():
    routes = ekalathi_routes()
    base = routes["retail/fetch-retail-branch-list"]

    def branches(url):
        if "companyIds=471" in url:
            return {"content": [{"companyName": "ΑΛΦΑΜΕΓΑ", "name": "ΑΛΦΑΜΕΓΑ Ακρόπολης", "retailerProductPrice": 9.99}]}
        return base(url) if "companyIds=" not in url else {"content": []}

    routes["retail/fetch-retail-branch-list"] = branches
    offers = ekalathi.scrape(FakeHttp(routes), {"always_include_chain_ids": [471]})
    stores = {o.store for o in offers if o.product_id == "2194"}
    assert stores == {"Sklavenitis", "Lidl", "AlphaMega"}


FETCH_PAGE = """<html><head>
<script type="application/ld+json">{"@type":"BreadcrumbList","itemListElement":[{"name":"Home"},{"name":"Food Cupboard"},{"name":"Crisps"},{"name":"Pringles Original 165g"}]}</script>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":"Pringles Original 165g",
 "image":["https://img/p.webp"],"gtin13":"5053990101573",
 "offers":{"@type":"Offer","url":"https://fetch.com.cy/p/pringles-original-165g","price":2.45,"priceCurrency":"EUR",
 "availability":"https://schema.org/InStock","seller":{"@type":"Organization","name":"Grocery Island"}}}</script>
</head><body></body></html>"""


def test_fetch_product_page():
    from scraper.sources import fetchcy
    offers = fetchcy.read_product(FakeHttp({"fetch.com.cy/p/": FETCH_PAGE}), "https://fetch.com.cy/p/pringles-original-165g")
    assert len(offers) == 1
    o = offers[0]
    assert (o.store, o.price, o.barcode, o.category) == ("Grocery Island", 2.45, "5053990101573", "Crisps")
    assert o.product_id == "gtin-5053990101573"


def test_fetch_candidates(mcfg):
    from scraper.sources import fetchcy
    urls = ["https://fetch.com.cy/p/pringles-original-165g", "https://fetch.com.cy/p/pringles-original-200g",
            "https://fetch.com.cy/p/urino-vet-dog-16gr"]
    north = [N("PRINGLES ORIGINAL 165 G", 149.9)]
    # same size first, then a similar pack size (compared per kg); unrelated products skipped
    assert fetchcy.candidates(urls, north, mcfg, 10) == ["https://fetch.com.cy/p/pringles-original-165g",
                                                          "https://fetch.com.cy/p/pringles-original-200g"]


def test_barcode_decides(mcfg):
    a = N("PRINGLES ORIGINAL 165 G", 149.9); a.barcode = "5053990101573"
    b = N("PRINGLES ORIGINAL 165 G", 139.9, url="other"); b.barcode = "1111111111111"
    s = S("Pringles Original 165g", 2.45, "gtin-5053990101573"); s.barcode = "5053990101573"; s.source = "fetch"
    groups = match([a, b], [s], mcfg)
    assert [[o.url for o in g.north] for g in groups] == [[a.url]]   # different barcode is rejected


def test_sugar_free_is_not_sugar(mcfg):
    north = [N("POKKA BLACK COFFEE NO SUGAR 240ML", 60)]
    south = [S("Pokka Black Coffee with sugar 240ml", 1.1, 30)]
    assert match(north, south, mcfg) == []


# --- shopper contributions ---
from scraper import contrib


def test_ean_check_digit():
    assert contrib.ean_ok("5449000000996")      # Coca-Cola 330ml
    assert not contrib.ean_ok("5449000000997")
    assert not contrib.ean_ok("12345")


def test_contrib_row_to_offer():
    row = {"Timestamp": "2026-11-05 10:00:00", "Side": "North", "Shop": "Molto", "Town": "Lefkoşa",
           "Product": "Coca-Cola", "Barcode": "5449000000996", "Pack size": "330 ml", "Price": "45,50",
           "Currency": "TRY", "Approved": "yes"}
    o = contrib.to_offer(row)
    assert o.side == "N" and o.currency == "TRY" and o.price == 45.5
    assert o.name == "Coca-Cola 330 ml" and o.barcode == "5449000000996"
    assert "shopper" in o.town
    assert contrib.to_offer({"Side": "South", "Product": "", "Price": "1"}) is None


def test_contrib_review_and_approval(tmp_path):
    (tmp_path / "data").mkdir()

    class FakeHttp:
        pass

    rows = [
        {"Side": "South", "Shop": "Sklavenitis", "Product": "Coke", "Barcode": "5449000000996",
         "Price": "9.99", "Currency": "EUR", "Approved": ""},
        {"Side": "South", "Shop": "Lidl", "Product": "Coke", "Barcode": "5449000000996",
         "Price": "0.89", "Currency": "EUR", "Approved": "yes"},
    ]
    contrib.read_rows = lambda http, url: rows
    got = contrib.load(FakeHttp(), {"csv_url": "x"}, {"5449000000996": ("Coca-Cola 330ml", {"N": [], "S": [0.8, 1.0]})},
                       tmp_path)
    assert len(got) == 1 and got[0].store == "Lidl"
    review = (tmp_path / "data" / "contributions_review.md").read_text()
    assert "Sklavenitis" in review and "⚠️" in review


def test_fetch_staple_urls():
    from scraper.sources.fetchcy import staple_urls
    urls = ["https://fetch.com.cy/p/cyprus-white-sugar-1kg", "https://fetch.com.cy/p/sugar-free-gum",
            "https://fetch.com.cy/p/colgate-toothpaste-75ml", "https://fetch.com.cy/p/white-sugar"]
    got = staple_urls(urls, ["white-sugar", "toothpaste"], 5)
    assert got == ["https://fetch.com.cy/p/white-sugar", "https://fetch.com.cy/p/cyprus-white-sugar-1kg",
                   "https://fetch.com.cy/p/colgate-toothpaste-75ml"]
