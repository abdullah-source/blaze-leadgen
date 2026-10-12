"""One deterministic fit rubric, used in two directions:

  - outbound: src/enrich.py scores every scraped lead (fit_score / fit_reason columns)
  - inbound:  src/score_inbound.py scores a lead-form payload the same way

Keeping it deterministic means every score is explainable in one line and identical on
every run. The LLM writes copy; it does not decide who is a good fit.
"""
from __future__ import annotations


def score_lead(*, signal_types: set[str], doors: int | None, reviews: int | None,
               has_email: bool, has_phone: bool) -> tuple[int, str]:
    score = 1
    reasons: list[str] = []

    if "hiring" in signal_types:
        score += 2
        reasons.append("hiring finance/office staff (budgeted pain)")
    if doors is not None:
        if doors >= 300:
            score += 2
            reasons.append(f"{doors} doors stated (controller-sized books, likely no controller)")
        elif doors >= 50:
            score += 1
            reasons.append(f"{doors} doors stated")
    if "finance_ops" in signal_types:
        score += 1
        reasons.append("advertises in-house accounting / owner statements (the work Blaze automates)")
    if "late_rent" in signal_types:
        score += 1
        reasons.append("talks about late rent / delinquency (collections pain)")
    if "software" in signal_types:
        score += 1
        reasons.append("runs PM accounting software Blaze can sit on top of")
    if "payment_portal" in signal_types and "software" not in signal_types:
        score += 1
        reasons.append("already collects rent online")
    if reviews is not None and reviews >= 100 and doors is None:
        score += 1
        reasons.append(f"{reviews} Google reviews (scale proxy)")
    if not has_email and not has_phone:
        score -= 1
        reasons.append("no contact info found")

    score = max(1, min(5, score))
    if not reasons:
        reasons.append("no site signals; Maps footprint only")
    return score, "; ".join(reasons)
