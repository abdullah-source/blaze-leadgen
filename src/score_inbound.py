"""Bridge to the 22-hour response problem (Option B in one file).

Scores an inbound lead-form payload (Facebook lead-ad shape: name, email, phone, company,
doors, message) with the SAME deterministic rubric used for the outbound list, so one
definition of "good fit" serves both directions. Reads a JSON file path or stdin.

  python src/score_inbound.py data/sample_inbound_lead.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from signals import extract_signals  # noqa: E402
from fit import score_lead  # noqa: E402


def score_payload(p: dict) -> dict:
    doors_raw = str(p.get("doors") or p.get("num_doors") or p.get("# of doors") or "").replace(",", "")
    doors = int(doors_raw) if doors_raw.isdigit() else None
    text = " ".join(str(p.get(k, "")) for k in ("message", "company", "notes"))
    sigs = {s.type for s in extract_signals(text, "inbound-form")}
    score, reason = score_lead(signal_types=sigs, doors=doors, reviews=None,
                               has_email=bool(p.get("email")), has_phone=bool(p.get("phone")))
    return {
        "fit_score": score,
        "reason": reason,
        "signals_in_message": sorted(sigs),
        "route": "call within 5 minutes" if score >= 4 else ("email reply within 60 seconds" if score >= 2 else "nurture sequence"),
    }


def main() -> None:
    src = Path(sys.argv[1]).read_text() if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(score_payload(json.loads(src)), indent=2))


if __name__ == "__main__":
    main()
