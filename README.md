# file: README.md
# phoneint (Phone Number OSINT)

This tool parses and enriches phone numbers (offline via `phonenumbers`) and can run **pluggable, async** reputation checks (optional) to produce an **auditable** risk score and report.

## Disclaimer (Read First)

**This tool is for lawful, ethical OSINT research only.**  
Do not use it to harass, stalk, dox, or violate privacy. Always comply with applicable laws and third-party Terms of Service.

## Features

- E.164 parsing + normalization (`phonenumbers`)
- Deterministic enrichment: carrier (if available), country/region, time zones, number type, ISO code
- Async adapters (`httpx`): DuckDuckGo Instant Answer (ToS-friendly), Google Custom Search (requires your key), public dataset checks
- Explainable risk scoring with configurable weights (YAML)
- Reports: JSON + CSV; optional PDF (extra dependency)
- Optional SQLite TTL caching for adapter calls
- CLI and minimal non-blocking GUI skeleton (PySide6 + qasync, optional)

## Install

Python 3.11+ recommended.

```bash
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

## Example Numbers (Format Examples)

These are example formats. Validate legality and intent before using any real numbers.

- USA: `phoneint lookup +12015550123`
- UK: `phoneint lookup +441212345678`
- Bangladesh: `phoneint lookup +88027111234`
- India: `phoneint lookup +917410410123`

If you have a national-format number without `+CC`, provide a default region:

```bash
phoneint lookup 6502530000 --region US
```

## Configuration

Create a local `.env` from `.env.example` (do not commit real secrets).

Environment variables:

- `GCS_API_KEY` / `GCS_CX`: required only for the Google Custom Search adapter
- `PHONEINT_*`: HTTP, cache, logging, default region, scoring weights (JSON)

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

### Google Custom Search — costs & free alternatives

Setting up a Google Programmable Search Engine (the Search Engine ID / `CX`) is free — you get a CX at no cost. The Google Custom Search API (the API key used by this tool, `GCS_API_KEY`) is not completely free: Google provides a small free quota (varies by account/region) but after that the API is billed per-requests (typically per 1,000 requests). In some cases you may need to enable billing in Google Cloud to activate the API key even to access the free quota.

In short: you can get started for free, but heavy or programmatic use may incur small charges.

If you prefer fully free options, consider these alternatives:

- `duckduckgo`: uses DuckDuckGo Instant Answer and requires no API key.
- `public`: checks bundled/public datasets (ships with `phoneint/data/scam_list.json`) and is free to use.

Quick recap:

- **CX (Search Engine ID)**: Free ✅
- **Custom Search API key usage**: Free tier then paid ⚠️
- **Free alternatives**: DuckDuckGo adapter, public datasets ✅

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

