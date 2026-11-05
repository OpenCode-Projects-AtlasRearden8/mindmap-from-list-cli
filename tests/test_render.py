"""Offline tests for palettes and both renderers."""

from __future__ import annotations

import pytest

from mindmap_from_list.layout import build_layout
from mindmap_from_list.parser import clamp_depth, parse
from mindmap_from_list.palette import PALETTES, color_for, get_palette, tint_for

SAMPLE = """\
# Study Map
## Digestion
- Mouth
    - Chewing
    - Saliva enzymes
## Absorption
- Small intestine
    - Villi and microvilli
"""


@pytest.fixture()
def layout():
    root = clamp_depth(parse(SAMPLE), 3)
    return root, build_layout(root, 3)


class TestPalettes:
    def test_known_palettes(self):
        assert set(PALETTES) >= {"okabe-ito", "ibm", "mono"}
        assert all(len(v) >= 4 for v in PALETTES.values())

    def test_default_palette_is_okabe_ito(self):
        assert get_palette(None) == PALETTES["okabe-ito"]

    def test_unknown_palette_name(self):
        with pytest.raises(ValueError):
            get_palette("fuchsia-sparkle")

    def test_colors_cycle_without_repeating_neighbour(self):
        palette = PALETTES["okabe-ito"]
        seq = [color_for(palette, d) for d in range(8)]
        for a, b in zip(seq, seq[1:]):
            assert a != b

    def test_tints_are_light(self):
        tint = tint_for("#56B4E9")
        r, g, b = (int(tint[i:i + 2], 16) for i in (1, 3, 5))
        assert min(r, g, b) > 200

    def test_mono_palette(self):
        assert get_palette("mono")[0] == "#333333"


class TestSvg:
    def test_structure_and_counts(self, layout):
        from mindmap_from_list.svg_renderer import render as render_svg
        root, lay = layout
        svg = render_svg(root, lay)
        assert svg.startswith("<svg ") and svg.rstrip().endswith("</svg>")
        assert svg.count("<rect") == len(lay.placed) + 1  # + page background
        assert svg.count("<path") == len(lay.links)
        assert 'viewBox="0 0' in svg

    def test_text_escaping(self):
        from mindmap_from_list.svg_renderer import render as render_svg
        root = clamp_depth(
            parse('- Root with <tag> "quotes" & ampersand'), 1)
        lay = build_layout(root)
        svg = render_svg(root, lay)
        assert "&lt;tag&gt;" in svg and "&quot;quotes&quot;" in svg
        assert "&amp;" in svg and "&lt;tag&gt;" in svg
        assert "&quot;quotes&quot;" in svg
        # no raw '<tag>' sneaks in as an element name
        assert "<tag>" not in svg

    def test_width_height_positive(self, layout):
        from mindmap_from_list.svg_renderer import render as render_svg
        root, lay = layout
        svg = render_svg(root, lay)
        assert 'width="' in svg and 'height="' in svg

    def test_palette_color_used(self, layout):
        from mindmap_from_list.svg_renderer import render as render_svg
        root, lay = layout
        svg = render_svg(root, lay, palette_name="mono")
        assert "#333333" in svg
        svg2 = render_svg(root, lay, palette_name="ibm")
        assert "#648FFF" in svg2

    def test_per_branch_mode(self, layout):
        from mindmap_from_list.svg_renderer import render as render_svg
        root, lay = layout
        per_depth = render_svg(root, lay, "okabe-ito", per_branch=False)
        per_branch = render_svg(root, lay, "okabe-ito", per_branch=True)
        assert per_depth != per_branch


class TestPdf:
    def test_header_and_eof(self, layout):
        from mindmap_from_list.pdf_renderer import render as render_pdf
        root, lay = layout
        data = render_pdf(root, lay)
        assert data.startswith(b"%PDF-1.4")
        assert data.rstrip().endswith(b"%%EOF")

    def test_has_flate_stream_and_catalog(self, layout):
        from mindmap_from_list.pdf_renderer import render as render_pdf
        root, lay = layout
        data = render_pdf(root, lay)
        assert b"/Filter /FlateDecode" in data
        assert b"/Type /Catalog" in data
        assert b"/BaseFont /Helvetica" in data

    def test_paper_sizes(self, layout):
        from mindmap_from_list.pdf_renderer import PAPER, render as render_pdf
        root, lay = layout
        for paper in ("a4", "letter", "a3"):
            data = render_pdf(root, lay, paper=paper)
            assert data.startswith(b"%PDF")
        with pytest.raises(ValueError):
            render_pdf(root, lay, paper="tabloid-fantasy")

    def test_deterministic_content_stream(self, layout):
        from mindmap_from_list.pdf_renderer import render as render_pdf
        root, lay = layout
        a = render_pdf(root, lay)
        b = render_pdf(root, lay)
        assert a == b  # no timestamps leak into page content
