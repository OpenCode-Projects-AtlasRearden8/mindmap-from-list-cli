"""Offline tests for the auto-balanced layout math."""

from __future__ import annotations

import pytest

from mindmap_from_list.layout import (
    V_GAP, balance_sides, build_layout, font_size_for, measure,
    subtree_height,
)
from mindmap_from_list.parser import clamp_depth, parse


def make_root(markdown: str, max_depth: int = 99):
    return clamp_depth(parse(markdown), max_depth)


def overlaps(a, b):
    return (a.left < b.right and b.left < a.right
            and a.top < b.bottom and b.top < a.bottom)


class TestBalanceSides:
    def test_even_split(self):
        right, left = balance_sides([10, 10, 10, 10])
        assert right == [0, 3] and left == [1, 2]

    def test_one_heavy_item_goes_right_first(self):
        right, left = balance_sides([100, 1, 1, 1, 1])
        assert 0 in right and len(right) == 1
        assert sorted(left) == [1, 2, 3, 4]

    def test_higher_weight_heavier_side(self):
        right, left = balance_sides([50, 10])
        totals = (sum(weights) for weights in ([50], [10]))
        assert 0 in right  # heaviest first
        r = sum(w for i, w in enumerate([50, 10]) if i in right)
        l = sum(w for i, w in enumerate([50, 10]) if i in left)
        assert abs(r - l) <= 50

    def test_totals_close_for_many_items(self):
        weights = [7, 3, 9, 2, 5, 8, 1, 6]
        right, left = balance_sides(weights)
        r = sum(weights[i] for i in right)
        l = sum(weights[i] for i in left)
        assert abs(r - l) <= max(weights)

    def test_empty(self):
        assert balance_sides([]) == ([], [])


class TestLayoutBasics:
    def test_every_node_is_placed(self):
        root = make_root("# T\n## A\n- a1\n- a2\n## B\n- b1\n- b2")
        layout = build_layout(root)
        assert len(layout.placed) == root.count()

    def test_root_is_at_center(self):
        root = make_root("- A\n- B\n- C")
        layout = build_layout(root)
        root_p = layout.placed[0]
        assert root_p.side == 0
        assert root_p.x == 0.0 and root_p.y == 0.0

    def test_links_reference_placed_boxes(self):
        root = make_root("# T\n## A\n- a1\n## B\n- b1")
        layout = build_layout(root)
        boxes = [(p.left, p.right, p.top, p.bottom) for p in layout.placed]

        def inside(point):
            x, y = point
            return any(l <= x <= r and t <= y <= b for l, r, t, b in boxes)

        for link in layout.links:
            assert inside(link.points[0]), "link starts outside every box"
            assert inside(link.points[3]), "link ends outside every box"

    def test_deterministic_layout(self):
        md = "\n".join(f"- Topic {i}\n    - Detail {i} alpha\n    - Detail {i} beta"
                       for i in range(5))
        root = make_root(md)
        a = build_layout(root)
        b = build_layout(root)
        assert [(p.x, p.y) for p in a.placed] == [(p.x, p.y) for p in b.placed]
        assert [l.points for l in a.links] == [l.points for l in b.links]

    def test_no_box_overlaps(self):
        md = ("# Study Map\n## One\n- alpha lengthy detail about anatomy today\n"
              "    - sub alpha\n    - sub beta\n## Two\n- beta section\n"
              "    - more items\n    - another entry here\n## Three\n- gamma part")
        root = make_root(md)
        layout = build_layout(root)
        for i in range(len(layout.placed)):
            for j in range(i + 1, len(layout.placed)):
                assert not overlaps(layout.placed[i], layout.placed[j]), (
                    layout.placed[i].box.text, layout.placed[j].box.text)

    def test_children_share_parent_side(self):
        root = make_root("# T\n## A\n    - a1\n    - a2")
        layout = build_layout(root)
        by_text = {p.box.text: p for p in layout.placed}
        a = by_text["A"]
        for child in ("a1", "a2"):
            c = by_text[child]
            assert c.side == a.side


