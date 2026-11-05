"""Colorblind-safe palettes (Okabe-Ito, IBM design, and greyscale)."""

from __future__ import annotations

PALETTES: dict[str, list[str]] = {
    # Okabe-Ito: the standard palette for colorblind-safe scientific figures.
    "okabe-ito": [
        "#E69F00", "#56B4E9", "#009E73", "#F0E442",
        "#0072B2", "#D55E00", "#CC79A7", "#999999",
    ],
    # IBM Design Library's colorblind-safe palette.
    "ibm": [
        "#648FFF", "#785EF0", "#DC267F", "#FE6100",
        "#FFB000", "#00A28A", "#407DFF", "#B0A8F5",
    ],
    # Monochrome fallback for photocopiers and e-ink printers.
    "mono": ["#333333", "#595959", "#737373", "#8C8C8C"],
}

_SOFT_BG = {  # very light tints used to fill branch label boxes
    "#E69F00": "#FDF3DF", "#56B4E9": "#E9F4FB", "#009E73": "#E6F4F0",
    "#F0E442": "#FCFAE4", "#0072B2": "#E6EEF6", "#D55E00": "#FBEBE2",
    "#CC79A7": "#F8EDF3", "#999999": "#F0F0F0",
    "#648FFF": "#EDF2FF", "#785EF0": "#F1EDFD", "#DC267F": "#FCE9F0",
    "#FE6100": "#FDEAE0", "#FFB000": "#FEF4E3", "#00A28A": "#E5F5F2",
    "#407DFF": "#EBF0FF", "#B0A8F5": "#F4F1FE",
    "#333333": "#EDEDED", "#595959": "#F0F0F0",
    "#737373": "#F3F3F3", "#8C8C8C": "#F6F6F6",
}


def get_palette(name: str | None) -> list[str]:
    """Return the palette hex list for ``name`` (default: Okabe-Ito)."""
    key = (name or "okabe-ito").strip().lower().replace("_", "-")
    if key not in PALETTES:
        known = ", ".join(sorted(PALETTES))
        raise ValueError(f"Unknown palette '{name}'. Known palettes: {known}")
    return PALETTES[key]


def color_for(palette: list[str], depth: int, per_branch: bool = False,
              branch_index: int = 0) -> str:
    """Pick a color for a node.

    By default, color follows depth (classic mind map shading). With
    ``per_branch``, depth-1 branches cycle through the palette and their
    descendants inherit the branch color.
    """
    if per_branch and depth > 0:
        return palette[branch_index % len(palette)]
    return palette[max(depth, 0) % len(palette)]


def tint_for(hex_color: str) -> str:
    """Very light background tint for a palette color."""
    base = hex_color.upper()
    return _SOFT_BG.get(base, "#F5F5F5")
