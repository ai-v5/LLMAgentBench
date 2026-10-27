"""Noninteractive commands usable by a person, CI, or an LLM orchestrator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .contracts import ContractError, load_config, load_pack, read_json, write_json
from .report import export_public, markdown, summarize
from .runner import load_run, run


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="llmagentbench")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate and fingerprint a case pack")
    validate.add_argument("--pack", type=Path, required=True)
    execute = commands.add_parser("run", help="Execute a frozen candidate matrix")
    execute.add_argument("--pack", type=Path, required=True)
    execute.add_argument("--config", type=Path, required=True)
    execute.add_argument("--out", type=Path, required=True)
    report = commands.add_parser("report", help="Print a private/local aggregate")
    report.add_argument("--run", type=Path, required=True)
    export = commands.add_parser("export-public", help="Export an explicitly public synthetic run")
    export.add_argument("--run", type=Path, required=True)
    export.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            pack = load_pack(args.pack)
            print(json.dumps({"valid": True, "id": pack["manifest"]["id"], "cases": len(pack["cases"]), "pack_sha256": pack["sha256"]}))
        elif args.command == "run":
            pack, config = load_pack(args.pack), load_config(args.config)
            record = run(pack, config, args.out)
            summary = summarize(record)
            write_json(args.out / "summary.json", summary)
            (args.out / "report.md").write_text(markdown(summary), encoding="utf-8")
            print(json.dumps({"run_id": record["run_id"], "state": record["state"], "attempts": len(record["attempts"])}))
        elif args.command == "report":
            print(markdown(summarize(load_run(args.run))))
        elif args.command == "export-public":
            result = export_public(load_run(args.run), args.out)
            print(json.dumps({"export_sha256": result["export_sha256"], "candidates": len(result["candidates"])}))
    except (ContractError, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"error": type(error).__name__, "status": "blocked"}))
        return 2
    return 0
