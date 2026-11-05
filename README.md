# mindmap-from-list

Turn a plain, indented list (or a Markdown outline) into a mind map you can
print. Offline, pure Python, no dependencies.

Every branch you indent one level deeper becomes a level deeper in the map.
The layout engine splits branches onto both sides, shares the load evenly
(auto-balanced), aligns every depth into tidy columns, and prints at a
readable depth limit.

Part of the ASDALE DYNAMICS, LLC collection of beginner-friendly,
local-first AI tools. Warm, plain-English, and never condescending — like a
friend explaining AI. See [dylanasdale.github.io](https://dylanasdale.github.io).

## Features

- **Plain-list parsing** — Markdown bullets (`-`, `*`, `+`), numbered lists,
  `#` headings, tabs or spaces, blank lines, code fences, and HTML comments
  are all handled. The first heading becomes the map's root.
- **Auto-balanced branch layout** — heavy subtrees are distributed left and
  right so the chart stays comfortable to read. Fully deterministic: the
  same input always produces the same map.
- **SVG and print-ready PDF** — vector output that scales cleanly on paper.
  PDF uses only the standard library (Flate-compressed streams, embedded
  Helvetica metrics) with A4/Letter/A3 landscape or portrait-ish sizes and
  automatic fit-to-page scaling.
- **Colorblind-safe palettes** — Okabe-Ito (default), the IBM colorblind-safe
  palette, and a printable monochrome fallback.
- **Max-depth limit** — keep only the first N levels for readability;
  truncated branches get a clear "(+k more)" marker.
- **Optional AI study questions** — off by default, never required. Point
  `--questions` at any OpenAI-compatible chat endpoint, including a local
  Ollama server, and it drafts two recall questions per top-level branch.
  No API keys, no accounts, no data leaving your machine unless you opt in.

## Install

Requires Python 3.9+.

```bash
python -m pip install .
```

## Usage

```bash
# SVG next to your list file
mindmap-from-list my-notes.md

# SVG plus print-ready PDF (A4 landscape is the default paper)
mindmap-from-list my-notes.md --pdf my-notes.pdf

# Pick palette, paper size, and depth limit
mindmap-from-list course-notes.md --pdf notes.pdf \
    --palette ibm --paper letter --max-depth 3

# Read from stdin
cat big-list.txt | mindmap-from-list - -o map.svg
```

Optional study questions with a **local Ollama** server:

```bash
ollama serve                # in another terminal
mindmap-from-list my-notes.md --pdf my-notes.pdf \
    --questions --model llama3.2
```

Any other OpenAI-compatible endpoint works the same way, for example
LM Studio (`http://127.0.0.1:1234/v1`) or a remote server:

```bash
mindmap-from-list my-notes.md --pdf my-notes.pdf \
    --questions --endpoint https://your-server.example/v1 --model gpt-4o-mini
```

Question drafts are saved as a plain-text `<name>.questions.txt` beside your
output and printed to the terminal. The tool sends only the short branch
titles you map, only when you ask, and never needs or stores API keys.

## Input format

Indentation defines hierarchy. Mixing the styles below is fine.

```markdown
# Course Study Plan

## Heart anatomy
- Four chambers
    - Right atrium
    - Right ventricle
- Four valves

## Blood flow
1. Pulmonary circuit
2. Systemic circuit
```

Tips:
- First `#` heading = the root; later headings = top-level branches.
- Handy for study sheets, meeting outlines, lecture notes, checklist
  breakdowns — anything you can outline.

## Why "printable"?

The PDF fits the whole map on one page, scales it to the paper, uses the
Helvetica base-14 font (no font embedding needed), and draws everything as
vector paths, so it prints crisp at any size on home printers.

## Examples

`examples/anatomy-study.md` is included. Render it with:

```bash
mindmap-from-list examples/anatomy-study.md \
    --pdf examples/anatomy-study.pdf
```

## Development

Run the offline test suite (no network access needed):

```bash
python -m pytest tests
```

Layout math details live in `mindmap_from_list/layout.py`; the PDF writer in
`mindmap_from_list/pdf_renderer.py` is a tiny PDF 1.4 implementation with
Flate compression and reuse of the same text-wrapping math as the SVG path.

## Related tools (distinct projects)

- `brain-dump-to-outline-cli` — turns freeform brain-dumps into structured outlines.
- `pdf-lite-tasks-cli` — light PDF task-sheet generation.

`mindmap-from-list` is the map/layout half of that workflow: you already
have the structure; it makes a visual artifact.

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Asdale Dynamics, LLC.
Created with care for nurses, students, small authors, and curious humans.
