"""Deterministic checks on every generated subject/opener.

This is the "how I checked the AI's output" step. Each check is a rule the prompt states;
a flagged draft is sent back to the model once with the flags as feedback, then re-checked.
Run standalone to re-audit data/leads_final.csv.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINAL_CSV = ROOT / "data" / "leads_final.csv"

BANNED = [
    "hope this finds you well", "i hope this", "love what you", "big fan", "synergy", "leverage",
    "revolutioniz", "streamline", "seamless", "quick question", "touch base", "circle back",
    "game-chang", "cutting-edge", "ai-generated", "as an ai", "i noticed that", "i came across",
]
# numbers that are fine ONLY as a meeting length ("a 15-minute look"), never elsewhere
ASK_NUMBERS = {"10", "15", "20", "30"}
ASK_CONTEXT = re.compile(r"\b(10|15|20|30)[\s-]*(?:min(?:ute)?s?)\b", re.I)
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

LEAD_FACT_FIELDS = ["business_name", "city", "state", "signal_evidence", "doors_stated", "pm_software", "google_rating", "google_reviews"]


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUM_RE.findall(text or "")}


def check(lead: dict, draft: dict) -> list[str]:
    flags: list[str] = []
    subject = (draft.get("subject") or "").strip()
    opener = (draft.get("opener") or "").strip()
    both = subject + " " + opener
    low = both.lower()

    if not subject or not opener:
        return ["empty"]
    if len(subject.split()) > 7:
        flags.append("subject_over_7_words")
    if "!" in both:
        flags.append("exclamation")
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", opener) if s.strip()]
    if not 2 <= len(sentences) <= 3:
        flags.append(f"sentences={len(sentences)}")
    words = len(opener.split())
    if words > 60:
        flags.append(f"words={words}")
    if "—" in both or "–" in both:
        flags.append("em_dash")
    if re.search(r"\[[^\]]+\]", both) or "{" in both:
        flags.append("placeholder")
    for b in BANNED:
        if b in low:
            flags.append(f"banned:{b}")

    allowed = set()
    for f in LEAD_FACT_FIELDS:
        allowed |= _numbers(str(lead.get(f, "")))
    stripped = ASK_CONTEXT.sub(" ", both)  # "15-minute" is fine; a bare "30th" is not
    for n in _numbers(stripped):
        if n not in allowed:
            flags.append(f"unsupported_number:{n}")

    st = lead.get("signal_type", "")
    if st == "maps_only" and re.search(r"appfolio|buildium|yardi|rent manager|\bdoors\b|\bunits\b|you(?:'re| are) hiring", low):
        flags.append("maps_only_overclaim")
    if st == "scale" and lead.get("doors_stated") and str(lead["doors_stated"]) not in _numbers(opener):
        flags.append("signal_not_used")
    if st == "software" and lead.get("pm_software") and not any(s in low.replace(" ", "") for s in str(lead["pm_software"]).split(",")):
        flags.append("signal_not_used")
    if st == "hiring" and not re.search(r"bookkeep|accountant|accounting|office manager|controller|hiring|hire|role|position|opening", low):
        flags.append("signal_not_used")
    if st == "late_rent" and not re.search(r"late|delinquen|evict|collect", low):
        flags.append("signal_not_used")
    if st == "payment_portal" and not re.search(r"online|portal|pay", low):
        flags.append("signal_not_used")
    return flags


def main() -> None:
    rows = list(csv.DictReader(FINAL_CSV.open()))
    counter: Counter = Counter()
    bad = 0
    for r in rows:
        flags = check(r, {"subject": r.get("subject"), "opener": r.get("opener")})
        if flags:
            bad += 1
            counter.update(f.split(":")[0] for f in flags)
            print(f"{r['lead_id']}  {r['business_name'][:35]:35s}  {', '.join(flags)}")
    print(f"\n{len(rows)} rows checked, {bad} with flags. Flag counts: {dict(counter)}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
