"""Step 3: personalised subject line + 2-3 sentence opener per lead.

For each row of data/leads_enriched.csv:
  1. send prompts/outreach.md (system) + the lead facts as JSON (user) to the LLM
  2. run the deterministic checks in qa.py
  3. if anything is flagged, send the draft back once with the flags as feedback
  4. write subject / opener / qa_flags / draft_attempts columns -> data/leads_final.csv

Rejected first drafts are kept in data/qa_report.md so the v1 -> v2 improvement is visible.
Nothing is ever sent to the businesses.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import LLM, LLMError  # noqa: E402
from qa import check  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IN_CSV = ROOT / "data" / "leads_enriched.csv"
OUT_CSV = ROOT / "data" / "leads_final.csv"
PROMPT = ROOT / "prompts" / "outreach.md"
REPORT = ROOT / "data" / "qa_report.md"

LEAD_FIELDS = ["business_name", "city", "state", "category", "signal_type", "signal_evidence", "signal_source_url",
               "doors_stated", "pm_software", "google_rating", "google_reviews"]
EXTRA_COLS = ["subject", "opener", "qa_flags", "draft_attempts", "llm_backend", "llm_model", "llm_cached"]


def lead_facts(row: dict) -> dict:
    return {k: row.get(k, "") for k in LEAD_FIELDS if row.get(k, "") != ""}


def user_message(row: dict, feedback: str | None = None, previous: dict | None = None) -> str:
    msg = "Lead:\n" + json.dumps(lead_facts(row), indent=2, ensure_ascii=False)
    if feedback:
        msg += ("\n\nYour previous draft failed these checks: " + feedback +
                "\nPrevious draft: " + json.dumps(previous, ensure_ascii=False) +
                "\nWrite a new draft that passes every rule.")
    return msg


def generate_one(llm: LLM, system: str, row: dict) -> tuple[dict, list[dict]]:
    """Return (final_row_additions, rejected_drafts)."""
    rejected: list[dict] = []
    draft, meta = llm.complete_json(system, user_message(row))
    flags = check(row, draft)
    attempts = 1
    if flags:
        rejected.append({"lead_id": row["lead_id"], "attempt": 1, "flags": flags, "draft": draft})
        draft2, meta2 = llm.complete_json(system, user_message(row, ", ".join(flags), draft))
        flags2 = check(row, draft2)
        attempts = 2
        # keep whichever draft has fewer flags (prefer the retry on ties)
        if len(flags2) <= len(flags):
            draft, meta, flags = draft2, meta2, flags2
    return ({
        "subject": draft["subject"].strip(),
        "opener": " ".join(draft["opener"].split()),
        "qa_flags": ";".join(flags),
        "draft_attempts": attempts,
        "llm_backend": meta.get("backend", ""),
        "llm_model": meta.get("model", ""),
        "llm_cached": "TRUE" if meta.get("cached") else "FALSE",
    }, rejected)


def main() -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--backend", choices=["anthropic", "claude-cli", "cache"], default=None)
    args = ap.parse_args()

    rows = list(csv.DictReader(IN_CSV.open()))
    if args.limit:
        rows = rows[: args.limit]
    system = PROMPT.read_text().strip()
    llm = LLM(backend=args.backend)
    print(f"backend={llm.backend} model={llm.model if llm.backend == 'anthropic' else llm.cli_model} leads={len(rows)} cached_answers={len(llm.cache)}", file=sys.stderr)

    results: dict[int, dict] = {}
    all_rejected: list[dict] = []
    lock = threading.Lock()

    def work(i: int, row: dict) -> None:
        try:
            add, rejected = generate_one(llm, system, row)
        except LLMError as e:
            add = {"subject": "", "opener": "", "qa_flags": f"llm_error:{e}"[:200], "draft_attempts": 0, "llm_backend": llm.backend, "llm_model": "", "llm_cached": "FALSE"}
            rejected = []
        with lock:
            results[i] = {**row, **add}
            all_rejected.extend(rejected)
            print(f"  [{len(results)}/{len(rows)}] {row['business_name'][:38]:38s} flags={add['qa_flags'] or '-'} attempts={add['draft_attempts']}", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(work, i, r) for i, r in enumerate(rows)]
        for f in as_completed(futs):
            f.result()

    # best leads first: fit score desc, then original order (stable)
    out_rows = [results[i] for i in sorted(results, key=lambda i: (-int(results[i].get("fit_score") or 0), i))]
    fieldnames = list(rows[0].keys()) + [c for c in EXTRA_COLS if c not in rows[0]]
    with OUT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    flagged_final = sum(1 for r in out_rows if r["qa_flags"])
    retried = sum(1 for r in out_rows if str(r["draft_attempts"]) == "2")
    lines = [
        "# QA report: generated outreach",
        "",
        f"- leads: {len(out_rows)}",
        f"- first drafts rejected and regenerated: {retried}",
        f"- rows still flagged after retry: {flagged_final}",
        f"- LLM calls this run: {llm.calls} (cache hits: {llm.cache_hits}); cost reported by backend: ${llm.cost_usd:.2f} (the claude-cli figure is a subscription-usage estimate, not a bill)",
        "",
        "## Rejected first drafts (kept so the v1 -> v2 fix is auditable)",
        "",
    ]
    for rj in sorted(all_rejected, key=lambda r: r["lead_id"]):
        lines += [f"### {rj['lead_id']}", f"- flags: `{', '.join(rj['flags'])}`", f"- subject: {rj['draft'].get('subject')}", f"- opener: {rj['draft'].get('opener')}", ""]
    REPORT.write_text("\n".join(lines))
    print(f"\nwrote {len(out_rows)} rows -> {OUT_CSV.relative_to(ROOT)}; retried={retried}; still_flagged={flagged_final}; llm_calls={llm.calls}; cost=${llm.cost_usd:.2f}", file=sys.stderr)


if __name__ == "__main__":
    main()
