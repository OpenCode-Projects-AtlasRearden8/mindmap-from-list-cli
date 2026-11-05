"""Render a LayoutResult into a print-ready PDF, no dependencies.

A tiny PDF 1.4 writer that draws the same vector art as the SVG
renderer: rounded shapes, Bezier connectors, and Helvetica text
(base-14 font, already embedded in every PDF reader).
"""

from __future__ import annotations

import zlib
from datetime import datetime, timezone

from .metrics import text_width
from .palette import get_palette, tint_for

PAPER = {
    "a4": (595.28, 841.89),
    "letter": (612.0, 792.0),
    "a3": (841.89, 1190.55),
    "letter-landscape": (792.0, 612.0),
    "a4-landscape": (841.89, 595.28),
}

MARGIN = 24.0
LEVEL_FONT_WEIGHT = {0: 2.2, 1: 1.8, 2: 1.4}

# Characters WinAnsi can't show get plain-ASCII equivalents.
_UNICODE_ASCII = {
    "\u2013": "-", "\u2014": "--", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2026": "...",
    "\u2192": "->", "\u2190": "<-", "\u00d7": "x", "\u2022": "-",
    "\u00a0": " ", "\t": " ",
}


def _to_ascii(text: str) -> str:
    for key, val in _UNICODE_ASCII.items():
        text = text.replace(key, val)
    return text.encode("latin-1", "replace").decode("latin-1")


def _hex_to_rgb(color: str) -> tuple:
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join(c * 2 for c in color)
    return tuple(round(int(color[i:i + 2], 16) / 255.0, 4) for i in (0, 2, 4))


def _pdf_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _n(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".") if "." in f"{value:.2f}" else f"{value:.2f}"


class PDFWriter:
    """Minimal uncompressed-then-flate-compressed PDF writer."""

    def __init__(self, title: str = "Mind Map"):
        self.title = title
        self.pages: list = []          # list of (content_stream_bytes, page_w, page_h)
        self._objects: list = []
        self.created = datetime.now(timezone.utc).strftime("D:%Y%m%d%H%M%SZ")

    # -- final assembly ------------------------------------------------------
    def add_page(self, content: bytes, width: float, height: float):
        self.pages.append((content, width, height))

    def build(self) -> bytes:
        n_info = 1
        n_catalog = 2
        n_pages_obj = 3
        next_free = 4

        page_ids = []
        font_ids = []
        objects = []

        info = (
            f"<< /Title ({_pdf_escape(self.title)}) "
            f"/Producer (mindmap-from-list-cli) "
            f"/CreationDate ({self.created}) >>"
        ).encode("latin-1", "replace")
        objects.append((n_info, info))

        offsets: dict = {}
        body_start = len(b"%PDF-1.4\n%\xc7\xec\x8f\xa2\n")

        for content, w, h in self.pages:
            page_ids.append(next_free)
            font_ids.append(next_free + 1)
            next_free += 2

        # fonts: one Helvetica object per feature set is enough; use one.
        font_id = next_free
        objects.append((font_id, b"<< /Type /Font /Subtype /Type1 "
                                 b"/BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"))
        next_free += 1

        for (content, w, h), page_id in zip(self.pages, page_ids):
            compressed = zlib.compress(content)
            stream_id = next_free
            next_free += 1
            page_obj = (
                f"<< /Type /Page /Parent {n_pages_obj} 0 R "
                f"/MediaBox [0 0 {_n(w)} {_n(h)}] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
                f"/Contents {stream_id} 0 R >>"
            ).encode("latin-1", "replace")
            objects.append((page_id, page_obj))
            objects.append(
                (stream_id,
                 b"<< /Length " + str(len(compressed)).encode() +
                 b" /Filter /FlateDecode >>\nstream\n" + compressed +
                 b"\nendstream")
            )

        kids = " ".join(f"{pid} 0 R" for pid in page_ids)
        objects.append((n_pages_obj,
                        f"<< /Type /Pages /Count {len(page_ids)} "
                        f"/Kids [{kids}] >>".encode("latin-1", "replace")))
        objects.append((n_catalog,
                        f"<< /Type /Catalog /Pages {n_pages_obj} 0 R >>"
                        .encode("latin-1", "replace")))

        objects.sort(key=lambda item: item[0])

        out = bytearray()
        out += b"%PDF-1.4\n%\xc7\xec\x8f\xa2\n"
        for obj_id, payload in objects:
            offsets[obj_id] = len(out)
            out += f"{obj_id} 0 obj\n".encode() + payload + b"\nendobj\n"

        xref_pos = len(out)
        max_id = max(offsets)
        out += f"xref\n0 {max_id + 1}\n".encode()
        out += b"0000000000 65535 f \n"
        for i in range(1, max_id + 1):
            if i in offsets:
                out += f"{offsets[i]:010d} 00000 n \n".encode()
            else:
                out += b"0000000000 65535 f \n"
        out += (
            f"trailer\n<< /Size {max_id + 1} /Root {n_catalog} 0 R "
            f"/Info {n_info} 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
        ).encode("latin-1", "replace")
        return bytes(out)


