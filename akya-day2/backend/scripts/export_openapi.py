"""Write the OpenAPI schema to a file without starting the server.

Usage: uv run python -m scripts.export_openapi ../frontend/openapi.json
"""

import json
import sys
from pathlib import Path

from app.main import create_app


def main() -> None:
    """Dump `app.openapi()` as JSON to the path in argv[1]."""
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    out.write_text(json.dumps(create_app().openapi(), indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
