"""Command-line interface for mindmap-from-list."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .parser import clamp_depth, parse
from .layout import build_layout
from .svg_renderer import render as render_svg
from .pdf_renderer import PAPER, render as render_pdf
from .palette import PALETTES


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="mindmap-from-list",
        description=(
            "Offline tool that turns a plain indented or Markdown list into a "
            "printable mind map (SVG + PDF). Pure Python, no network needed. "
            "AI study questions are optional, off by default, and need no keys."
        ),
    )
    ap.add_argument("input", help="input .txt/.md file ('-' reads stdin)")
    ap.add_argument("-o", "--output", metavar="FILE",
                    help="output SVG file (default: <input base>.svg)")
    ap.add_argument("--pdf", metavar="FILE",
                    help="also write a print-ready PDF to this file")
    ap.add_argument("--paper", choices=sorted(PAPER), default="a4-landscape",
                    help="PDF paper size (default: a4-landscape)")
    ap.add_argument("--palette", choices=sorted(PALETTES), default="okabe-ito",
                    help="colorblind-safe palette name (default: okabe-ito)")
    ap.add_argument("--per-branch-colors", action="store_true",
                    help="one color per top-level branch instead of by depth")
    ap.add_argument("--max-depth", type=int, metavar="N", default=0,
                    help="keep only the first N levels (0 = no limit; "
                         "default 4 when the tree is deeper)")
    ap.add_argument("--questions", action="store_true",
                    help="draft study questions per top-level branch via an "
                         "OpenAI-compatible endpoint (off by default)"
                    )
    ap.add_argument("--endpoint", default=None,
                    help="OpenAI-compatible base URL for study questions "
                         "(default: Ollama's local endpoint)")
    ap.add_argument("--model", default=None,
                    help="model name at that endpoint (default: llama3.2)")
    ap.add_argument("--stdout", action="store_true",
                    help="print the SVG to stdout instead of a file")
    ap.add_argument("--version", action="version",
                    version=f"mindmap-from-list {__version__}")
    ap.epilog = (
        "AI study questions (fully optional, off by default): pass --questions "
        "plus any OpenAI-compatible endpoint, e.g.:\n"
        "  mindmap-from-list my-list.md --pdf my-map.pdf --questions \\\n"
        "      --endpoint http://127.0.0.1:11434/v1 --model llama3.2\n"
        "Question drafts are saved next to your output as <base>.questions.txt "
        "and also printed. A running server must be reachable; nothing is sent "
        "unless you ask, and no API keys are ever required or stored."
    )
    return ap


def main(argv: list | None = None) -> int:
    ap = _build_parser()
    args = ap.parse_args(argv)

    try:
        text = _read_input(args.input)
    except OSError as exc:
        print(f"mindmap-from-list: cannot read input: {exc}", file=sys.stderr)
        return 1

    if args.max_depth < 0:
        print("mindmap-from-list: --max-depth must be 0 or a positive number",
              file=sys.stderr)
        return 1

    try:
        root = parse(text)
        max_depth = args.max_depth
        if max_depth == 0:
            max_depth = arg_max_depth(root)
        root = clamp_depth(root, max_depth)
        layout = build_layout(root, max_depth)
    except ValueError as exc:
        print(f"mindmap-from-list: {exc}", file=sys.stderr)
        return 1

    svg = render_svg(root, layout, args.palette, args.per_branch_colors)

    if args.stdout:
        sys.stdout.write(svg)
        out_path = None
    else:
        out_path = Path(args.output) if args.output else _default_out(args.input, ".svg")
        out_path.write_text(svg, encoding="utf-8")
        print(f"Wrote SVG: {out_path}")

    if args.pdf:
        try:
            pdf_bytes = render_pdf(root, layout, args.palette,
                                   args.per_branch_colors, args.paper)
        except ValueError as exc:
            print(f"mindmap-from-list: {exc}", file=sys.stderr)
            return 1
        pdf_path = Path(args.pdf)
        pdf_path.write_bytes(pdf_bytes)
        print(f"Wrote PDF: {pdf_path}")

    if args.questions:
        return _maybe_questions(args, root, out_path)
    return 0


def arg_max_depth(root) -> int:
    """Auto depth limit: show at most 4 levels for readability."""
    return min(root.max_depth(), 4) if root.max_depth() > 4 else root.max_depth()


def _read_input(src: str) -> str:
    if src == "-":
        return sys.stdin.read()
    return Path(src).read_text(encoding="utf-8")


def _default_out(input_path: str, suffix: str) -> Path:
    stem = Path(input_path).stem or "mindmap"
    return Path(f"{stem}{suffix}")


def _maybe_questions(args, root, out_path) -> int:
    """Fetch study-question drafts if the endpoint is reachable."""
    from .questions import annotate_questions, DEFAULT_ENDPOINT, DEFAULT_MODEL

    endpoint = args.endpoint or DEFAULT_ENDPOINT
    model = args.model or DEFAULT_MODEL
    print(f"Asking {model} at {endpoint} for study-question drafts...")
    try:
        data = annotate_questions(root, endpoint, model)
    except Exception as exc:  # network errors shouldn't kill the map
        print(f"mindmap-from-list: questions skipped ({exc})", file=sys.stderr)
        return 0
    if not data:
        print("No branches to build questions for.", file=sys.stderr)
        return 0

    lines = []
    for branch, questions in data.items():
        lines.append(f"# Branch: {branch}")
        for q in questions:
            lines.append(f"- {q}")
        lines.append("")
    text = "\n".join(lines)
    base = Path(out_path) if out_path else Path("mindmap")
    q_path = base.with_name(base.stem + ".questions.txt")
    q_path.write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"Wrote study questions: {q_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
