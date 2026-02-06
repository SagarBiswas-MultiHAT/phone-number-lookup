# file: CONTRIBUTING.md
# Contributing

Thanks for your interest in contributing to `phoneint`.

## Code of Conduct

This project aims to be welcoming and harassment-free. See `CODE_OF_CONDUCT.md`.

## Scope and Ethics

`phoneint` is intended for lawful, ethical OSINT research only. Contributions that:
- enable harassment, stalking, doxxing, or privacy violations
- bypass authentication or scrape private/paid services without permission
- embed or request secret keys

will not be accepted.

## Development Setup

```bash
python -m venv .venv
# activate your venv
pip install -U pip
pip install -e ".[dev]"
```

## Quality Bar

Before opening a PR:

```bash
black phoneint tests
mypy phoneint
pytest
```

## Pull Requests

- Keep PRs focused and small.
- Add tests for new behavior.
- Update docs when changing user-facing behavior.

