PY ?= python3

.PHONY: setup snapshot pull enrich generate qa test all clean-cache

setup:            ## create venv + install deps
	$(PY) -m venv .venv && .venv/bin/pip install -q -r requirements.txt && echo "now: source .venv/bin/activate"

snapshot:         ## show what is in the committed Google Maps snapshot
	$(PY) src/fetch_maps.py

pull:             ## re-pull Google Maps live via Apify (needs APIFY_TOKEN, ~$0.50)
	$(PY) src/fetch_maps.py --live

enrich:           ## clean, dedupe, scan websites for signals -> data/leads_enriched.csv
	$(PY) src/enrich.py

generate:         ## LLM subject + opener per lead, with QA retry -> data/leads_final.csv
	$(PY) src/generate.py

qa:               ## re-run the deterministic checks on data/leads_final.csv
	$(PY) src/qa.py

inbound:          ## demo: score a sample inbound lead with the same rubric
	$(PY) src/score_inbound.py data/sample_inbound_lead.json

test:
	$(PY) -m unittest discover -s tests -v

all: enrich generate qa

clean-cache:      ## drop page cache (LLM cache is kept on purpose; delete lines to regenerate)
	rm -rf data/cache/pages
