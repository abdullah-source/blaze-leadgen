# Decision record: Option A vs Option B

**Date:** 2026-10-12
**Method:** "Agent Abdullah" (the candidate, prompting in first person) briefed three
independent agents, each run as a separate Claude Code subagent with no shared
context: a **GTM agent**, an **Engineer agent**, and a **CEO agent**. Each scored both
options on feasibility, build time, and traction friction, then gave a verdict with a
confidence and a single "flip fact". The rule going in: the final decision had to be
unanimous, or a second round would run. The verbatim prompts are in
[PROMPTS.md](PROMPTS.md).

## Environment the agents were told to assume (verified before briefing)

- GitHub CLI authenticated; Python 3.13; Node 20.
- **No API keys**: no Anthropic/OpenAI key, no Google Places key, no Twilio, no
  Slack/Discord webhook, no Google Sheets service account, no Airtable/Supabase.
- Claude Code CLI available and verified to run headless (`claude -p`), so an LLM step
  can run with zero API keys.
- Apify connector attached; Google Maps scraper verified at $0.004/place (free tier),
  ~$0.50 for the whole pull.
- Build had to complete autonomously in one session, in roughly 2 hours.

## Scores

| Agent | A feasibility | A build | A friction | B feasibility | B build | B friction | Verdict | Confidence |
|---|---|---|---|---|---|---|---|---|
| GTM | 5/5 | ~2h | 1/5 | 2/5 | 3–4h | 5/5 | **A** | 82 |
| Engineer | 4/5 | ~2.5h | 2/5 | 2/5 | 1.5h code, spec incomplete | 4/5 | **A** | 85 |
| CEO | 5/5 | ~2.5h | 2/5 | 2/5 | 2h with creds, 3h+ without | 4/5 | **A** | 78 |

(Friction: 5 = most friction to land with the reviewer.)

## Why A, in each agent's words (condensed)

- **GTM:** Option A forces you to define the ICP and write copy an AE can paste into a
  sequencer Monday morning; "the signal choice *is* the understanding." Option B
  proves you understand Blaze's funnel, not Blaze's buyer. Skip brokerages: commission
  splits are not a CFO problem; rent rolls, owner disbursements and trust
  reconciliation are.
- **Engineer:** Option B's steps 2 (sheet backend) and 4 (SMS/email/Slack/Discord) are
  blocked without credentials nobody can create tonight. The honest fallback is a
  terminal print, "which is the entire point of the option, so it fails 'small that
  works'." Option A's main failure mode (website fetches failing on 30–50% of rows) is
  mitigable with a Maps-metadata fallback so the signal column is never blank.
- **CEO:** "A's failure mode is 'boring,' recoverable with judgment; B's is 'doesn't
  work,' which isn't." Narrating "imagine this hits Slack" reads as unfinished to a
  founder whose stated problem is closing loops.

## The flip fact (identical across all three)

A working outbound channel (Discord webhook URL or SMTP app password) verified
before the build. It did not exist, so the flip did not trigger.

## Final decision: **Option A, unanimous (3/3)**

### Choices adopted from the panel

- **City + segment:** Phoenix, AZ metro, property-management companies only (GTM).
- **Signals, in priority order:** hiring a bookkeeper / office manager / property
  accountant; stated door or unit count; late-rent or late-fee language; PM software
  detected (AppFolio, Buildium, Rent Manager, Yardi, Propertyware); online rent payment
  or owner/tenant portal; fallback to Google review count + rating (never blank).
- **Evidence, not inference:** every signal row carries the verbatim phrase and the URL
  it came from (GTM + CEO).
- **Rank, don't list:** a deterministic `fit_score` 1–5 with a `fit_reason` (CEO).
- **Zero-key reproducibility:** raw Apify snapshot and an LLM response cache are
  committed so `make all` rebuilds the CSV identically with no keys (Engineer).
- **QA loop on the LLM output:** automatic checks that flag openers which cite numbers
  absent from the source row, exceed 3 sentences, or use filler phrases (CEO).
- **Bridge to the 22-hour problem:** the same fit rubric is exposed as a small
  `score_inbound.py` for an inbound lead payload, as a one-paragraph pointer rather
  than a second project (CEO).
