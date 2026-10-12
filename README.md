# blaze-leadgen: property managers in Phoenix, AZ + AI outreach

Build task for Blaze, **Option A**. One city (Phoenix, AZ), one segment (property-management
companies). The pipeline collects businesses from Google Maps, enriches each one from its own
website, finds one *evidenced* signal that it would care about an AI CFO, scores fit, and has
an LLM write a subject line and a 2-3 sentence opener that uses that signal. Nothing is sent
to anyone.

**Output:** [`data/leads_final.csv`](data/leads_final.csv), 37 deduped leads, sorted by fit.

| | |
|---|---|
| Raw Google Maps places pulled | 80 (two search terms, Phoenix polygon) |
| Kept as property-management companies | 40 (apartment communities, brokerages, law firms, landscapers dropped; see `data/enrich_dropped.csv`) |
| After dedupe (domain, phone, or name) | **37** (3 merged: one brand with two listings, one HOA manager with two domains) |
| Websites scanned | 35 of 37 (5 via a reader proxy after a 403; 2 unreachable) |
| Public email found | 23 of 37; every row has a phone except one, so `missing_contact` is FALSE for all 37 and `missing_fields` says what is missing |
| Primary signal | 13 finance_ops, 7 maps_only, 6 payment_portal, 4 software, 4 scale, 2 late_rent, 1 hiring |
| First drafts rejected by QA and regenerated | 8 of 37 (4 em dashes, 4 over-claims on Maps-only leads); 0 rows flagged after retry |

## Sample rows

| business | signal (evidence) | fit | subject | opener |
|---|---|---|---|---|
| Ziprent | scale: "4,546 Units managed, 639 Cities served" | 5 | Owner statements for 4,546 managed units | Your site shows Ziprent managing 4,546 units across 639 cities since launching in 2019. With that many owners expecting accurate statements and timely disbursements each month, the back-office load compounds fast. Open to a 15-minute look? |
| Sentry Management | hiring: careers page, "Staff opportunities include Accounting, Accounts Payable, Accounts Receivable" | 5 | Filling accounting and AP/AR roles at Sentry | Sentry Management is currently recruiting for accounting, accounts payable, and accounts receivable staff. Blaze covers all of that work directly, so you could bypass the hire and the overhead that comes with it. Open to a 15-minute look at how it works? |
| All in the Family RE & PM | software: "chosen property management and accounting software called AppFolio Property Manager" | 3 | AppFolio without a bookkeeper behind it | Your site highlights AppFolio Property Manager as your chosen accounting platform. AppFolio tracks the numbers, but trust-account reconciliation at month-end still takes a person to run. Open to a 15-minute look at how Blaze handles that? |
| Renters Choice Homes | finance_ops: owner FAQ, "Do I get a 1099 and a yearend statement?" | 3 | Year-end owner statements without the manual work | Your FAQ explains that owners receive a 1099 and a year-end statement, so someone on your team is preparing and delivering those each January. Blaze produces owner statements and 1099s automatically, taking that cycle off your staff entirely. Open to a 15-minute look at how it works? |
| Peace Properties | maps_only: 3.2 stars, 34 reviews (site had no usable signal) | 1 | Finance back office for Phoenix property managers | Peace Properties came up when I was looking at property managers in the Phoenix area on Google Maps. Growing portfolios tend to turn owner statements and disbursements into a real drain, and that is the work Blaze takes off your plate. Open to a 15-minute look? |

Every row also carries `signal_source_url` (the page the evidence came from), `fit_reason`,
`qa_flags`, `draft_attempts`, and which LLM backend/model wrote it.

## How to run

Python 3.10+. Zero keys needed: the raw Maps snapshot and the LLM response cache are
committed, so the whole thing rebuilds offline and byte-identically.

```bash
git clone https://github.com/abdullah-source/blaze-leadgen && cd blaze-leadgen
make setup && source .venv/bin/activate
make test        # unit tests: signal extractor, fit rubric, QA checks
make snapshot    # what is in data/raw/maps_phoenix.json
make enrich      # ~20 s with the page cache, ~1 min cold (needs network for the websites)
make generate    # instant from data/cache/llm_cache.jsonl; no keys, no network
make qa          # re-audit every subject/opener against the rules
make inbound     # bonus: score a sample inbound lead-form payload with the same rubric
```

To run the LLM step live instead of from cache, do one of these and delete the lines you
want regenerated from `data/cache/llm_cache.jsonl` (or the whole file):

- `export ANTHROPIC_API_KEY=...` -> Anthropic API, model `LLM_MODEL` (default `claude-opus-5-5`), JSON-schema structured output
- or have the Claude Code CLI installed -> `claude -p` headless with tools disabled (this is how the committed output was produced, on Claude Sonnet 4.6)

To re-pull Google Maps live: `cp .env.example .env`, set `APIFY_TOKEN`, `make pull`
(Apify Google Maps Scraper, about $0.50 for 80 places including website-contact enrichment).

