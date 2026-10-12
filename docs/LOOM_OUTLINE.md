# Loom outline (3-5 min)

0:00  Open `data/leads_final.csv` sorted by fit. Read the top three openers aloud and
      click one `signal_source_url` to show the evidence on the live site.
0:45  "Which option and why": show `docs/DECISION.md` scores table. Three agents, no
      shared context, unanimous A; the flip fact was a Discord webhook I didn't have.
1:15  Run it end to end in the terminal:
        make test  ->  make enrich  ->  make generate  ->  make qa
      Point out: zero keys, cache makes generate instant, 0 flags.
2:15  Show the AI prompts on screen: `docs/PROMPTS.md` (the three Agent Abdullah prompts),
      then `prompts/outreach.md` (the production prompt).
2:45  How I checked and improved the AI's output:
      - first signal pass: 17/37 "late rent" = noise -> show the before/after table
      - `data/qa_report.md`: 8 first drafts rejected (em dashes, Maps-only over-claims),
        show one v1 next to its v2
      - the "30th" number check story (hole found, closed, tested)
3:30  `make inbound`: same rubric scoring an inbound lead in one line; this is the bridge
      to the 22-hour problem.
3:50  Limits, said plainly: 1 hiring signal, 4 door counts, 2 sites unreachable, 14 rows
      without email. What I'd do with more time (see `docs/SUBMISSION.md`).
