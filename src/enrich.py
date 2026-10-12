"""Step 2: clean, dedupe, and enrich the raw Google Maps places into leads.

  raw snapshot -> keep property-management businesses -> dedupe (domain > phone > name)
  -> fetch homepage + a few same-domain pages (careers/about/owners/pay/...)
  -> public email (Apify contacts first, then our own scan) -> signals -> fit score
  -> data/leads_enriched.csv

Network is needed for the page fetches (about 1-2 minutes for 50 domains). Page text is
cached under data/cache/pages/ so re-runs are instant.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from signals import extract_signals, pick_primary, PRIORITY  # noqa: E402
from fit import score_lead  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "raw" / "maps_phoenix.json"
OUT_CSV = ROOT / "data" / "leads_enriched.csv"
PAGE_CACHE = ROOT / "data" / "cache" / "pages"
DROPPED_LOG = ROOT / "data" / "enrich_dropped.csv"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
TIMEOUT = 15
MAX_SUBPAGES = 5
SUBPAGE_HINT = re.compile(r"(career|job|hiring|join|about|contact|owner|portal|pay|rent|service|management|team|faq)", re.I)

# Google Maps returns a lot of noise for "property management company": apartment
# communities, brokerages, law firms, landscapers. Segment is property-management
# COMPANIES only, so keep a row when Maps' primary category says so, or the business name
# says so (e.g. "Foothills Realty & Property Management" is filed under Real estate agency).
PM_PRIMARY = re.compile(r"^property management company$", re.I)
PM_IN_NAME = re.compile(r"property (?:management|mgmt)|\bPMI\b", re.I)
NOT_PM_PRIMARY = re.compile(r"apartment|condominium|construction|attorney|landscap|roofing|security|association|office space|fire protection|tree service|gardener", re.I)

EMAIL_NOISE_DOMAINS = {"propertymanagerwebsites.com", "moatable.com", "wixpress.com", "godaddy.com", "squarespace.com", "sentry.io"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_NOISE = re.compile(r"(^u003e|\.png|\.jpg|\.jpeg|\.gif|\.svg|\.webp|example\.|sentry|wixpress|yourdomain|domain\.com|email\.com|@2x|\.js$|\.css$)", re.I)

FIELDS = [
    "lead_id", "business_name", "website", "domain", "city", "state", "phone", "email",
    "email_confidence", "missing_contact", "missing_fields", "google_rating", "google_reviews", "category",
    "signal_type", "signal_evidence", "signal_source_url", "signals_all", "doors_stated",
    "pm_software", "fit_score", "fit_reason", "pages_scanned", "fetch_status", "maps_url",
    "search_terms", "duplicates_merged",
]


def norm_domain(url: str | None) -> str:
    if not url:
        return ""
    host = urlparse(url if "://" in url else "http://" + url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def norm_phone(p: str | None) -> str:
    return re.sub(r"\D", "", p or "")


def norm_name(n: str | None) -> str:
    n = (n or "").lower()
    n = re.sub(r"\b(llc|inc|co|corp|pllc|ltd|the)\b\.?", "", n)
    return re.sub(r"[^a-z0-9]", "", n)


def is_property_business(item: dict) -> tuple[bool, str]:
    primary = item.get("categoryName") or ""
    cats = " | ".join(c for c in [primary] + list(item.get("categories") or []) if c)
    if PM_PRIMARY.search(primary):
        return True, cats
    if PM_IN_NAME.search(item.get("title") or "") and not NOT_PM_PRIMARY.search(primary):
        return True, cats or "(by name)"
    return False, cats


def dedupe(items: list[dict]) -> list[dict]:
    """Merge listings that share a website domain OR a phone number OR a normalised name."""
    leads: list[dict] = []
    index: dict[str, dict] = {}
    for it in items:
        keys = [k for k in (
            "d:" + norm_domain(it.get("website")),
            "p:" + norm_phone(it.get("phoneUnformatted") or it.get("phone")),
            "n:" + norm_name(it.get("title")),
        ) if len(k) > 2]
        hit = next((index[k] for k in keys if k in index), None)
        if hit is None:
            it["_terms"] = {it.get("searchString") or ""}
            it["_dupes"] = 0
            leads.append(it)
            hit = it
        else:
            hit["_terms"].add(it.get("searchString") or "")
            hit["_dupes"] += 1
            for f in ("emails", "city", "state", "phone", "phoneUnformatted", "totalScore", "reviewsCount"):
                if not hit.get(f) and it.get(f):
                    hit[f] = it[f]
        for k in keys:
            index.setdefault(k, hit)
    return leads


# ---------- fetching ----------
def _cache_file(domain: str) -> Path:
    return PAGE_CACHE / f"{domain}.json"


def fetch_site(website: str, domain: str) -> dict:
    """Return {'status': str, 'pages': [{'url','text','html_emails'}]} using a per-domain cache."""
    cf = _cache_file(domain)
    if cf.exists():
        return json.loads(cf.read_text())
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9"})
    pages: list[dict] = []
    status = "ok"
    try:
        r = sess.get(website, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        home_html = r.text
        pages.append(_page_record(r.url, home_html))
        soup = BeautifulSoup(home_html, "html.parser")
        links: list[str] = []
        for a in soup.find_all("a", href=True):
            href = urljoin(r.url, a["href"].strip())
            p = urlparse(href)
            if p.scheme not in ("http", "https") or norm_domain(href) != norm_domain(r.url):
                continue
            if href.rstrip("/") == r.url.rstrip("/"):
                continue
            if SUBPAGE_HINT.search(p.path) or SUBPAGE_HINT.search(a.get_text(" ")):
                clean = href.split("#")[0]
                if clean not in links:
                    links.append(clean)
        for href in links[:MAX_SUBPAGES]:
            try:
                rr = sess.get(href, timeout=TIMEOUT)
                if rr.ok and "text/html" in rr.headers.get("content-type", ""):
                    pages.append(_page_record(rr.url, rr.text))
            except requests.RequestException:
                continue
    except requests.RequestException as e:
        status = f"fetch_failed: {type(e).__name__}"
        # Bot walls (403) and odd TLS setups: try a public reader proxy for the homepage
        # only. It renders the page in a headless browser and returns plain text.
        reader = _fetch_via_reader(website)
        if reader:
            pages.append(reader)
            status = "ok_via_reader"
    rec = {"status": status, "pages": pages}
    if pages:  # cache successes only, so failed domains are retried next run
        PAGE_CACHE.mkdir(parents=True, exist_ok=True)
        cf.write_text(json.dumps(rec))
    return rec


READER = "https://r.jina.ai/"


def _fetch_via_reader(url: str) -> dict | None:
    try:
        r = requests.get(READER + url, headers={"Accept": "text/plain", "User-Agent": UA}, timeout=30)
    except requests.RequestException:
        return None
    body = r.text or ""
    if not r.ok or "Verification required" in body[:400] or "returned error 403" in body[:600] or len(body) < 300:
        return None
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", body)          # drop images
    text = re.sub(r"\]\([^)]*\)", "] ", text)                       # drop link targets
    text = re.sub(r"\s+", " ", text).strip()
    emails = [e for e in set(EMAIL_RE.findall(body)) if not EMAIL_NOISE.search(e)]
    return {"url": url, "text": text[:60000], "html_emails": emails}


def _page_record(url: str, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    text = soup.get_text(" ")
    text = re.sub(r"\s+", " ", text).strip()
    emails = [e for e in set(EMAIL_RE.findall(html)) if not EMAIL_NOISE.search(e)]
    return {"url": url, "text": text[:60000], "html_emails": emails}


def choose_email(apify_emails: list[str], page_emails: list[str], domain: str) -> str:
    cands = [e for e in (apify_emails or []) if not EMAIL_NOISE.search(e)] + page_emails
    cands = list(dict.fromkeys(e.strip().lower() for e in cands if e))
    cands = [e for e in cands if e.split("@")[-1] not in EMAIL_NOISE_DOMAINS]
    same = [e for e in cands if e.split("@")[-1].endswith(domain)] if domain else []
    pool = same or cands
    pool.sort(key=lambda e: (0 if re.match(r"^(info|contact|office|hello|admin|leasing|rentals?|management)@", e) else 1, e))
    return pool[0] if pool else ""


# ---------- main ----------
def build_lead(i: int, it: dict) -> dict:
    website = it.get("website") or ""
    domain = norm_domain(website)
    site = fetch_site(website, domain) if website else {"status": "no_website", "pages": []}
    all_sigs = []
    page_emails: list[str] = []
    for p in site["pages"]:
        all_sigs.extend(extract_signals(p["text"], p["url"]))
        page_emails.extend(p.get("html_emails", []))
    rating = it.get("totalScore")
    reviews = it.get("reviewsCount")
    primary = pick_primary(all_sigs, rating, reviews, it.get("url") or "")
    email = choose_email(it.get("emails") or [], page_emails, domain)
    phone = it.get("phone") or ""
    doors = next((int(s.value) for s in all_sigs if s.type == "scale" and s.value), None)
    software = sorted({s.value for s in all_sigs if s.type == "software"})
    sig_types = {s.type for s in all_sigs}
    fit, reason = score_lead(signal_types=sig_types, doors=doors, reviews=reviews, has_email=bool(email), has_phone=bool(phone))
    missing = [f for f, v in (("email", email), ("phone", phone)) if not v]
    return {
        "lead_id": f"PHX-{i:03d}",
        "business_name": it.get("title") or "",
        "website": website,
        "domain": domain,
        "city": it.get("city") or "",
        "state": it.get("state") or "",
        "phone": phone,
        "email": email,
        "email_confidence": ("same_domain" if email and domain and email.split("@")[-1].endswith(domain) else ("other_domain" if email else "")),
        "missing_contact": "TRUE" if (not email and not phone) else "FALSE",
        "missing_fields": ",".join(missing),
        "google_rating": rating if rating is not None else "",
        "google_reviews": reviews if reviews is not None else "",
        "category": it.get("categoryName") or "",
        "signal_type": primary.type,
        "signal_evidence": primary.evidence,
        "signal_source_url": primary.source_url,
        "signals_all": ";".join(t for t in PRIORITY if t in sig_types),
        "doors_stated": doors if doors is not None else "",
        "pm_software": ",".join(software),
        "fit_score": fit,
        "fit_reason": reason,
        "pages_scanned": len(site["pages"]),
        "fetch_status": site["status"],
        "maps_url": it.get("url") or "",
        "search_terms": ";".join(sorted(t for t in it["_terms"] if t)),
        "duplicates_merged": it["_dupes"],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0, help="cap number of leads (0 = all)")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    raw = json.loads(SNAPSHOT.read_text())
    kept, dropped = [], []
    for it in raw:
        ok, cats = is_property_business(it)
        if ok and it.get("website") and not it.get("permanentlyClosed"):
            kept.append(it)
        else:
            dropped.append({"title": it.get("title"), "categoryName": it.get("categoryName"), "categories": cats, "website": it.get("website"), "reason": "closed" if it.get("permanentlyClosed") else ("no website" if not it.get("website") else "category")})
    deduped = dedupe(kept)
    if args.limit:
        deduped = deduped[: args.limit]
    print(f"raw={len(raw)} kept_property={len(kept)} dropped={len(dropped)} after_dedupe={len(deduped)}", file=sys.stderr)

    with DROPPED_LOG.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["title", "categoryName", "categories", "website", "reason"])
        w.writeheader()
        w.writerows(dropped)

    leads: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(build_lead, i + 1, it): i for i, it in enumerate(deduped)}
        for n, fut in enumerate(as_completed(futs), 1):
            i = futs[fut]
            leads[i] = fut.result()
            print(f"  [{n}/{len(deduped)}] {leads[i]['business_name'][:40]:40s} signal={leads[i]['signal_type']:14s} fit={leads[i]['fit_score']} pages={leads[i]['pages_scanned']} {leads[i]['fetch_status']}", file=sys.stderr)

    rows = [leads[i] for i in sorted(leads)]
    with OUT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    print("\nsignal_type:", dict(Counter(r["signal_type"] for r in rows)), file=sys.stderr)
    print("fit_score:  ", dict(sorted(Counter(r["fit_score"] for r in rows).items())), file=sys.stderr)
    print("with email: ", sum(1 for r in rows if r["email"]), " missing_contact:", sum(1 for r in rows if r["missing_contact"] == "TRUE"), file=sys.stderr)
    print(f"wrote {len(rows)} leads -> {OUT_CSV.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
