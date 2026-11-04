"""Text helpers: price parsing, pack-size parsing and name normalisation.

Shop sites write the same thing in many ways ("1.050,00 TL", "10.25 ₺",
"700 G", "2X1L", "12 ΤΕΜΑΧΙΑ"), so everything is turned into plain numbers
and lowercase ASCII words before products are compared.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# ---------------------------------------------------------------- prices

_NUM = r"(?<![\d.,])(?:\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)(?![\d])"
PRICE_RE = re.compile(
    r"(?:(?P<pre>₺|€|TL|EUR)\s*)?(?P<num>" + _NUM + r")\s*(?P<post>₺|€|TL|TRY|EUR|eur|tl)?",
)


def parse_number(s: str) -> float | None:
    """Parse '1.050,00', '1,050.00', '10.25', '49,90' or '1050' into a float."""
    s = s.strip().replace(" ", "").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        # whichever comes last is the decimal separator
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = head.replace(",", "") + ("." + tail if len(tail) <= 2 else tail)
    elif "." in s:
        head, _, tail = s.rpartition(".")
        if len(tail) == 3 and head:  # 1.050 -> thousands separator
            s = head.replace(".", "") + tail
        else:
            s = head.replace(".", "") + "." + tail
    try:
        return float(s)
    except ValueError:
        return None


def find_prices(text: str, require_currency: bool = True) -> list[float]:
    """All prices in a piece of text. By default only numbers next to a currency."""
    out = []
    # rejoin thousands split across HTML tags: "1. 007,25 TL" / "1 . 007,25" -> "1.007,25"
    text = re.sub(r"(?<![\d.,])(\d{1,3})\s*([.,])\s+(\d{3}(?:[.,]\d{1,2})?)\b", r"\1\2\3", text or "")
    for m in PRICE_RE.finditer(text):
        if require_currency and not (m.group("pre") or m.group("post")):
            continue
        v = parse_number(m.group("num"))
        if v is not None and v > 0:
            out.append(v)
    return out


# ---------------------------------------------------------------- names

_TR_MAP = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
                          "ç": "c", "Ç": "c", "ö": "o", "Ö": "o", "ü": "u", "Ü": "u"})
_GREEK = dict(zip("αβγδεζηθικλμνξοπρσςτυφχψω",
                  ["a", "v", "g", "d", "e", "z", "i", "th", "i", "k", "l", "m", "n", "x", "o",
                   "p", "r", "s", "s", "t", "y", "f", "ch", "ps", "o"]))


def fold(s: str) -> str:
    """Lowercase, strip accents, Turkish letters -> ASCII, Greek -> Latin."""
    s = (s or "").translate(_TR_MAP).lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(_GREEK.get(c, c) for c in s)


def tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(s).replace("&", " and "))


# ---------------------------------------------------------------- sizes

@dataclass(frozen=True)
class Size:
    unit: str        # "g", "ml" or "pc"
    each: float      # amount per item in base unit
    count: int = 1   # number of items in the pack

    @property
    def total(self) -> float:
        return self.each * self.count

    def same_as(self, other: "Size", tol: float = 0.03) -> bool:
        """Same unit, same number of items and the same amount per item."""
        if other is None or self.unit != other.unit or self.count != other.count:
            return False
        return abs(self.each - other.each) <= tol * max(self.each, other.each)

    def label(self) -> str:
        def fmt(v, u):
            if u == "g" and v >= 1000:
                return f"{v/1000:g} kg"
            if u == "ml" and v >= 1000:
                return f"{v/1000:g} L"
            return f"{v:g} {'pcs' if u == 'pc' else u}"
        base = fmt(self.each, self.unit)
        return f"{self.count} × {base}" if self.count > 1 else base


_UNITS = {
    "g": ("g", 1), "gr": ("g", 1), "grm": ("g", 1), "gram": ("g", 1), "grams": ("g", 1), "gm": ("g", 1),
    "kg": ("g", 1000), "kgr": ("g", 1000), "kilo": ("g", 1000),
    "ml": ("ml", 1), "cl": ("ml", 10), "lt": ("ml", 1000), "l": ("ml", 1000), "ltr": ("ml", 1000),
    "litre": ("ml", 1000), "liter": ("ml", 1000), "lit": ("ml", 1000),
}
_PIECES = r"(?:adet|ad|li|lu|lı|lü|pcs|pc|pieces|piece|tem|temachia|temaxia|tabs|tablets|kapsul|caps|rolls|roll|rulo|yaprak|sheets|cekim|pack)"
_Q = r"(\d+(?:[.,]\d+)?)"
_U = r"(kgr|kg|kilo|grams|gram|grm|gr|gm|g|ml|cl|ltr|litre|liter|lit|lt|l)"

_MULTI1 = re.compile(rf"\b(\d+)\s*[x×*]\s*{_Q}\s*{_U}\b")          # 8x330ml, 6 x 1.5L
_MULTI2 = re.compile(rf"\b{_Q}\s*{_U}\s*[x×*]\s*(\d+)\b")          # 330ml x8
_MULTI3 = re.compile(rf"\b(\d+)\s*(?:li|lu|'li|'lu)\s+{_Q}\s*{_U}\b")  # 4 lu 1 lt
_SINGLE = re.compile(rf"(?<![\d.,]){_Q}\s*{_U}\b")
_COUNT = re.compile(rf"\b(\d+)\s*'?\s*{_PIECES}\b")
_COUNT_X = re.compile(r"\b(?:x|×)\s*(\d+)\b|\b(\d+)\s*(?:x|×)\b")


def parse_size(name: str) -> Size | None:
    """Extract the pack size from a product name. Returns None if none found."""
    s = fold(name)
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)
    s = re.sub(r"\+\s*\d+(?:\.\d+)?\s*(?:g|gr|ml)\b\s*(?:free|bedava|hediye)?", " ", s)  # "400g+80g free" -> 400 g
    for rx, order in ((_MULTI1, "cqu"), (_MULTI2, "quc"), (_MULTI3, "cqu")):
        m = rx.search(s)
        if m:
            vals = dict(zip(order, m.groups()))
            unit, mult = _UNITS[vals["u"]]
            if rx is _MULTI3 and unit == "g" and int(vals["c"]) >= 8:
                return Size(unit, float(vals["q"]) * mult, 1)   # "16 li 200 g" = 16 pieces, 200 g in total
            return Size(unit, float(vals["q"]) * mult, int(vals["c"]))
    m = None
    for m in _SINGLE.finditer(s):
        pass  # take the last explicit size in the name
    if m:
        unit, mult = _UNITS[m.group(2)]
        q = float(m.group(1))
        if (m.group(2) == "cl" and q >= 100) or (mult == 1000 and q > 60):
            mult = 1  # typos: "1000 CL", "1400 LT", "500 KG" mean ml / g
        each = float(m.group(1)) * mult
        c = _COUNT_X.search(s)
        count = int(c.group(1) or c.group(2)) if c else 1
        if count > 48:
            count = 1
        return Size(unit, each, count)
    m = _COUNT.search(s)
    if m:
        return Size("pc", float(m.group(1)), 1)
    return None


SIZE_TOKEN_RE = re.compile(r"^\d+([.,]\d+)?(kgr|kg|grams|gram|gr|gm|g|ml|cl|ltr|lt|l|x)?$")


def size_codes(t: str) -> str:
    """Nappy / clothing sizes: "S3", "size 3", "3 numara", "no:3", "beden 3" -> "sz3"."""
    return re.sub(r"\b(?:s|size|no|numara|beden|n)\s?(\d{1,2})\b|\b(\d{1,2})\s?(?:numara|no|beden)\b",
                  lambda mm: f" sz{mm.group(1) or mm.group(2)} ", t)


def rule_text(name: str) -> str:
    """Name as ' word word ' for keyword rules (space at both ends)."""
    return " " + " ".join(size_codes(" ".join(tokens(name))).split()) + " "
