"""Export the FastAPI OpenAPI spec to a JSON file (input for the frontend orval client).

Usage::

    python -m protcellar.scripts.export_openapi [output_path]

Defaults to writing ``<repo>/frontend/openapi.json``. Sets dummy Sentinel env vars
so ``create_app()`` constructs without real auth config (the schema is route-only;
no DB or network is touched).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SENTINEL_SERVICE_KEY", "openapi-export")
os.environ.setdefault("SENTINEL_URL", "https://sentinel.example.com")
os.environ.setdefault("SENTINEL_SERVICE_NAME", "protcellar")
os.environ.setdefault("SENTINEL_IDP_AUDIENCE", "openapi-export.example.com")


def main() -> None:
    from protcellar.interface.app import app

    spec = app.openapi()
    default = Path(__file__).resolve().parents[4] / "frontend" / "openapi.json"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    out.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"wrote {out} ({len(spec.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
