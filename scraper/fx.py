"""Euro -> Turkish lira rate, refreshed every run (European Central Bank data)."""
from __future__ import annotations

import logging
from datetime import date

log = logging.getLogger(__name__)

SOURCES = [
    ("https://api.frankfurter.dev/v1/latest?base=EUR&symbols=TRY", lambda d: (d["rates"]["TRY"], d.get("date"))),
    ("https://api.frankfurter.app/latest?from=EUR&to=TRY", lambda d: (d["rates"]["TRY"], d.get("date"))),
    ("https://open.er-api.com/v6/latest/EUR", lambda d: (d["rates"]["TRY"], d.get("time_last_update_utc", "")[:16])),
]


def eur_try(http, previous: dict | None = None) -> dict:
    for url, read in SOURCES:
        try:
            rate, when = read(http.json(url))
            if rate and 10 < float(rate) < 1000:
                return {"eur_try": round(float(rate), 4), "date": when or date.today().isoformat(), "source": url.split("/")[2]}
        except Exception as e:  # noqa: BLE001
            log.warning("FX source %s failed: %s", url, e)
    if previous and previous.get("eur_try"):
        log.warning("Using yesterday's exchange rate")
        return {**previous, "stale": True}
    raise RuntimeError("No exchange rate available")
