"""Render a LayoutResult into a clean, print-friendly SVG document."""

from __future__ import annotations

from .palette import get_palette, tint_for

FONT_FAMILY = "Arial, Helvetica, sans-serif"
MARGIN = 36.0
STROKE_W = {0: 2.2, 1: 1.8, 2: 1.4}


def _fmt(value: float) -> str:
    text = f"{value:.1f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render(root, layout, palette_name: str = "okabe-ito",
           per_branch: bool = False) -> str:
    """Return a full SVG document as a string."""
    colors = get_palette(palette_name)

    def color_for(depth: int, branch: int) -> str:
        if per_branch and depth >= 1 and branch >= 0:
            return colors[branch % len(colors)]
        return colors[max(depth, 0) % len(colors)]

    width = layout.width + 2 * MARGIN
    height = layout.height + 2 * MARGIN
    ox = -layout.min_x + MARGIN
    oy = -layout.min_y + MARGIN

    out: list = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{_fmt(width)}pt" height="{_fmt(height)}pt" '
        f'viewBox="0 0 {_fmt(width)} {_fmt(height)}">'
    )
    out.append("  <title>Mind map</title>")
    out.append(
        f'  <rect width="{_fmt(width)}" height="{_fmt(height)}"'
        ' fill="#FFFFFF"/>'
    )

    # --- connector curves (under the boxes) --------------------------------
    out.append('  <g id="connectors" fill="none">')
    for link in layout.links:
        (sx, sy), c1, c2, (ex, ey) = link.points
        color = color_for(link.depth, link.branch)
        sw = STROKE_W.get(link.depth, 1.2)
        out.append(
            f'    <path d="M {_fmt(sx + ox)} {_fmt(sy + oy)} '
            f'C {_fmt(c1[0] + ox)} {_fmt(c1[1] + oy)} '
            f'{_fmt(c2[0] + ox)} {_fmt(c2[1] + oy)} '
            f'{_fmt(ex + ox)} {_fmt(ey + oy)}" '
            f'stroke="{color}" stroke-width="{_fmt(sw)}"'
            ' stroke-linecap="round"/>'
        )
    out.append("  </g>")

    # --- label boxes --------------------------------------------------------
    out.append('  <g id="boxes">')
    for p in layout.placed:
        color = color_for(p.box.depth, p.branch)
        bg = tint_for(color) if p.box.depth >= 1 else "#FFFFFF"
        sw = STROKE_W.get(p.box.depth, 1.0)
        rx = 6.0 if p.box.depth <= 1 else 4.0
        out.append(
            f'    <rect x="{_fmt(p.left + ox)}" y="{_fmt(p.top + oy)}" '
            f'width="{_fmt(p.box.box_w)}" height="{_fmt(p.box.box_h)}" '
            f'rx="{_fmt(rx)}" ry="{_fmt(rx)}" fill="{bg}" '
            f'stroke="{color}" stroke-width="{_fmt(sw)}"/>'
        )
    out.append("  </g>")

    # --- label text ---------------------------------------------------------
    out.append(f'  <g id="labels" font-family="{FONT_FAMILY}" '
               'fill="#27272A" text-anchor="middle">')
    for p in layout.placed:
        n_lines = len(p.box.lines)
        line_h = p.box.font_size * 1.28
        center_y = p.y + oy
        first_baseline = center_y - (n_lines - 1) * line_h / 2.0
        first_baseline += p.box.font_size * 0.34
        for i, line in enumerate(p.box.lines):
            ty = first_baseline + i * line_h
            out.append(
                f'    <text x="{_fmt(p.x + ox)}" y="{_fmt(ty)}" '
                f'font-size="{_fmt(p.box.font_size)}">{_esc(line)}</text>'
            )
    out.append("  </g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"
