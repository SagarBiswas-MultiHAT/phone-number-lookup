# phoneint (Phone Number OSINT)

[![CI](https://img.shields.io/github/actions/workflow/status/SagarBiswas-MultiHAT/phoneint-osint-toolkit/ci.yml?branch=main)](https://github.com/SagarBiswas-MultiHAT/phoneint-osint-toolkit/actions) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![License](https://img.shields.io/github/license/SagarBiswas-MultiHAT/phoneint-osint-toolkit?cacheSeconds=1) ![Ruff](https://img.shields.io/badge/lint-ruff-101010) ![Last commit](https://img.shields.io/github/last-commit/SagarBiswas-MultiHAT/phoneint-osint-toolkit)

`phoneint` parses and enriches phone numbers offline (via `phonenumbers`) and runs optional, pluggable async reputation checks to produce an auditable risk score and report. The goal is transparent, explainable OSINT with clear inputs, visible signals, and reproducible output.

## Disclaimer (Read First)

**This tool is for lawful, ethical OSINT research only.**
Do not use it to harass, stalk, dox, or violate privacy. Always comply with applicable laws and third-party Terms of Service.

---

![](https://imgur.com/XCNwZsf.png)

---

![](https://imgur.com/uHusxTO.png)

---

## Table of Contents

- What This Tool Does
- How It Works
- Features
- Install
- Quick Start (CLI)
- GUI Usage
- Signals and Scoring
- Signal Overrides (Testing)
- Configuration
- Adapters
- Owner Intelligence
- Reports
- Example Numbers
- Troubleshooting
- Development and CI
- Docker
- License

## What This Tool Does

- Normalizes numbers to E.164 and common display formats
- Enriches with deterministic metadata (carrier when available, region, time zones, number type)
- Optionally queries public OSINT sources via adapters
- Produces explainable risk scoring and owner intelligence
- Exports JSON, CSV, and optional PDF reports
- Provides a CLI and a minimal non-blocking GUI

## How It Works

1. **Parse + Normalize**: `phonenumbers` parses the input to E.164 and standard formats.
2. **Deterministic Enrichment**: carrier, time zone, number type, and region are derived offline.
3. **Adapter Checks (Optional)**: adapters query public sources and return evidence items.
4. **Signals + Scoring**: boolean signals are derived and a risk score is computed with a breakdown.
5. **Owner Intelligence (Optional)**: evidence is converted into associations and confidence scores.
6. **Reporting**: a full JSON report is built and can be exported to CSV/PDF.

## Features

- E.164 parsing and normalization (`phonenumbers`)
- Deterministic enrichment: carrier, region, time zones, number type, ISO code
- Async adapters (`httpx`): DuckDuckGo Instant Answer, Google Custom Search, public dataset checks
- Explainable risk scoring with configurable weights (YAML/JSON)
- Owner intelligence with audit trail for PII-capable adapters
- Reports: JSON + CSV; optional PDF (extra dependency)
- Optional SQLite TTL caching
- CLI and GUI (PySide6 + qasync)

## Install

Python 3.11+ recommended.

```bash
python -m venv .venv
\.\.venv\Scripts\Activate.ps1

python -m pip install -U pip
python -m pip install -e .
```

Dev tools:

```bash
python -m pip install ".[dev]"
```

GUI:

```bash
python -m pip install ".[gui]"
```

PDF export:

```bash
python -m pip install ".[pdf]"
```

## Quick Start (CLI)

Lookup and print a human summary:

```bash
phoneint lookup +16502530000
```

Write a full JSON report:

```bash
phoneint lookup +16502530000 --report report.json --adapters duckduckgo,public
```

Print JSON to stdout:

```bash
phoneint lookup +16502530000 --json
```

Export an existing report:

```bash
phoneint report report.json --format csv --output evidence.csv
phoneint report report.json --format pdf --output report.pdf
```

If you have a national-format number without `+CC`, provide a default region:

```bash
phoneint lookup 6502530000 --region US
```

## GUI Usage

Launch:

```bash
phoneint serve-gui
```

Highlights:

- Download report: choose `json`, `csv`, or `pdf` and click Save.
- Owner Intelligence: consent checkbox gates PII-capable lookups.
- Evidence list: populated as adapters complete.
- Non-blocking: UI remains responsive during async checks.

## Signals and Scoring

`phoneint` calculates a small set of transparent, boolean signals and then computes a risk score with a breakdown. Default signals include:

- `found_in_scam_db`: true when the number is matched in the public scam dataset
- `voip`: true when libphonenumber classifies the number as VoIP
- `found_in_classifieds`: true when evidence URLs match classifieds domains
- `business_listing`: true when evidence URLs match business directory domains

Scoring weights are configurable; see Configuration below.

## Signal Overrides (Testing)

When you need deterministic tests (or you do not have access to provider-specific VoIP numbers), use signal overrides. The override file lets you force signals for specific E.164 numbers.

Default override file:

- `phoneint/data/signal_overrides.json`

Example:

```json
{
  "voip": ["+14155552671"],
  "found_in_classifieds": ["+12025550199"],
  "business_listing": ["+18005550100"]
}
```

When an override fires, a synthetic evidence item with `source: signal_override` is appended to the report so the Evidence list (CLI/GUI/CSV) records why the signal changed even if no adapter returned data.

You can also set a custom path via `PHONEINT_SIGNAL_OVERRIDES_PATH`.

## Configuration

Create a local `.env` from `.env.example` (do not commit real secrets).

Environment variables:

- `GCS_API_KEY` / `GCS_CX`: required only for the Google Custom Search adapter
- `PHONEINT_*`: HTTP, cache, logging, default region, scoring weights (JSON)
- `ENABLE_TRUECALLER` / `TRUECALLER_API_KEY`: required only for PII-capable Truecaller adapter
- `PHONEINT_SIGNAL_OVERRIDES_PATH`: path to the signal override JSON file

YAML config (recommended for score weights and non-secret defaults):

```yaml
# config.yaml
http_timeout_seconds: 12
http_rate_limit_per_host_per_second: 1
score_weights:
  found_in_scam_db: 70
  voip: 10
  found_in_classifieds: 20
  business_listing: -10
  age_of_first_mention_per_year: -2
```

Then:

```bash
phoneint lookup +16502530000 --config config.yaml
```

Or set `PHONEINT_CONFIG=config.yaml` in `.env`.

## Adapters

- `public`: checks a JSON dataset (ships with a demo list in `phoneint/data/scam_list.json`)
- `duckduckgo`: DuckDuckGo Instant Answer API (not full web search)
- `google`: Google Custom Search (requires your API key + CX)

No private-service scraping is included or encouraged.

### Google Custom Search - Costs and Free Alternatives

Setting up a Google Programmable Search Engine (the Search Engine ID / `CX`) is free. The Google Custom Search API (`GCS_API_KEY`) provides a small free quota and then is billed per request (typically per 1,000 requests). Some accounts require billing to access even the free quota.

Free alternatives:

- `duckduckgo`: requires no API key
- `public`: checks bundled/public datasets

## Owner Intelligence (Ethical Use Only)

`phoneint` includes an Owner Intelligence layer that produces evidence-based owner-related intelligence while remaining privacy-preserving by default.

What it does:

- Infers a coarse `ownership_type` (`business` | `individual` | `voip` | `unknown`) using deterministic rules
- Extracts auditable signals and associations from public evidence
- Produces an explainable confidence score with a breakdown

What it does not do:

- It does not claim to identify a private individual by default
- It does not scrape private services or bypass authentication

### PII-Capable Adapters (Gated)

PII-capable adapters (e.g., Truecaller) are disabled by default and will only run when:

1. You provide official credentials via `.env` (never commit secrets)
2. You explicitly enable the adapter in config or environment
3. You explicitly confirm lawful purpose plus explicit consent (`--enable-pii` in CLI, checkbox in GUI)
4. An audit trail is recorded in the report (`owner_audit_trail`)

Enable (example):

- `.env`: set `ENABLE_TRUECALLER=1` and `TRUECALLER_API_KEY=...`
- CLI: pass `--enable-pii` and `--legal-purpose "..."`

### CLI Examples

Public evidence only:

```bash
phoneint lookup +8801712345678 --adapters duckduckgo --output report.json
```

PII-capable (only if you have official API access and explicit consent):

```bash
ENABLE_TRUECALLER=true phoneint lookup +8801712345678 --enable-pii --legal-purpose "customer-verification" --output report.json
```

### GUI Usage

In the GUI, the Owner Intelligence panel includes a consent checkbox:
"I confirm I have lawful basis and explicit consent to query identity data..."

Default is unchecked. If checked and a PII-capable adapter is enabled, a warning modal is shown and the action is logged to the audit trail.

### Step-by-Step: If You See "PII Adapter Not Enabled"

This dialog means you tried to enable PII-capable lookups but have not configured an official adapter.

1. Close the dialog.
2. Create a local `.env` file from `.env.example`.
3. Add your official credentials:
   - `ENABLE_TRUECALLER=1`
   - `TRUECALLER_API_KEY=your_key_here`
4. Restart the GUI.
5. Check the consent checkbox and provide a lawful purpose.

If you do not have official credentials or consent, leave PII disabled. Public evidence and deterministic enrichment still work.

## Reports

- JSON: full report, includes owner intelligence and audit trail
- CSV: evidence and owner associations in a single long table
- PDF: summary pages plus legal disclaimer (requires `reportlab`)

## Example Numbers

These example numbers are reserved test ranges or fictional examples intended for documentation and testing only. Do not use them to query private services or target real individuals.

Reserved test range (NANP):

```text
+1 202-555-0100
+1 202-555-0101
+1 202-555-0147
+1 202-555-0199
```

Toll-free examples:

```text
+1 800-356-9377
+1 888-555-0000
+1 877-555-1212
```

International format examples:

```text
+44 7000 000000
+61 400 000 000
+49 151 00000000
```

If you want deterministic testing for scoring signals, use the signal overrides file described above.

## Troubleshooting

**Error: GUI dependencies not installed**

- Ensure you installed GUI extras into the active venv:

```bash
python -m pip install ".[gui]"
```

- If you still see the error, run the GUI directly to surface the real traceback:

```bash
python run_gui_direct.py
```

## Development and CI

Local checks (the same checks you would typically run in CI):

```bash
black phoneint tests
mypy phoneint
pytest
```

If you add GitHub Actions, use these commands in your workflow to keep the build green.

## Docker

```bash
docker build -t phoneint .
docker run --rm phoneint lookup +16502530000
```

## License

MIT. See `LICENSE`.
