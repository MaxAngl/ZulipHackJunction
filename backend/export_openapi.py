"""Régénère contract/openapi.json depuis les schémas Pydantic.

Usage : uv run python -m backend.export_openapi
"""

import json
from pathlib import Path

from backend.main import app

CONTRACT_PATH = Path(__file__).resolve().parent.parent / "contract" / "openapi.json"


def main() -> None:
    CONTRACT_PATH.parent.mkdir(exist_ok=True)
    content = json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"
    CONTRACT_PATH.write_text(content, encoding="utf-8", newline="\n")
    print(f"OK -> {CONTRACT_PATH}")


if __name__ == "__main__":
    main()
