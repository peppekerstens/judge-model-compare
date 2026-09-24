"""Build `pii_cases.jsonl` from `../poc/judge_cases.jsonl`.

The judge bench labels each case with `sensitive` yes or no. A replacer needs
more: it needs the exact strings that must not reach the cloud. This script
adds that list, `must_mask`, for the 8 sensitive cases.

The list holds literal strings, so the check is exact and needs no judgement.
Run it again after a change to the case file:

    python3 pii-proxy/build-cases.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

# The literal strings that must not reach the cloud model. One list for each
# sensitive case. A case that is not in this map gets an empty list.
MUST_MASK = {
    "r1-10": ["Jan de Vries", "Kerkstraat 12", "Utrecht"],
    "r1-11": ["Tr0ub4dor&3"],
    "r1-12": ["Peppe Kerstens", "NL91ABNA0417164300"],
    "r2-01": ["192.168.2.22"],
    "r2-02": ["06-12345678"],
    "r2-05": ["Anna", "Bram", "Chantal"],
    "r2-08": ["AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"],
    "r2-11": ["asthma"],
}


def main() -> int:
    source = HERE.parent / "poc" / "judge_cases.jsonl"
    cases = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    out = []
    for case in cases:
        wanted = MUST_MASK.get(case["id"], [])
        missing = [s for s in wanted if s not in case["text"]]
        if missing:
            raise SystemExit(f"{case['id']}: these strings are not in the text: {missing}")
        if case["sensitive"] and not wanted:
            raise SystemExit(f"{case['id']} is sensitive and has no must_mask list")
        out.append({**case, "must_mask": wanted})
    target = HERE / "pii_cases.jsonl"
    target.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in out))
    print(f"{len(out)} cases written to {target}, "
          f"{sum(1 for c in out if c['must_mask'])} with a must_mask list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
