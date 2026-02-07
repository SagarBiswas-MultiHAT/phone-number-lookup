# file: README.md
# phoneint (Phone Number OSINT)

`phoneint` parses and enriches phone numbers offline (via `phonenumbers`) and runs optional, pluggable async reputation checks to produce an auditable risk score and report. It is designed to be transparent, explainable, and safe-by-default.

## Disclaimer (Read First)

**This tool is for lawful, ethical OSINT research only.**
Do not use it to harass, stalk, dox, or violate privacy. Always comply with applicable laws and third-party Terms of Service.

## What This Tool Does (At a Glance)

- Normalizes numbers to E.164 and common formats
- Enriches with deterministic metadata (carrier when available, region, time zones, number type)
- Optionally queries public OSINT sources via adapters
- Produces explainable risk scoring and owner intelligence
- Exports JSON, CSV, and optional PDF reports
- Provides a CLI and a minimal non-blocking GUI

## How It Works

1. **Parse + Normalize**: `phonenumbers` parses the input to E.164 and standard formats.
2. **Deterministic Enrichment**: carrier, time zone, number type, and region are derived offline.
3. **Adapter Checks (Optional)**: adapters query public sources and return evidence items.
4. **Scoring**: risk score is calculated from explicit signals with a breakdown.
5. **Owner Intelligence (Optional)**: evidence is converted into associations and confidence scores.
6. **Reporting**: a full JSON report is built and can be exported to CSV/PDF.

## Features

- E.164 parsing + normalization (`phonenumbers`)
- Deterministic enrichment: carrier (when available), region/country name, time zones, number type, ISO code
- Async adapters (`httpx`): DuckDuckGo Instant Answer, Google Custom Search, public dataset checks
- Explainable risk scoring with configurable weights (YAML/JSON)
- Owner Intelligence with audit trail for PII-capable adapters
- Reports: JSON + CSV; optional PDF (extra dependency)
- Optional SQLite TTL caching
- CLI and GUI (PySide6 + qasync)

## Install

Python 3.11+ recommended.

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -U pip
pip install .
```

Dev tools:

```bash
pip install ".[dev]"
```

GUI:

```bash
pip install ".[gui]"
```

PDF export:

```bash
pip install ".[pdf]"
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

Launch GUI:

```bash
phoneint serve-gui
```

## GUI Highlights

- **Download report**: choose `json`, `csv`, or `pdf` and click Save.
- **Owner Intelligence**: consent checkbox gates PII-capable lookups.
- **Evidence list**: populated as adapters complete.
- **Non-blocking**: UI remains responsive during async checks.

## Example Numbers
These example numbers are reserved test ranges, fictional examples, or public-format demonstrations intended for documentation and testing only. Do not use them to query private services or to target real individuals.

### 1. Reserved Test Numbers (RFC / NANP)

These numbers are explicitly reserved for testing and documentation and are never assigned to real users.

```text
+1 202-555-0100
+1 202-555-0101
+1 202-555-0147
+1 202-555-0199
```

Expected behavior (when running in example/test mode or when marked in harnesses):

- `number_classification`: `reserved_test_number`
- `example_mode`: `true`
- `risk_score`: `0`
- No live OSINT checks performed; adapters should be mocked or skipped.

### 2. Toll-Free Number Examples

Useful for testing toll-free detection, multi-timezone handling, and business vs scam ambiguity.

```text
+1 800-356-9377
+1 888-555-0000
+1 877-555-1212
```

Expected behavior:

- `line_type`: `toll_free`
- Timezone coverage may be broad or absent depending on enrichment metadata
- Neutral or low risk in example mode unless synthetic signals are injected

### 3. Fictional Bangladesh Numbers (Example Mode)

These demonstrate country-specific parsing and carrier detection. Treat as fictional/demo data.

```text
+8801700000000
+8801800000000
+8801900000000
```

Expected behavior:

- `number_classification`: `fictional_example`
- `example_mode`: `true`
- `risk_score`: `0`
- Carrier may be mocked for demo purposes

### 4. International Fictional Examples

Useful for international formatting, country & timezone extraction, and multi-region validation.

```text
+44 7000 000000   # UK-style fictional number
+61 400 000 000   # Australia-style fictional mobile
+49 151 00000000  # Germany-style fictional mobile
```

Expected behavior:

- Correct country detection
- Valid international formatting (E.164 and international display)
- No real OSINT signals in example mode

### 5. Spam / Risk Logic Demonstration (Mocked)

These are NOT real scam numbers; use them to exercise scoring and signal detection in example/test harnesses.

```text
+1 202-555-0147   # used to simulate scam_db match in tests
+1 800-555-9999   # used to simulate classifieds exposure
```

Expected behavior (example mode only):

- Deterministic mocked signals (e.g., `found_in_scam_db: true` for the first item)
- Scoring logic exercised without querying live data

How to use in tests or demos:

- CLI: run with adapters mocked or with `--no-cache` and a local test adapter.
- GUI: use a test harness that injects `example_mode` or pre-populates adapter results.
- Always mark runs that use these numbers as `example_mode=true` in logs/reports so audits can distinguish synthetic data from live OSINT.

---



If you have a national-format number without `+CC`, provide a default region:

```bash
phoneint lookup 6502530000 --region US
```

## Sample Output (Human Summary)

```text
E.164: +88027111234
International: +880 2-7111234
National: 02-7111234
Region (ISO): BD
Country code: 880

Carrier:
Region: Dhaka
Time zones: Asia/Dhaka
Type: fixed_line
ISO country code: BD
Dialing prefix: 880

Risk score: 0/100

Breakdown:
- found_in_scam_db: 0.0 (Matched a public scam dataset)
- voip: 0.0 (libphonenumber classified the number as VOIP)
- found_in_classifieds: 0.0 (Evidence URL matched a classifieds domain heuristic)
- business_listing: -0.0 (Evidence URL matched a business listing domain heuristic)
```

## Configuration

Create a local `.env` from `.env.example` (do not commit real secrets).

Environment variables:

- `GCS_API_KEY` / `GCS_CX`: required only for the Google Custom Search adapter
- `PHONEINT_*`: HTTP, cache, logging, default region, scoring weights (JSON)
- `ENABLE_TRUECALLER` / `TRUECALLER_API_KEY`: required only for PII-capable Truecaller adapter

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

- `public`: checks a JSON dataset (ships with `phoneint/data/scam_list.json` as a demo)
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
2. You explicitly enable the adapter in config/environment
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
- CSV: evidence + owner associations + audit trail in a single long table
- PDF: summary pages plus legal disclaimer (requires `reportlab`)

## Docker

```bash
docker build -t phoneint .
docker run --rm phoneint lookup +16502530000
```

## Development

```bash
black phoneint tests
mypy phoneint
pytest
```

## License

MIT. See `LICENSE`.