def _round_rect(x0: float, y0: float, width: float, height: float,                rx: float) -> str:
    """Counter-clockwise rounded rectangle starting at bottom-left (PDF y-up)."""
    if rx > width / 2:
        rx = width / 2
    if rx > height / 2:
        rx = height / 2
    kappa = 0.5523
    k = kappa * rx
    x1, y1 = x0 + width, y0 + height
    return (
        f"{_n(x0 + rx)} {_n(y0)} m "
        f"{_n(x1 - rx)} {_n(y0)} l "
        f"{_n(x1 - rx + k)} {_n(y0)} {_n(x1)} {_n(y0 + rx - k)} {_n(x1)} {_n(y0 + rx)} c "
        f"{_n(x1)} {_n(y1 - rx)} l "
        f"{_n(x1)} {_n(y1 - rx + k)} {_n(x1 - rx + k)} {_n(y1)} {_n(x1 - rx)} {_n(y1)} c "
        f"{_n(x0 + rx)} {_n(y1)} l "
        f"{_n(x0 + rx - k)} {_n(y1)} {_n(x0)} {_n(y1 - rx + k)} {_n(x0)} {_n(y1 - rx)} c "
        f"{_n(x0)} {_n(y0 + rx)} l "
        f"{_n(x0)} {_n(y0 + rx - k)} {_n(x0 + rx - k)} {_n(y0)} {_n(x0 + rx)} {_n(y0)} c "
        "h "
    )


def page_content_stream(root, layout, palette_name: str, per_branch: bool,
                        paper: str) -> tuple:
    """Build the single print page content stream bytes."""
    colors = get_palette(palette_name)
    page_w, page_h = PAPER[paper]

    def color_for(depth, branch):
        if per_branch and depth >= 1 and branch >= 0:
            return colors[branch % len(colors)]
        return colors[max(depth, 0) % len(colors)]

    # scale to fit inside the printable area, never upscale
    usable_w = page_w - 2 * MARGIN
    usable_h = page_h - 2 * MARGIN
    scale = min(usable_w / layout.width if layout.width else 1.0,
                usable_h / layout.height if layout.height else 1.0,
                1.0)
    scale = max(scale, 0.01)
    content_w = layout.width * scale
    content_h = layout.height * scale
    ox = -layout.min_x
    oy = -layout.min_y

    def tx(v):
        return (v + ox) * scale + (page_w - content_w) / 2.0

    def ty(v):
        return page_h - ((v + oy) * scale + (page_h - content_h) / 2.0)

    ops: list = []
    ops.append("0 0 0 RG 1 w 1 J\n")

    # connectors
    ops.append("q\n")
    for link in layout.links:
        rgb = _hex_to_rgb(color_for(link.depth, link.branch))
        sw = LEVEL_FONT_WEIGHT.get(link.depth, 1.2) * max(scale, 0.35)
        ops.append(f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} RG {_n(sw)} w 1 J\n")
        (sx, sy), c1, c2, (ex, ey) = link.points
        ops.append(
            f"{_n(tx(sx))} {_n(ty(sy))} m "
            f"{_n(tx(c1[0]))} {_n(ty(c1[1]))} "
            f"{_n(tx(c2[0]))} {_n(ty(c2[1]))} "
            f"{_n(tx(ex))} {_n(ty(ey))} c S\n"
        )
    ops.append("Q\n")

    # boxes
    for p in layout.placed:
        color = color_for(p.box.depth, p.branch)
        bg = _hex_to_rgb(tint_for(color)) if p.box.depth >= 1 else (1, 1, 1)
        line = _hex_to_rgb(color)
        sw = LEVEL_FONT_WEIGHT.get(p.box.depth, 1.0) * max(scale, 0.35)
        rx = 6.0 if p.box.depth <= 1 else 4.0
        x0 = tx(p.left)
        y0 = ty(p.bottom)
        w = p.box.box_w * scale
        h = p.box.box_h * scale
        ops.append("q\n")
        ops.append(f"{bg[0]:.3f} {bg[1]:.3f} {bg[2]:.3f} rg\n")
        ops.append(_round_rect(x0, y0, w, h, rx))
        ops.append("f\n")
        ops.append(f"{line[0]:.3f} {line[1]:.3f} {line[2]:.3f} RG {_n(sw)} w\n")
        ops.append(_round_rect(x0, y0, w, h, rx))
        ops.append("S\n")
        ops.append("Q\n")

    # text (each line gets its own BT/ET block: Td is relative inside one)
    for p in layout.placed:
        n_lines = len(p.box.lines)
        line_h = p.box.font_size * 1.28
        first_baseline_y = p.y - (n_lines - 1) * line_h / 2.0
        first_baseline_y += p.box.font_size * 0.34
        for i, line in enumerate(p.box.lines):
            line = _to_ascii(line)
            baseline_y = first_baseline_y + i * line_h
            cx = tx(p.x)
            # each line gets its own BT/ET block so Td is absolute
            half_w = (text_width(line, p.box.font_size) * scale) / 2.0
            ops.append(
                f"BT 0 0 0 rg /F1 {_n(p.box.font_size * scale)} Tf "
                f"{_n(cx - half_w)} {_n(ty(baseline_y))} Td "
                f"({_pdf_escape(line)}) Tj ET\n"
            )

    return ("\n".join(ops)).encode("latin-1", "replace"), page_w, page_h


def render(root, layout, palette_name: str = "okabe-ito",
           per_branch: bool = False, paper: str = "a4") -> bytes:
    """Return PDF document bytes with one print-ready landscape page."""
    if paper not in PAPER:
        names = ", ".join(sorted(PAPER))
        raise ValueError(f"Unknown paper '{paper}'. Options: {names}")
    if paper not in ("a4-landscape", "letter-landscape"):
        paper = paper + "-landscape"
    if paper not in PAPER:
        paper = "a4-landscape"
    content, w, h = page_content_stream(
        root, layout, palette_name, per_branch, paper)
    writer = PDFWriter(title="Mind Map")
    writer.add_page(content, w, h)
    return writer.build()
