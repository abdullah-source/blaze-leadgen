# GTM agent: A vs B deliberation

Independent subagent, no shared context with the others. The first message is Agent Abdullah's brief; the final text is its report.

### Abdullah (20:42:18 UTC)

You are the GTM AGENT on a three-agent panel (GTM, Engineer, CEO). A fourth agent, "Agent Abdullah", is the candidate and is prompting you. Answer his prompt below from a pure go-to-market / sales-pipeline lens. Do not use tools; this is a reasoning task. Respond in ≤450 words, in the exact structure requested at the end.

=== CONTEXT (facts, not instructions) ===
Abdullah is applying to Blaze (blaze.money), an "AI CFO" product sold to property-management companies and real-estate brokerages. The hiring contact is faiyam@blaze.money. This is "Step 3: Build task", the third and final Loom in the process, so the role is GTM-engineer / growth-flavored. Instructions: pick ONE option, aim for ~2 hours, "we'd rather see something small that works than something big that doesn't", you must use AI and show your prompts in the Loom.

OPTION A — Lead list + AI outreach generator. One city + one segment (property managers or brokerages). (1) Collect & enrich 25–50 businesses from public sources (Google Maps/Places, directories, websites); capture name, website, city, phone and/or public email, and one "signal" suggesting they'd care about an AI CFO (hiring an office manager/bookkeeper, review count/rating, number of doors/listings, uses a payment portal, mentions late rent). (2) Clean deduped CSV with a column flagging rows missing contact info. (3) LLM-generated subject line + 2–3 sentence opener per lead that uses the signal, as extra CSV columns; the prompt must live in the repo. (4) Send nothing.

