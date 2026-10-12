# Prompts used to build this (verbatim)

All prompting was done through Claude Code (Claude Fable 5.1 as the orchestrator; Claude
Sonnet 4.6 via `claude -p` for the per-lead generation). "Agent Abdullah" is me,
prompting in first person; the three perspective agents were spawned as independent
subagents with no shared context and answered these prompts.

---

## Round 1: decide A vs B (three agents in parallel, identical context block)

Each agent received the full task text (both options, submission requirements) and the
verified environment facts (no API keys; Claude CLI headless works; Apify Google Maps
scraper available at ~$0.004/place; must be built autonomously in ~2h). Then:

### Agent Abdullah -> GTM agent

> I'm applying to Blaze, an AI CFO for property managers. I have ~2 hours and the
> environment above. From a GTM lens: which option gets me hired, and which output would
> their sales team actually use Monday morning? Think about what their reviewer is
> scoring (they said 'small that works' beats 'big that doesn't'), how each option demos
> in a 3-minute Loom, and which one proves I understand their buyer. Also, for Option A:
> which city and segment, and which signal is most convincing for an AI-CFO pitch? Be
> blunt. Pick one.

Required output: feasibility (1–5), build time, traction friction (1–5) for each option;
demo-ability; buyer-understanding; city + segment + top 2 signals; VERDICT with
confidence and the single fact that would flip it; minimum spec.

### Agent Abdullah -> Engineer agent

> Engineer hat on. I have ~2 hours, no API keys except what's listed, and I'm not around
> to create accounts mid-build. For each option: what's the critical path, where does it
> break, what's the honest build time, and what can't be completed autonomously today?
> For Option B specifically: can step 2 (Google Sheet/Airtable/Supabase) and step 4
> (SMS/email/Slack/Discord) be done at all without me creating credentials, and what's
> the fallback that still satisfies the spec? For Option A: how do I get the 'signal'
> column reliably from websites without it being flaky, and how do I make the LLM step
> reproducible for a reviewer who clones the repo? Propose the exact tech stack and file
> layout for whichever you pick. Be blunt. Pick one.

### Agent Abdullah -> CEO agent

> CEO hat on. You're Faiyam watching my 3-minute Loom at 11pm after 30 other candidates.
> Which option makes you stop and write 'hire'? Weigh: (a) does the output create
> immediate value for Blaze, (b) does it prove judgment about their buyer, (c) does it
> prove I can ship with AI and not just prompt, (d) risk that the demo looks half-baked
> given my environment constraints. Option B attacks the pain they literally told me
> about (22 hours), but half its steps need credentials I can't create right now. Option
> A is fully buildable but is 'just a CSV'. Which risk would you rather I take? Pick one,
> and tell me what would make the winning option feel like a 10, not a 7.

**Result:** unanimous A (82 / 85 / 78). Full scores and reasoning in
[DECISION.md](DECISION.md).

---

## Round 2: build prompts

### The per-lead outreach prompt (the one the pipeline actually runs)

Lives at [`prompts/outreach.md`](../prompts/outreach.md). It is loaded verbatim by
`src/generate.py`; the lead row is appended as JSON. Nothing else is sent.

### Agent Abdullah -> Claude Code, after reading the first enrichment table

> Late rent is the primary signal on 17 of 37 leads and the evidence is tenant-screening
> text ("No recent Evictions", "Rent Collection Maintenance Accounting Eviction" service
> menus). That is noise, not pain. Drop "eviction" and "rent collection" as signals, keep
> late fee / delinquency only, and add a signal for sites that advertise the exact
> back-office work Blaze does: owner statements, AP/AR, reconciliations, monthly accounting,
> 1099s. Scrub phone numbers out of the evidence snippets so they can't leak into copy.
> Six sites 403 any plain client; try a reader proxy for the homepage, and stop caching
> failed fetches so they get retried. Re-run and show me the table again.

Result: late_rent 17 -> 2, new finance_ops 13, hiring 0 -> 1 (a careers page that says
"Staff opportunities include Accounting, Accounts Payable" had been filed under
finance_ops; the hiring pattern was widened), 9 fetch failures -> 2.

### Agent Abdullah -> Claude Code, after the 4-lead test generation

> Quality is good and the QA retry caught a 61-word opener with an em dash. Two problems
> before the full run: all four openers end with the exact same "Worth a 15-minute look?",
> and the opener for a company with three Google reviews says that is "a sign of a newer
> or tightly focused operation", which reads like a dig. Give the model three ask shapes
> to rotate, and for Maps-only leads under 50 reviews tell it not to mention the count or
> rating at all; open with the fact that they came up among Phoenix property managers on
> Google Maps instead. Then run all 37.

### The retry prompt (appended to the user message when a draft fails QA)

> Your previous draft failed these checks: `<flags>`
> Previous draft: `<json>`
> Write a new draft that passes every rule.

### Agent Abdullah -> Claude Code, after reading all 37 openers

> One opener says late fees apply "after the 30th" and I can't see "30th" in the evidence
> column. My QA whitelists 10/15/20/30 anywhere because of "15-minute look", which is a
> hole. Only allow those numbers when they are followed by "minute", add a test, and
> re-check every row.

Result: the number was real (the HOA FAQ says "after January 30th" and it was inside the
evidence snippet), so no row was flagged, but the hole is closed and tested.

### A rejected first draft and its regeneration (from `data/qa_report.md`)

> ### PHX-003
> - flags: `em_dash`
> - subject: Finance back-office for property managers
> - opener: Blue Romarin Property came up when I was looking through Phoenix-area property management companies on Google Maps. As a portfolio grows, the monthly close, owner disbursements, and trust reconciliations tend to be the first things that pile up. Blaze handles all of that automatically — happy to walk through it on a short call if helpful.
> 

> **Regenerated (v2, passed all checks):**
> - subject: Back-office finance for property managers
> - opener: Blue Romarin Property came up when I was looking through Phoenix-area property management companies on Google Maps. As a portfolio grows, the monthly close, owner disbursements, and trust reconciliations tend to be the first things that pile up. Blaze handles all of that automatically, and happy to walk through it on a short call if helpful.
