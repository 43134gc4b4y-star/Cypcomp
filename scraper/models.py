from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Offer:
    """One product at one shop, as read from that shop's website."""
    source: str             # which scraper produced it, e.g. "starling"
    side: str               # "N" (North) or "S" (South)
    store: str              # shop / chain name shown to people
    name: str               # product name exactly as the shop writes it
    price: float            # in the shop's currency
    currency: str           # "TRY" or "EUR"
    url: str = ""           # product page
    image: str = ""         # product photo
    category: str = ""      # shop's own category name
    barcode: str = ""       # EAN, when the shop shows one
    product_id: str = ""    # e-kalathi productMasterId etc.
    town: str = ""
    maps: str = ""          # Google Maps link to the store
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