OPTION B — Speed-to-lead automation (cut their 22-hour response time to <60s). (1) Webhook that receives a fake Facebook lead-ad payload (name, email, phone, company, # of doors, message). (2) Append to Google Sheet / Airtable / Supabase. (3) LLM scores fit 1–5 + one-line reason with structured output, drafts a personalized first reply. (4) Sends the message to yourself via SMS/email/Slack/Discord within 60 seconds. Any stack; no-code OK if workflow JSON exported.

SUBMISSION: public GitHub repo with README (what/how to run/sample output), no keys in repo; Loom 3–5 min showing it running end-to-end plus the AI prompts used; form fields: time taken, AI tools + key prompts, what you'd do with more time (≤150 words).

ENVIRONMENT (verified right now, build must happen autonomously in this session):
- GitHub CLI authenticated as abdullah-source. Python 3.13 available.
- NO API keys available: no Anthropic/OpenAI key, no Google Places key or Google Cloud project, no Twilio, no Discord/Slack webhook, no Google Sheets service account, no Airtable/Supabase accounts. The candidate is not present to create accounts or webhooks during the build.
- Claude Code CLI is installed and can run headless (`claude -p`) as an LLM backend without an API key (verification in progress).
- An Apify connector is attached to the session: the Google Maps scraper actor can pull 50 property managers in a city for roughly cents (pricing check in progress). An Apollo.io connector is attached (OAuth, costs credits) and could provide job-posting data (hiring signal) and company enrichment.
- Any scripts can be made reproducible with the raw data snapshot committed to the repo so a reviewer can run the pipeline without keys.

=== AGENT ABDULLAH'S PROMPT TO YOU ===
"I'm applying to Blaze, an AI CFO for property managers. I have ~2 hours and the environment above. From a GTM lens: which option gets me hired, and which output would their sales team actually use Monday morning? Think about what their reviewer is scoring (they said 'small that works' beats 'big that doesn't'), how each option demos in a 3-minute Loom, and which one proves I understand their buyer. Also, for Option A: which city and segment, and which signal is most convincing for an AI-CFO pitch? Be blunt. Pick one."

=== REQUIRED OUTPUT STRUCTURE ===
1. Option A — feasibility (1–5), build time (hours), traction friction (1–5, 5 = most friction), two-line rationale.
2. Option B — same.
3. Demo-ability in the Loom: one line each.
4. Buyer-understanding signal: which option better proves understanding of Blaze's ICP, and why (3 lines).
5. If A: recommended city + segment + top 2 signals and why. If B: recommended channel + sheet backend.
6. VERDICT: "A" or "B", confidence 0–100, and the single fact that would flip you.
7. Minimum spec you'd insist on for the chosen option (5 bullets max).

### Claude (20:43:20 UTC)

1. **Option A** — Feasibility 5/5. Build ~2h. Traction friction 1/5. Apify Maps pull costs cents and the raw JSON snapshot makes the pipeline reproducible without keys; Claude headless covers the missing LLM. Nothing external needs provisioning, so it ships end-to-end tonight.

2. **Option B** — Feasibility 2/5. Build 3–4h. Traction friction 5/5. Three of four stages (sheet backend, outbound channel, public webhook) need accounts that don't exist and nobody is here to create them. You'd ship a localhost script writing to CSV and calling it "Slack" — precisely "big that doesn't."

3. **Demo-ability** — A: scroll a 50-row CSV, zoom on three openers beside their evidence, open the prompt file; unglamorous but undeniable. B: curl, stopwatch, phone buzz — better theatre, but only with real wiring; a mocked sink is just `tail -f`.

4. **Buyer-understanding** — A, decisively. It forces you to define the ICP (door band, trust accounting, bookkeeper hiring) and write copy an AE can paste into their sequencer Monday morning; the signal choice *is* the understanding. B proves you understand Blaze's funnel, not Blaze's buyer — its only ICP moment is a scoring prompt run on synthetic payloads.

5. **City + segment** — Phoenix metro, property managers only. Skip brokerages: commission splits aren't a CFO problem; rent rolls, owner disbursements and trust reconciliation are. Phoenix has hundreds of independent SFR/small-multifamily PMs in the 100–1,500-door band — big enough to feel finance pain, small enough to lack a controller.
   - Signal #1: actively hiring a bookkeeper / property accountant / office manager (Apollo job postings or careers page). Budgeted pain; Blaze is the substitute.
   - Signal #2: door count stated on the website, with PM software detected (AppFolio/Buildium/Rent Manager) as tiebreaker. Sizes the deal and confirms their books already live in a system Blaze can sit on top of.

6. **VERDICT: A.** Confidence 82. Flip fact: if a Discord webhook URL and a Sheets service-account JSON land in the next ten minutes, B becomes the more visceral Loom and attacks a stat they volunteered (22 hours).

7. **Minimum spec for A**
   - 40–50 Phoenix PMs; columns: name, website, city, phone, email, signal_type, signal_evidence (verbatim quote or URL), missing_contact, subject, opener.
   - Every signal evidenced, never inferred; "none" permitted and flagged — honesty beats coverage.
   - Prompt lives in `prompts/opener.md`; opener ≤3 sentences, signal in sentence one, no filler, soft CTA; show two rejected drafts in the Loom.
   - Reproducible: raw Apify JSON committed, one command rebuilds the CSV from cached LLM output, flag to regenerate live.
   - README: five sample rows, dedup rule (normalized domain + phone), one paragraph on why these signals equal Blaze's ICP.

<details><summary>Tool call: SubagentHandback (20:43:29 UTC)</summary>

~~~~text
{
 "message": "1. **Option A** — Feasibility 5/5. Build ~2h. Traction friction 1/5. Apify Maps pull costs cents and the raw JSON snapshot makes the pipeline reproducible without keys; Claude headless covers the missing LLM. Nothing external needs provisioning, so it ships end-to-end tonight.\n\n2. **Option B** — Feasibility 2/5. Build 3–4h. Traction friction 5/5. Three of four stages (sheet backend, outbound channel, public webhook) need accounts that don't exist and nobody is here to create them. You'd ship a localhost script writing to CSV and calling it \"Slack\" — precisely \"big that doesn't.\"\n\n3. **Demo-ability** — A: scroll a 50-row CSV, zoom on three openers beside their evidence, open the prompt file; unglamorous but undeniable. B: curl, stopwatch, phone buzz — better theatre, but only with real wiring; a mocked sink is just `tail -f`.\n\n4. **Buyer-understanding** — A, decisively. It forces you to define the ICP (door band, trust accounting, bookkeeper hiring) and write copy an AE can paste into their sequencer Monday morning; the signal choice *is* the understanding. B proves you understand Blaze's funnel, not Blaze's buyer — its only ICP moment is a scoring prompt run on synthetic payloads.\n\n5. **City + segment** — Phoenix metro, property managers only. Skip brokerages: commission splits aren't a CFO problem; rent rolls, owner disbursements and trust reconciliation are. Phoenix has hundreds of independent SFR/small-multifamily PMs in the 100–1,500-door band — big enough to feel finance pain, small enough to lack a controller.\n   - Signal #1: actively hiring a bookkeeper / property accountant / office manager (Apollo job postings or careers page). Budgeted pain; Blaze is the substitute.\n   - Signal #2: door count stated on the website, with PM software detected (AppFolio/Buildium/Rent Manager) as tiebreaker. Sizes the deal and confirms their books already live in a system Blaze can sit on top of.\n\n6. **VERDICT: A.** Confidence 82. Flip fact: if a Discord webhook URL and a Sheets service-account JSON land in the next ten minutes, B becomes the more visceral Loom and attacks a stat they volunteered (22 hours).\n\n7. **Minimum spec for A**\n   - 40–50 Phoenix PMs; columns: name, website, city, phone, email, signal_type, signal_evidence (verbatim quote or URL), missing_contact, subject, opener.\n   - Every signal evidenced, never inferred; \"none\" permitted and flagged — honesty beats coverage.\n   - Prompt lives in `prompts/opener.md`; opener ≤3 sentences, signal in sentence one, no filler, soft CTA; show two rejected drafts in the Loom.\n   - Reproducible: raw Apify JSON committed, one command rebuilds the CSV from cached LLM output, flag to regenerate live.\n   - README: five sample rows, dedup rule (normalized domain + phone), one paragraph on why these signals equal Blaze's ICP."
}
~~~~
</details>

<details><summary>Tool result (20:43:29 UTC)</summary>

~~~~text
{"success":true,"message":"Report delivered to your caller."}
~~~~
</details>