## How it works

```
fetch_maps.py   Apify Google Maps Scraper -> data/raw/maps_phoenix.json  (committed snapshot)
      |
enrich.py       keep PM companies -> dedupe -> fetch homepage + up to 5 same-domain pages
      |         (careers/about/owners/pay/...) -> email -> signals.py -> fit.py
      v         -> data/leads_enriched.csv
generate.py     prompts/outreach.md + lead JSON -> llm.py (API | claude -p | cache)
      |         -> qa.py checks -> one retry with the flags as feedback
      v         -> data/leads_final.csv + data/qa_report.md
```

### Signals (and why these are Blaze's ICP)

Blaze replaces the bookkeeper / office-manager / fractional-controller work inside a PM firm:
owner statements and disbursements, trust-account reconciliation, delinquency tracking, AP,
and the monthly close. So the signals are evidence that this work exists and costs them staff
today, in priority order:

1. **hiring**: a careers page naming a bookkeeper / accountant / office manager role (budgeted pain).
2. **scale**: a stated door or unit count (sizes the deal; a 600-door firm has controller-sized books and usually no controller).
3. **software**: AppFolio / Buildium / Yardi / Rent Manager named on the site (their books already live in a system Blaze sits on top of). A RentCafe-built site counts as Yardi.
4. **finance_ops**: the site advertises owner statements, AP/AR, reconciliations, monthly accounting, 1099s (they do the exact work in-house).
5. **late_rent**: late-fee / delinquency language (collections pain).
6. **payment_portal**: owner or tenant portal, online rent payment.
7. **maps_only**: nothing usable on the site, so the Google rating and review count stand in; the prompt is told to stay humble and not pretend to know their operations.

Things I deliberately do **not** count: "eviction" and "rent collection" on their own. Almost
every PM site lists them in a services menu or tenant-screening criteria, so they say nothing
(my first pass had 17 of 37 leads on that signal; they were noise).

Every signal is stored with the verbatim snippet (`signal_evidence`, phone numbers and emails
scrubbed) and the page URL (`signal_source_url`), so a rep can click and verify before sending.

### Dedupe and contact flags

- Two listings are the same lead if they share a normalised website domain, a phone number, or
  a normalised name. Merged duplicates fill each other's gaps and `duplicates_merged` counts them.
- `missing_contact` is TRUE only when a row has neither phone nor public email.
  `missing_fields` lists which of `email,phone` is empty, `email_confidence` says whether the
  email is on the company's own domain.

### Fit score

Deterministic, so every score is explainable in one line (`fit_reason`) and identical on every
run: hiring +2, 300+ doors +2 (50+ doors +1), finance_ops +1, late_rent +1, software +1
(else portal +1), 100+ reviews +1 when no door count, no contact info -1, clamped to 1-5.
The LLM writes copy; it never decides who is a good fit.

### The prompt and the QA loop

The only prompt the pipeline runs is [`prompts/outreach.md`](prompts/outreach.md) (system)
plus the lead row as JSON (user). The model must return `{"subject", "opener"}`.

`src/qa.py` then checks every draft: subject <= 7 words, opener 2-3 sentences and <= 60 words,
no exclamation marks, no em dashes, no placeholders, no filler or buzzword phrases, **every
number in the copy must appear in the lead's data** (a "15-minute look" is the only exception),
the primary signal must actually be used, and Maps-only leads must not claim software, door
counts or hiring. A failing draft is sent back once with the flags; the rejected first drafts
are kept in [`data/qa_report.md`](data/qa_report.md) so the v1 -> v2 fix is auditable.

### Bonus: the same rubric for inbound leads

`src/score_inbound.py` scores a Facebook-lead-ad style payload (name, email, phone, company,
doors, message) with the same `fit.py` rubric and the same signal extractor run over the free
text, so "good fit" means one thing in both directions. `make inbound` runs it on
`data/sample_inbound_lead.json`. That is the piece Option B would wrap in a webhook + sheet +
alert.

## Decisions, prompts, limitations

- [`docs/DECISION.md`](docs/DECISION.md): how A vs B was decided (three independent agents, unanimous).
- [`docs/PROMPTS.md`](docs/PROMPTS.md): every prompt used, verbatim.
- [`docs/SUBMISSION.md`](docs/SUBMISSION.md): the form answers.

Known limits, stated plainly: only 1 of 37 sites exposed a finance hiring signal (most small
PM firms post on Indeed, not their site); only 4 state a door count; 2 sites sit behind bot
walls that even the reader proxy could not pass; 14 rows have a phone but no public email;
Google Maps' Phoenix polygon returned a few businesses in Glendale and Scottsdale, kept and
labelled by `city`. The raw snapshot is projected to the fields the pipeline uses (no social
links or reviewer data were kept).

No API keys live in this repo. `.env.example` documents the optional ones.
