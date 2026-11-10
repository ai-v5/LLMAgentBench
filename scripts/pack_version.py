"""Show or bump a case-pack version (YYYYMMDD or YYYYMMDD-vN)."""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path


def next_version(current: str | None) -> str:
    today = date.today().strftime("%Y%m%d")
    if not current:
        return today
    match = re.fullmatch(r"(\d{8})(?:-v(\d+))?", current)
    if not match:
        raise ValueError("Current version must be YYYYMMDD or YYYYMMDD-vN")
    base, number = match.group(1), match.group(2)
    if base != today:
        return today
    return f"{today}-v{int(number or 1) + 1}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=Path("pack.json"))
    parser.add_argument("--bump", action="store_true", help="Set the next version for today")
    args = parser.parse_args()
    data = json.loads(args.pack.read_text(encoding="utf-8"))
    if args.bump:
        data["version"] = next_version(data.get("version"))
        args.pack.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pack": str(args.pack), "version": data.get("version")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
