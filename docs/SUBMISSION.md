# Submission form: draft answers

Copy-paste material for the application form. Numbers marked (final) are filled in from
the committed outputs.

## Which option did you pick?

**A (Lead list + AI outreach)**

## GitHub repo

https://github.com/abdullah-source/blaze-leadgen (public)

## Output file

`data/leads_final.csv` in the repo (37 property-management companies, Phoenix AZ, with
signal, evidence URL, fit score, subject line and opener).

## Roughly how long did the build take?

About 2.5 hours end to end: ~15 min deciding A vs B with a three-agent panel, ~1.5 h
building and iterating on the signal extractor and prompt, ~30 min on README, tests and
the repo.

## Which AI tools did you use, and what were your key prompts?

- **Claude Code (Claude Fable 5.1)** as the build agent: ran the A-vs-B deliberation as
  three independent subagents (GTM, Engineer, CEO), wrote the pipeline, ran it, reviewed
  the output and iterated.
- **Claude Sonnet 4.6 via `claude -p`** (Claude Code headless) as the per-lead copy
  generator, so the pipeline runs with no API key. The script also supports the Anthropic
  API when `ANTHROPIC_API_KEY` is set.
- **Apify Google Maps Scraper** (via the Apify connector) for the 80-place pull (~$0.50).

How I checked and improved what the AI gave me: the first signal pass was dominated by
"late rent / eviction" hits that turned out to be generic service menus and tenant-screening
text, so I removed those patterns and added a "finance_ops" signal for sites that advertise
the exact back-office work Blaze does (owner statements, AP/AR, reconciliations). On the
copy side, `src/qa.py` runs deterministic checks on every draft (numbers must exist in the
lead data, 2-3 sentences, no filler, no em dashes, signal actually used); failing drafts are
sent back once with the flags and the rejected v1 is kept in `data/qa_report.md`.

Key prompts (verbatim in `docs/PROMPTS.md`):

1. Agent Abdullah -> GTM / Engineer / CEO agents: "...From a GTM lens: which option gets
   me hired, and which output would their sales team actually use Monday morning?... Be
   blunt. Pick one." (three variants, one per lens)
2. The production prompt: `prompts/outreach.md` (system) + the lead row as JSON (user).
3. The retry prompt: "Your previous draft failed these checks: <flags>. Previous draft:
   <json>. Write a new draft that passes every rule."

## Links to AI chat transcripts

(optional: paste the Claude Code session share link here)

## What would you do with more time? (<=150 words)

Three things. First, a real hiring signal: only 1 of 37 sites exposed a finance role on a
careers page, so I would pull Indeed/LinkedIn postings (Apollo's job-postings endpoint)
for "bookkeeper", "property accountant" and "office manager" and rank those leads first,
since a budgeted hire is the strongest sign they will pay for an AI CFO. Second, door
counts for everyone: only 4 sites state them, so I would estimate from listing counts on
their rental-search pages and from AppFolio/Buildium portal URLs, with a confidence
column. Third, close the loop with Option B: the same fit rubric already scores an inbound
payload (`make inbound`); wiring it to a webhook, a Google Sheet and a Discord/SMS alert
is about an hour once credentials exist, and it would cut the 22-hour response time to
under a minute with one definition of "good fit" in both directions.
