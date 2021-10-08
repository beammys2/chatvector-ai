#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema for static documentation builds."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = DOCS_ROOT / "content" / "assets" / "openapi.json"

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
)
os.environ.setdefault("GEN_AI_KEY", "docs-export-key")

sys.path.insert(0, str(REPO_ROOT / "backend"))

from main import app  # noqa: E402


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
