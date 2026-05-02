#!/usr/bin/env python3
"""Print shell-safe exports from a dotenv file."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ".env")
    if not path.exists():
        print(f"Missing {path}", file=sys.stderr)
        return 1

    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key.replace("_", "").isalnum() or key[0].isdigit():
            continue
        print(f"export {key}={shlex.quote(value)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
