"""Deterministic signal extraction from a company's web pages.

Pure functions, no network. `extract_signals` scans visible page text for evidence that
a property-management company would care about an AI CFO, and returns every match with
the verbatim evidence and the URL it came from. `pick_primary` chooses the one signal
that goes into the outreach prompt.

Signal types, in priority order (strongest buying signal first):
  hiring          actively hiring a bookkeeper / accountant / office manager
  scale           states a door / unit count on the site
  software        names a PM accounting system (AppFolio, Buildium, Yardi, ...)
  finance_ops     advertises the back-office finance work Blaze automates
                  (owner statements, AP/AR, reconciliations, monthly accounting)
  late_rent       talks about late fees / delinquency (collections pain)
  payment_portal  offers online rent payment or an owner / tenant portal
  maps_only       nothing found on the site; fall back to Google rating + reviews

Deliberately NOT signals: "eviction" and "rent collection" alone. Almost every PM site
lists them in a services menu or tenant-screening criteria, so they say nothing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

PRIORITY = ["hiring", "scale", "software", "finance_ops", "late_rent", "payment_portal", "maps_only"]

_FIN_ROLE = r"(?:bookkeeper|property accountant|staff accountant|accounting(?: manager| specialist| clerk| assistant)?|accounts (?:payable|receivable)|office manager|controller)"
_HIRE_WORD = r"(?:hiring|now hiring|job opening|open positions?|position available|(?:career|staff|job|employment) opportunit\w+|opportunities include|open roles?|join our team|apply (?:now|today)|we are looking for|we're looking for)"

PATTERNS: dict[str, list[re.Pattern]] = {
    "hiring": [
        re.compile(_FIN_ROLE + r".{0,80}?" + _HIRE_WORD, re.I | re.S),
        re.compile(_HIRE_WORD + r".{0,120}?" + _FIN_ROLE, re.I | re.S),
    ],
    "scale": [
        # "1,200+ doors", "over 850 units under management", "500 rental homes"
        re.compile(
            r"\b(\d{1,3}(?:,\d{3})+|\d{2,6})\s*\+?\s*"
            r"(?:doors|units|rental units|residential units|rental homes|rental properties|properties under management|homes under management|units under management|doors under management)\b",
            re.I,
        ),
    ],
    "software": [
        re.compile(r"\b(appfolio|buildium|rent ?manager|yardi|propertyware|rentvine|doorloop|tenantcloud|rentec direct)\b", re.I),
    ],
    "finance_ops": [
        re.compile(r"\b(owner (?:statements?|disbursements?|draws?)|monthly (?:accounting|financial (?:statements?|reports?|reporting))|financial reporting|accounts (?:payable|receivable)|trust account(?:s|ing)?|bank reconciliations?|reconcil(?:e|ed|ing|iation)s?|1099s?|year-end (?:statements?|tax (?:statements?|reporting))|bookkeeping)\b", re.I),
    ],
    "late_rent": [
        re.compile(r"\blate (?:fee|rent|payment)s?\b", re.I),
        re.compile(r"\bdelinquen(?:t|cy|cies)\b", re.I),
    ],
    "payment_portal": [
        re.compile(r"\bpay (?:your )?rent online\b", re.I),
        re.compile(r"\bonline (?:rent )?payments?\b", re.I),
        re.compile(r"\b(?:tenant|resident|owner) portal\b", re.I),
        re.compile(r"\bowner (?:statements?|login)\b", re.I),
    ],
}

# Numbers that look like door counts but are not (years, phone fragments, zip codes).
_SCALE_MIN, _SCALE_MAX = 20, 200_000


@dataclass
class Signal:
    type: str
    evidence: str
    source_url: str
    value: str = ""  # e.g. door count or software name

    def to_dict(self) -> dict:
        return asdict(self)


_PHONE = re.compile(r"\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _snippet(text: str, start: int, end: int, pad: int = 60) -> str:
    s = max(0, start - pad)
    e = min(len(text), end + pad)
    snip = text[s:e].strip()
    if s > 0:
        snip = "..." + snip
    if e < len(text):
        snip = snip + "..."
    snip = _PHONE.sub("[phone]", snip)      # never let a phone number leak into copy
    snip = _EMAIL.sub("[email]", snip)
    return re.sub(r"\s+", " ", snip)


def clean_text(text: str) -> str:
    """Collapse whitespace so regexes can span line breaks sensibly."""
    return re.sub(r"\s+", " ", text or "").strip()


def extract_signals(text: str, source_url: str) -> list[Signal]:
    text = clean_text(text)
    found: list[Signal] = []
    seen: set[tuple[str, str]] = set()
    for sig_type, patterns in PATTERNS.items():
        for pat in patterns:
            for m in pat.finditer(text):
                value = ""
                if sig_type == "scale":
                    n = int(m.group(1).replace(",", ""))
                    if not (_SCALE_MIN <= n <= _SCALE_MAX):
                        continue
                    value = str(n)
                elif sig_type in ("software", "finance_ops"):
                    value = m.group(1).lower().replace(" ", "") if sig_type == "software" else m.group(1).lower()
                key = (sig_type, value or m.group(0).lower())
                if key in seen:
                    continue
                seen.add(key)
                found.append(Signal(sig_type, _snippet(text, m.start(), m.end()), source_url, value))
    return found


def pick_primary(signals: list[Signal], rating: float | None, reviews: int | None, maps_url: str) -> Signal:
    """Highest-priority signal wins; otherwise fall back to Google Maps footprint."""
    for sig_type in PRIORITY:
        for s in signals:
            if s.type == sig_type:
                return s
    if not rating and not reviews:
        return Signal("maps_only", "no Google rating or reviews yet", maps_url, "")
    rating_txt = f"{rating:.1f}-star" if rating else "unrated"
    reviews_txt = f"{reviews} Google reviews" if reviews else "no Google reviews yet"
    return Signal("maps_only", f"{rating_txt} Google rating with {reviews_txt}", maps_url, "")
