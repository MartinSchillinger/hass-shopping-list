#!/usr/bin/env python3
"""Set custom_components/hass_shopping_list/manifest.json version."""

from __future__ import annotations

import json
import sys
from pathlib import Path

MANIFEST = Path("custom_components/hass_shopping_list/manifest.json")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} X.Y.Z", file=sys.stderr)
        return 2
    version = sys.argv[1]
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    data["version"] = version
    MANIFEST.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