class TestBalanceBehavior:
    def test_both_sides_used_for_many_branches(self):
        md = "\n".join(f"- Branch {i}" for i in range(6))
        root = make_root(md)
        layout = build_layout(root)
        sides = {p.side for p in layout.placed}
        assert sides == {-1, 0, 1}

    def test_balanced_extents(self):
        md = "\n".join(f"- Branch {i}\n    - d{i} a\n    - d{i} b" for i in range(6))
        root = make_root(md)
        layout = build_layout(root)
        # the two sides should reach much the same distance from y=0
        top = min(p.top for p in layout.placed)
        bottom = max(p.bottom for p in layout.placed)
        biggest = max(abs(top), abs(bottom))
        assert abs(abs(top) - abs(bottom)) <= biggest * 0.5

    def test_heavy_branch_placed_with_room(self):
        # One deep branch among shallow siblings must still stack cleanly.
        md = ["# T"]
        for i in range(3):
            md.append(f"## Shallow {i}")
            md.append("- leaf")
        md += ["## Big", "- x", "    - y", "    - z", "        - w"]
        root = make_root("\n".join(md))
        layout = build_layout(root)
        big = next(p for p in layout.placed if p.box.text == "Big"
                   and p.box.depth == 1)
        kids = [p for p in layout.placed if p.box.depth >= 2
                and p.branch == big.branch]
        assert kids, "the Big branch's subtree is missing"
        for kid in kids:
            assert kid.side == big.side


class TestGeometry:
    def test_subtree_height_leaf_is_box_h(self):
        root = make_root("- A\n- B")
        node = root.children[0]
        assert subtree_height(node, 1) == measure(node, 1).box_h

    def test_subtree_height_parent_at_least_children_stack(self):
        root = make_root("- A\n    - b1\n    - b2\n    - b3")
        node = root.children[0]
        expected = sum(subtree_height(c, 2) for c in node.children) + 2 * V_GAP
        assert subtree_height(node, 1) >= expected

    def test_wrap_creates_taller_box(self):
        root = make_root("- something\n- " + " ".join(["word"] * 30))
        box = measure(root.children[1], 1)
        assert len(box.lines) >= 2
        assert box.box_h > measure(root.children[0], 1).box_h

    def test_font_sizes_shrink_with_depth(self):
        assert font_size_for(0) > font_size_for(1) > font_size_for(2)

    def test_columns_keep_depth_d_boxes_apart(self):
        root = make_root("# T\n## A\n    - a1\n    - a2")
        layout = build_layout(root)
        a = next(p for p in layout.placed if p.box.text == "A" and p.box.depth == 1)
        deeper = [p for p in layout.placed if p.box.depth == 2]
        if deeper:
            gap = min(abs(p.x - a.x) for p in deeper)
            assert gap > max(p.box.box_w for p in deeper) * 0.9


class TestDepthLimit:
    def test_deep_tree_clamped_four(self):
        chain = "- " + "\n".join(f"    {'    ' * k}- l{k}" for k in range(1, 6))
        md = "# T\n" + chain
        root = parse(md)
        assert root.max_depth() >= 5
        clamped = clamp_depth(root, 4)
        assert clamped.max_depth() == 4
        layout = build_layout(clamped, 4)
        assert len(layout.placed) == clamped.count()

    def test_max_depth_two_efficient(self):
        md = "# T\n" + "\n".join(
            f"## B{i}\n- item {i} a\n- item {i} b" for i in range(20))
        root = clamp_depth(parse(md), 2)
        layout = build_layout(root, 2)
        assert layout.height > layout.width or layout.width > 0
        for i in range(len(layout.placed)):
            for j in range(i + 1, len(layout.placed)):
                assert not overlaps(layout.placed[i], layout.placed[j])
