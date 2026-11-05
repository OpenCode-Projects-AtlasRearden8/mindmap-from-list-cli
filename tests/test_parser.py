"""Offline tests for outline parsing."""

from __future__ import annotations

import pytest

from mindmap_from_list.parser import (
    Node, clamp_depth, clean_text, parse, renumber,
)


def labels(node):
    return [n.text for n in node.children]


class TestMarkdownBullets:
    def test_flat_bullets_become_branches(self):
        root = parse("- Apples\n- Bananas\n- Cherries")
        assert root.text == "Mind Map"  # no single topic: generic root
        assert labels(root) == ["Apples", "Bananas", "Cherries"]
        assert root.depth == 0 and root.children[0].depth == 1

    def test_star_and_plus_bullets(self):
        root = parse("* A\n+ B\n- C")
        assert labels(root) == ["A", "B", "C"]

    def test_nested_bullets(self):
        root = parse("- A\n    - B\n        - C")
        assert labels(root) == ["B"]
        assert labels(root.children[0]) == ["C"]

    def test_two_space_indent_nesting(self):
        root = parse("- A\n  - B\n    - C")
        assert labels(root.children[0]) == ["C"]

    def test_equal_indent_items_are_siblings(self):
        root = parse("- A\n  - B\n  - C\n- D")
        assert root.text == "Mind Map"
        assert labels(root) == ["A", "D"]
        assert labels(root.children[0]) == ["B", "C"]

    def test_ordered_lists(self):
        root = parse("1. First\n2. Second\n3. Third")
        assert root.text == "Mind Map"
        assert labels(root) == ["First", "Second", "Third"]

    def test_tab_indent(self):
        root = parse("- A\n\t- B\n\t\t- C")
        a = root
        assert labels(a)[0] == "B"
        assert labels(a.children[0])[0] == "C"


class TestStructure:
    def test_multiple_top_level_items_get_a_root(self):
        root = parse("- A\n- B\n- C")
        assert root.text == "Mind Map"
        assert len(root.children) == 3

    def test_first_heading_is_root(self):
        root = parse("# Solar System\n## Mercury\n## Venus\n## Earth")
        assert root.text == "Solar System"
        assert labels(root) == ["Mercury", "Venus", "Earth"]

    def test_headings_then_bullets(self):
        text = "# Study\n## Topic one\n- alpha\n- beta\n## Topic two\n- gamma"
        root = parse(text)
        assert root.text == "Study"
        assert len(root.children) == 2
        assert labels(root.children[0]) == ["alpha", "beta"]
        assert labels(root.children[1]) == ["gamma"]

    def test_plain_indented_lines_parse(self):
        text = "Root\n    One\n        Two"
        root = parse(text)
        assert root.depth == 0
        assert root.text == "Root"
        assert labels(root)[0] == "One"
        assert labels(root.children[0]) == ["Two"]

    def test_depths_are_continuous(self):
        root = parse("- A\n  - B\n    - C\n      - D\n        - E")
        for node in root.walk():
            for child in node.children:
                assert child.depth == node.depth + 1


class TestNoiseHandling:
    def test_blank_lines_ignored(self):
        root = parse("- A\n\n\n- B\n")
        assert len(root.children) == 2

    def test_horizontal_rules_ignored(self):
        root = parse("- A\n---\n- B")
        assert [n.text for n in root.walk() if n.text != "Mind Map"] \
            and "---" not in [c.text for c in root.children]

    def test_code_fences_skipped(self):
        root = parse("- A\n```\n- not an item\n```\n- B")
        assert not any("not an item" in c.text for c in root.children)
        assert labels(root) == ["A", "B"]

    def test_html_comments_ignored(self):
        root = parse("- A\n<!-- secret -->\n- B")
        assert not any("secret" in c.text for c in root.children)

    def test_empty_input_raises(self):
        with pytest.raises(ValueError):
            parse("   \n\n  ---  \n")
        with pytest.raises(ValueError):
            parse("")

    def test_inline_markdown_stripped(self):
        root = parse("- **Bold** and *italic* and `code`")
        assert root.text == "Bold and italic and code"

    def test_links_keep_label_text(self):
        root = parse("- [Python docs](https://docs.python.org)")
        assert root.text == "Python docs"

    def test_escaped_characters_survive(self):
        root = parse(r"- Use \| pipes")
        assert root.text == "Use | pipes"

    def test_emoji_and_unicode_preserved(self):
        root = parse("- Arrows → and é")
        assert root.text == "Arrows → and é"


class TestClampDepth:
    def _tree(self):
        root = parse("# T\n## A\n- a1\n- a2\n## B\n- b1")
        return root

    def test_clamp_wider_than_tree_keeps_all(self):
        root = clamp_depth(self._tree(), 3)
        assert root.max_depth() == 2

    def test_clamp_drops_deeper(self):
        root = parse("- A\n    - B\n        - C\n            - D")
        clamped = clamp_depth(root, 2)
        texts = [n.text for n in clamped.walk()]
        assert "D" not in texts
        assert any(t.startswith("C") for t in texts)  # truncated marker
        assert "B" in texts

    def test_clamp_marks_truncated_multi_children(self):
        root = parse("- A\n- B\n    - c1\n    - c2\n    - c3")
        clamped = clamp_depth(root, 1)
        b = next(n for n in clamped.children if n.text == "B")
        assert b.children[0].text == "(+3 more)"

    def test_clamp_marks_truncated_single_child(self):
        root = parse("- A\n- B\n    - c1")
        clamped = clamp_depth(root, 1)
        b = next(n for n in clamped.children if n.text.startswith("B"))
        assert b.text == "B (...)"

    def test_clamp_min_depth_is_one(self):
        with pytest.raises(ValueError):
            clamp_depth(self._tree(), 0)

    def test_clamp_returns_copy_not_same_object(self):
        original = self._tree()
        clamped = clamp_depth(original, 2)
        assert clamped is not original
        # original untouched: still has all leaves
        assert [d.text for d in original.children[0].children] == ["a1", "a2"]


class TestHelpers:
    def test_clean_text_trim(self):
        assert clean_text("  hello  ") == "hello"

    def test_renumber_fixes_depths(self):
        tree = parse("- A\n  - B")
        orphan = tree.children[0]
        renumber(tree)
        assert tree.depth == 0 and orphan.depth == 1

    def test_walk_count(self):
        root = parse("- A\n  - B\n  - C\n- D")
        assert root.count() == 5  # root, A, B, C, D

    def test_is_leaf(self):
        root = parse("- A\n  - B\n- C")
        assert not root.is_leaf
        assert root.children[0].children[0].is_leaf

    def test_node_str_default(self):
        assert isinstance(Node("x", 0), Node)
        assert Node("x", 0).children == []
