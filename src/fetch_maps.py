"""Step 1: pull property-management companies from Google Maps.

Default: load the committed snapshot (data/raw/maps_phoenix.json) so the pipeline runs
with no keys. With --live and APIFY_TOKEN set, re-run the Apify Google Maps Scraper
(compass/crawler-google-places, ~$0.004 per place on the free tier) and overwrite the
snapshot.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "raw" / "maps_phoenix.json"
API = "https://api.apify.com/v2"
ACTOR = "compass~crawler-google-places"

DEFAULT_INPUT = {
    "searchStringsArray": ["property management company", "residential property management"],
    "locationQuery": "Phoenix, Arizona, USA",
    "maxCrawledPlacesPerSearch": 40,
    "language": "en",
    "website": "withWebsite",       # we need a site to find signals on
    "skipClosedPlaces": True,
    "scrapeContacts": True,          # pulls public emails / socials from the website
    "scrapePlaceDetailPage": False,
    "maxReviews": 0,
    "maxImages": 0,
}


def run_live(token: str, actor_input: dict) -> list[dict]:
    r = requests.post(f"{API}/acts/{ACTOR}/runs", params={"token": token}, json=actor_input, timeout=30)
    r.raise_for_status()
    run = r.json()["data"]
    run_id = run["id"]
    print(f"Apify run started: {run_id}", file=sys.stderr)
    while True:
        s = requests.get(f"{API}/actor-runs/{run_id}", params={"token": token}, timeout=30).json()["data"]
        status = s["status"]
        if status in {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}:
            break
        print(f"  status={status} ...", file=sys.stderr)
        time.sleep(10)
    if status != "SUCCEEDED":
        raise SystemExit(f"Apify run ended with status {status}")
    ds = s["defaultDatasetId"]
    items = requests.get(f"{API}/datasets/{ds}/items", params={"token": token, "clean": "true", "format": "json"}, timeout=120).json()
    return items


def load_snapshot() -> list[dict]:
    with SNAPSHOT.open() as f:
        return json.load(f)


def main() -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="re-pull from Apify (needs APIFY_TOKEN)")
    ap.add_argument("--location", default=DEFAULT_INPUT["locationQuery"])
    ap.add_argument("--per-term", type=int, default=DEFAULT_INPUT["maxCrawledPlacesPerSearch"])
    args = ap.parse_args()

    if args.live:
        token = os.environ.get("APIFY_TOKEN")
        if not token:
            raise SystemExit("--live requires APIFY_TOKEN in the environment or .env")
        actor_input = {**DEFAULT_INPUT, "locationQuery": args.location, "maxCrawledPlacesPerSearch": args.per_term}
        items = run_live(token, actor_input)
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(items, indent=1))
        print(f"Saved {len(items)} places to {SNAPSHOT.relative_to(ROOT)}")
    else:
        items = load_snapshot()
        with_site = sum(1 for i in items if i.get("website"))
        with_email = sum(1 for i in items if i.get("emails"))
        print(f"Snapshot: {len(items)} places, {with_site} with website, {with_email} with a public email")


if __name__ == "__main__":
    main()
