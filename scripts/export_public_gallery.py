"""Export an explicitly selected public drawing from a verified run."""

from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from pathlib import Path

from llmagentbench.contracts import ContractError, load_pack
from llmagentbench.runner import load_run
from scripts.audit_public import audit


TAGS = {"html", "head", "meta", "title", "style", "body", "main", "div", "section", "figure", "figcaption",
        "svg", "desc", "defs", "lineargradient", "radialgradient", "stop", "g", "circle", "path", "rect",
        "text", "ellipse", "line", "polyline", "polygon", "animatetransform", "animate", "use"}
REFERENCE_ATTRIBUTES = {"href", "xlink:href"}


def validate_css(value: str) -> None:
    if ("\\" in value or "/*" in value
            or re.search(r"@|javascript\s*:|data\s*:|(?:https?:)?//|(?:image-set|attr|src)\s*\(", value, re.I)):
        raise ContractError("Drawing contains an unsupported CSS reference")
    for match in re.finditer(r"url\s*\((.*?)\)", value, re.I | re.S):
        if not re.fullmatch(r"\s*['\"]?#[\w.-]+['\"]?\s*", match.group(1)):
            raise ContractError("Drawing contains an external CSS reference")


def validate_html(content: str) -> None:
    """Accept inert, self-contained drawings; display still uses a sandboxed frame."""
    if audit({"drawing.html": content.encode("utf-8")}):
        raise ContractError("Drawing did not pass the public content audit")
    # Escapes, CSS comments and at-rules can hide network-bearing CSS tokens.
    if "\\" in content or "/*" in content or re.search(r"@|javascript\s*:|data\s*:", content, re.I):
        raise ContractError("Drawing contains unsupported active content")
    class DrawingParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.seen_svg = False
            self.in_style = False

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag not in TAGS:
                raise ContractError("Drawing contains an unsupported element")
            self.seen_svg |= tag == "svg"
            self.in_style |= tag == "style"
            for name, value in attrs:
                value = value or ""
                if name.startswith("on") or name in {"src", "srcset", "http-equiv", "formaction"}:
                    raise ContractError("Drawing contains an active attribute")
                if name in REFERENCE_ATTRIBUTES and not re.fullmatch(r"#[\w.-]+", value):
                    raise ContractError("Drawing contains an external reference")
                if name in {"xmlns", "xmlns:xlink"} and value not in {
                        "http://www.w3.org/2000/svg", "http://www.w3.org/1999/xlink"}:
                    raise ContractError("Drawing contains an unsupported namespace")
                if name not in {"xmlns", "xmlns:xlink"}:
                    validate_css(value)
                if name == "attributename" and value.lower() in {"href", "xlink:href", "src", "style"}:
                    raise ContractError("Drawing can animate an active attribute")

        def handle_endtag(self, tag: str) -> None:
            if tag == "style":
                self.in_style = False

        def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            # Browsers do not self-close an HTML style element on '/>'.
            if tag == "style":
                raise ContractError("Self-closing style is unsupported")
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

        def handle_data(self, data: str) -> None:
            if self.in_style:
                validate_css(data)

    parser = DrawingParser()
    parser.feed(content)
    parser.close()
    if not parser.seen_svg:
        raise ContractError("Drawing has no SVG")


def selected_drawing(pack_path: Path, run_path: Path, model: str, effort: str) -> tuple[str, str]:
    pack, run = load_pack(pack_path), load_run(run_path)
    if (pack["manifest"]["visibility"] != "public" or pack["manifest"]["synthetic"] is not True
            or run["visibility"] != "public" or run["synthetic"] is not True
            or run["pack_sha256"] != pack["sha256"]
            or run["case_ids"] != [case["definition"]["id"] for case in pack["cases"]]):
        raise ContractError("Drawing source is not the verified public synthetic pack")
    candidates = [c for c in run["candidates"] if c["adapter"] == "codex"
                  and c["requested_model"] == model and c["reasoning_effort"] == effort]
    if len(candidates) != 1:
        raise ContractError("Drawing candidate is ambiguous")
    attempts = [a for a in run["attempts"] if a["candidate_id"] == candidates[0]["id"]
                and a["case_id"] == "crocodile-bike" and a["repeat"] == 0]
    if len(attempts) != 1 or not attempts[0]["rounds"]:
        raise ContractError("First drawing attempt is unavailable")
    if any(rnd["call"].get("evidence_level") != "MODEL_RUN" for rnd in attempts[0]["rounds"]):
        raise ContractError("Drawing must come from a model run")
    files = [f for f in attempts[0]["rounds"][-1]["call"]["response"]["files"] if f["path"] == "crocodile.html"]
    if len(files) != 1:
        raise ContractError("Drawing output is unavailable")
    content = files[0]["content"]
    validate_html(content)
    return content, attempts[0]["outcome"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pack", "run", "model", "effort", "out"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    content, outcome = selected_drawing(Path(args.pack), Path(args.run), args.model, args.effort)
    with Path(args.out).open("x", encoding="utf-8", newline="") as handle:
        handle.write(content)
    print(f"Exported verified first drawing attempt; outcome={outcome}")


if __name__ == "__main__":
    main()
