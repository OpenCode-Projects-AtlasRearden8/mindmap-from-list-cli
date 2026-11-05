# STATUS.md — mindmap-from-list

Last updated: 2026-11-05

## What was built

An offline command-line tool that turns a plain indented/Markdown list into a
printable mind map. Pure Python 3, standard library only, no network access
required for the core workflow.

Projects intentionally distinct from: `brain-dump-to-outline-cli`
(structuring unstructured notes) and `pdf-lite-tasks-cli` (task sheets).
This one takes an **already-structured outline** and produces a **visual,
printable artifact**.

### Modules (in `mindmap_from_list/`)

| File | Role |
|---|---|
| `parser.py` | Markdown/indented-list → tree. Handles `- * +` bullets, numbered lists, `#` headings (first heading = root), tabs/2-space/4-space indents, blank lines, code fences, HTML comments, and inline Markdown cleanup. `clamp_depth()` enforces the readability depth limit with clear "(+k more)" truncation markers. |
| `layout.py` | The layout math: measured text boxes (shared wrap math with the PDF renderer), the auto-balanced greedy left/right side assignment for root children, vertical subtree stacking, shared depth columns, and Bezier connector computation. Fully deterministic. |
| `metrics.py` | Approximate Helvetica AFM widths + word wrap, shared by SVG and PDF so both render identically. |
| `svg_renderer.py` | Clean vector SVG with rounded label boxes, tint fills, and S-curve connectors. |
| `pdf_renderer.py` | A tiny PDF 1.4 writer (stdlib only): Flate-compressed pages, vector paths, base-14 Helvetica text, automatic fit-to-page scaling, A4/Letter/A3 landscape sizes. |
| `palette.py` | Colorblind-safe palettes: Okabe-Ito (default), IBM, and a print-friendly monochrome fallback. `--per-branch-colors` optionally colors by top-level branch instead of depth. |
| `questions.py` | Optional study-question drafts via any OpenAI-compatible chat endpoint (local Ollama by default, LM Studio, llama.cpp, remote servers). **Off by default.** No API keys, no header auth, opt-in only. Unreachable endpoints warn and never break map generation. |
| `cli.py` | `mindmap-from-list` console entry point plus `python -m mindmap_from_list.cli`. |

## How to run it

```bash
python -m pip install .          # installs the `mindmap-from-list` command

mindmap-from-list my-notes.md                 # writes my-notes.svg
mindmap-from-list my-notes.md --pdf map.pdf   # also writes a print PDF
# options: --palette okabe-ito|ibm|mono, --paper a4|letter|a3 (+ landscape
# variants), --max-depth N, --per-branch-colors, --stdout, '-' for stdin

# Optional AI study questions (off by default; needs a reachable server):
mindmap-from-list my-notes.md --pdf map.pdf \
    --questions --endpoint http://127.0.0.1:11434/v1 --model llama3.2
```

A worked example lives in `examples/anatomy-study.md` with pre-rendered
`examples/anatomy-study.svg` and `.pdf`.

## Verification results (this machine: Python 3.13, Linux)

- `python -m pytest tests` → **79 passed**, fully offline. Coverage spans
  parsing (structure, siblings, headings, fences, escaping, clamping),
  layout math (balance side totals, center placement, no-overlap pairwise
  checks, link endpoints inside boxes, determinism, depth limits), palette
  selection, both renderers (SVG structure/escaping, PDF header/catalog/
  Flate streams/paper sizes/determinism), and CLI end-to-end runs including
  a local mock OpenAI-compatible server for the questions flow and an
  unreachable-endpoint failure-soft check.
- The Homebrew `qpdf --check` accepts the generated PDFs (no syntax or
  stream errors), and `pdftoppm` renders them to pixels correctly;
  results were inspected manually as images.
- Console script `mindmap-from-list --version` → `mindmap-from-list 0.1.0`.
- Package installs cleanly with `python -m pip install --break-system-packages -e .`
  (editable) and ran from a plain directory against the example file.

## Layout notes

- Root sits at origin; children split by greedy bin-packing so left/right
  vertical extents stay near-equal; every depth shares one column edge per
  side; a block's height is max(label box, stacked children) so nothing can
  overlap by construction; PDF page framing centers content and never
  upscales beyond 100%.

## Known gaps

- PDF text uses base-14 Helvetica with an ASCII-transliteration fallback,
  so non-Latin scripts and emojis degrade rather than render exactly.
- Links are drawn under the boxes: very deep trees (6+ levels, all visible)
  can look dense; `--max-depth 3` or `4` is recommended for readability
  (the tool defaults to 4 levels when the tree is deeper).
- Exactly equal-indent Markdown block elements (tables, block quotes) are
  treated as plain indented text, not special structures.
- The study-questions feature expects the endpoint to expose
  `/chat/completions`; Azure-style deployments that need keys are not the
  target (the tool never asks for keys by design).
- No DPI metadata hint inside the SVG (viewBox only); browsers/printers
  scale it as a document.
- Single-page PDF only; a huge un-clamped map scales down to fit one page.

## Publishing checklist for the LLC

- MIT `LICENSE` with the exact line `Copyright (c) 2026 Asdale Dynamics, LLC`.
- README credits ASDALE DYNAMICS, LLC and links the hub site.
- No secrets, keys, or personal data in any tracked file; git history starts
  clean with this repository's initial commit.
