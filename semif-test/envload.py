"""Read the repository .env, so a script holds no address of its own.

Every value already in the environment wins, so a command line override works:
  LEGION_IP=10.0.0.9 python3 judge_bench.py
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env(start: Path | None = None) -> Path | None:
    """Walk up from this file to find .env, read it, and return its path."""
    here = (start or Path(__file__)).resolve()
    for folder in [here.parent, *here.parents]:
        candidate = folder / ".env"
        if candidate.is_file():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
            return candidate
    return None


def need(name: str, hint: str = "") -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is missing. Add it to .env (see .env.example). {hint}")
    return value


load_env()
