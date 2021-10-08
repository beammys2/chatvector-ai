# ChatVector documentation site

Static developer documentation built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

## Prerequisites

- Python 3.11+
- Backend dependencies (for OpenAPI export): `pip install -r backend/requirements.txt`

## Build locally

From the repository root:

```bash
make docs
```

Or run the steps manually:

```bash
python3 -m venv .venv-docs
source .venv-docs/bin/activate
pip install -r backend/requirements.txt
pip install -r documentation/requirements.txt
python documentation/scripts/export_openapi.py
mkdocs serve -f documentation/mkdocs.yml
```

Open http://127.0.0.1:8000 (MkDocs dev server — not the ChatVector API).

To produce a static build:

```bash
python documentation/scripts/export_openapi.py
mkdocs build -f documentation/mkdocs.yml --strict
```

Output is written to `documentation/site/`.

## What gets generated

- `documentation/content/assets/openapi.json` — exported from `backend/main.py` at build time
- `documentation/site/` — static HTML output (ignored by git)

The exported OpenAPI file is gitignored because it is regenerated on every build.
