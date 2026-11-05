"""Approximate Helvetica metrics and text wrapping (no external deps).

Widths are from the AFM file for Helvetica-Oblique/Roman (base-14 PDF
font). Using the same numbers for SVG and PDF keeps both renderers
consistent, so the SVG preview matches the printed page.
"""

from __future__ import annotations

# Helvetica AFM widths for ASCII 32..126, in 1/1000 em units.
_WIDTHS = (
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389,
    584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556,
    556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278,
    500, 667, 556, 833, 722, 778, 667, 778, 722, 667,
    611, 722, 667, 944, 667, 667, 611, 278, 278, 278,
    469, 556, 333, 556, 556, 500, 556, 556, 556, 556,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 500,
    556, 556, 556, 556, 556, 556, 500, 556, 556, 556,
    333, 500, 278, 556,
)


def text_width(text: str, font_size: float) -> float:
    """Width of ``text`` in points at ``font_size`` (Arial/Helvetica)."""
    total = 0.0
    for ch in text:
        code = ord(ch)
        if 32 <= code <= 126:
            total += _WIDTHS[code - 32]
        elif ch in "\u2013\u2014":
            total += 1000  # en/em dash
        elif code > 126:
            total += 556  # treat other characters as average width
    return total * font_size / 1000.0


def wrap(text: str, max_width: float, font_size: float) -> list[str]:
    """Greedy word-wrap so each line fits ``max_width`` points."""
    max_width = max(max_width, text_width("MM", font_size))
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if text_width(candidate, font_size) <= max_width or not current:
            current = candidate
            while text_width(current, font_size) > max_width and \
                    len(current) > 1:
                # Very long single word: hard-break it.
                cut = len(current) - 1
                while cut > 1 and text_width(current[:cut], font_size) > max_width:
                    cut -= 1
                lines.append(current[:cut])
                current = current[cut:]
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines
