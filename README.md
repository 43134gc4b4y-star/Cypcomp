# Compare Cyprus

Is it cheaper in North or South Cyprus? Every morning this project reads
supermarket prices on both sides, pairs up identical products (same brand and
pack size), and publishes a website showing where each one is cheaper, the
store, and a map link. Lira and euro prices are shown side by side.

## How it works

```
 every morning (GitHub Actions, free)
        │
        ├─ South: e-kalathi.gov.cy (government price list, 476 products, cheapest branches)
        ├─ North: Starling, Sarper, Nesdersan, Unimar, Kıbrıs Sanal Market (+ any shop you add)
        ├─ Exchange rate: European Central Bank
        ▼
 pair products  →  site/data/prices.json  →  website (GitHub Pages)
```

| Folder / file | What it is |
|---|---|
| `scraper/` | The Python code that reads the shops and pairs products |
| `config/shops.yaml` | Which shops to read (switch on/off, add new ones) |
| `config/matching.yaml` | Brands, Turkish→English words, rules for pairing |
| `config/generic_items.yaml` | “Any brand” items such as tomatoes or eggs, compared per kg / per piece |
| `config/overrides.yaml` | Force two products to be paired, or never paired |
| `data/manual_prices.csv` | Prices you type in yourself (e.g. fuel) |
| `data/raw/` | Each shop's full product list from the last good run |
| `data/report.md` | Summary of the last run |
| `site/` | The website |

## One-time setup (about 5 minutes)

1. **Repository settings → Actions → General → Workflow permissions:** choose
   **Read and write permissions** and save. This lets the daily job save prices.
2. **Repository settings → Pages → Build and deployment → Source:** choose
   **GitHub Actions**.
3. **Actions tab → “Daily prices” → Run workflow.** The first run takes 10–30
   minutes. When it finishes, the website address appears on the run page
   (usually `https://<your-username>.github.io/<repository-name>/`).

After that it runs by itself every morning at about 05:15–06:15 Cyprus time.

## After the first run

Open the run in the Actions tab. The summary shows a table like:

| Shop | Result | Products |
|---|---|---|
| ekalathi | ok | 6500 |
| starling | ok | 2400 |

If a shop shows **failed** or very few products, the site most likely needs a
small adjustment. Download the **debug-pages** file at the bottom of the run
page (it's created automatically when something fails) and send it, together
with the summary, to whoever maintains the code. The website keeps showing
the last good prices in the meantime.

## Everyday edits (all doable on github.com, no coding)

- **Add a fuel or other hand-typed price:** edit `data/manual_prices.csv`,
  fill in `price` and `date`. An item appears once it has both a North and a
  South row. The site updates within a few minutes of saving.
- **A wrong pairing:** add it under `different:` in `config/overrides.yaml`
  (North product link + e-kalathi product number from its link).
- **A missed pairing:** add it under `same:` in the same file.
- **Add a North shop:** copy a block in `config/shops.yaml`, change the name,
  address and links, and set `enabled: true`.
- **SonMar:** add its online-shop address in `config/shops.yaml` and enable it.

## Running it on a computer (optional)

```bash
pip install -r requirements.txt
python -m scraper.run                  # read everything, build site/data/prices.json
python -m scraper.run --only starling  # one shop
python -m scraper.diagnose starling    # check what the scraper sees on one page
python -m pytest                       # tests
cd site && python -m http.server       # view the site at http://localhost:8000
```

## Shops checked but not included

| Shop | Why |
|---|---|
| Alphamega, CQUARE, SupermarketCy (South) | Bot protection blocks automated visitors |
| Bi-Sipariş, Cepbasket, Kesmar (North) | Bot protection or robots.txt says no |
| Athienitis, Sklavenitis (South) | No online shop with prices |
| Molto, Önder AVM (North) | No prices online (offers only as leaflet photos on Facebook) |
| Hapcı (kibrisonlinemarket) | Products only load with JavaScript |
| Erdener | Online shop holds template sample products, not real prices |
| Supermarket Kıbrıs (Girne) | Refuses automated connections |
| Dmarjet (İskele) | Prices load by JavaScript from an address its robots.txt closes |
| BurdaBurda | robots.txt says no |

## Good to know

- **Coverage:** only shops that publish prices online can be read, and an
  item only appears when the same brand and size exists on both sides, so
  expect hundreds of comparisons rather than every product.
- **Politeness:** the scraper reads one page per second, identifies itself,
  obeys each site's robots.txt, and runs once a day. Check each shop's terms
  before making the site public, and credit e-kalathi as the South source.
- **e-kalathi from abroad:** GitHub's servers are in the US/EU. If e-kalathi
  ever blocks them, the run report will say so.
