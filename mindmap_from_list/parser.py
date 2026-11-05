"""Parse plain indented lists and Markdown bullet/numbered lists into a tree."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Width of one tab, in "indent column" units. Tab and 4-space and 2-space
# indents are all treated permissively by normalizing to a logical column.
TAB_WIDTH = 4

# Markdown bullet styles we recognize (case-insensitive after the bullet).
_BULLET_RE = re.compile(r"^(\s*)([-*+])\s+(.*)$")
_NUMBER_RE = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
_TITLE_RE = re.compile(r"^(\s*)(#{1,6})\s+(.*)$")

# Stripped inline markers: emphasis, code, links.
_INLINE_PATTERNS = (
    (re.compile(r"\*\*\*(.+?)\*\*\*"), r"\1"),
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),
    (re.compile(r"\*(.+?)\*"), r"\1"),
    (re.compile(r"__(.+?)__"), r"\1"),
    (re.compile(r"_(.+?)_"), r"\1"),
    (re.compile(r"~~(.+?)~~"), r"\1"),
    (re.compile(r"`(.+?)`"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),
)

_SKIP_RE = re.compile(r"^\s*(---+|===+|```.*|<!--.*-->)\s*$")
_INLINE_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass
class Node:
    """A node in the outline tree (root included)."""

    text: str
    depth: int  # 0 for the root, 1..n inside the tree
    children: list = field(default_factory=list)

    # --- convenience ------------------------------------------------------
    @property
    def is_leaf(self) -> bool:
        return not self.children

    def walk(self):
        """Yield every node in the subtree, including self, depth-first."""
        yield self
        for child in self.children:
            yield from child.walk()

    def max_depth(self) -> int:
        """Deepest level (root counts as 0) reachable in this subtree."""
        if not self.children:
            return self.depth
        return max(child.max_depth() for child in self.children)

    def count(self) -> int:
        return sum(1 for _ in self.walk())


def clean_text(raw: str) -> str:
    """Strip inline Markdown emphasis/links so box labels stay readable."""
    text = raw.strip()
    for pattern, repl in _INLINE_PATTERNS:
        text = pattern.sub(repl, text)
    text = text.replace("\\|", "|")  # escaped pipes from table-ish input
    return text.strip()


def _indent_width(whitespace: str) -> int:
    """Normalize indent whitespace to a logical column count."""
    width = 0
    for ch in whitespace:
        if ch == "\t":
            width += TAB_WIDTH - (width % TAB_WIDTH)
        else:
            width += 1
    return width


def parse(text: str) -> Node:
    """Parse list text into a tree.

    Nesting is determined by indentation: Markdown bullets, ordered
    lists, plain indented lines, and ``#`` headings are all accepted.
    The first heading in the file is treated as the document title and
    becomes the root; later headings become top-level branches.
    """
    text = _INLINE_COMMENT_RE.sub("", text)
    entries: list[tuple[int, str]] = []  # (indent, cleaned text)
    in_fence = False
    title: str | None = None

    for line in text.splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _SKIP_RE.match(line):
            continue

        match = _BULLET_RE.match(line) or _NUMBER_RE.match(line)
        if match:
            indent, body = _indent_width(match.group(1)), match.group(3)
            entries.append((indent, clean_text(body)))
            continue

        match = _TITLE_RE.match(line)
        if match:
            if title is None:
                title = clean_text(match.group(3))  # doc title -> root
            else:
                # Later headings become top-level branches; a deeper '#'
                # changes emphasis, not structure.
                entries.append((-1, clean_text(match.group(3))))
            continue

        # Plain indented line: pure leading whitespace.
        stripped = line.lstrip()
        indent = _indent_width(line[: len(line) - len(stripped)])
        entries.append((indent, clean_text(stripped)))

    if not entries and title is None:
        raise ValueError("No list items found in the input text.")

    # Build the tree. The root carries a sentinel indent of -999 so any
    # item (including headings at -1) stays above it. An item nests under
    # the nearest ancestor with a smaller indent; equal-indented items
    # become siblings.
    root = Node("", -1, [])
    root.indent = -999
    stack: list = [(root.indent, root)]
    for indent, label in entries:
        if not label:
            continue
        while stack[-1][0] >= indent and len(stack) > 1:
            stack.pop()
        node = Node(label, stack[-1][1].depth + 1, [])
        stack[-1][1].children.append(node)
        stack.append((indent, node))

    if title is not None and root.children:
        root = Node(title, 0, root.children)
        renumber(root)
    elif title is not None:
        root = Node(title, 0, [])
    elif len(root.children) == 1:
        # Single top-level item: use it as the mind map's root.
        root = root.children[0]
        root.depth = 0
        renumber(root)
    else:
        root = Node("Mind Map", 0, root.children)
        renumber(root)
    return root


def renumber(node: Node, depth: int = 0) -> None:
    """Fix depth fields after tree surgery (e.g. synthesized root)."""
    node.depth = depth
    for child in node.children:
        renumber(child, depth + 1)


def clamp_depth(root: Node, max_depth: int) -> Node:
    """Return a copy of the tree whose children stop at ``max_depth``.

    Nodes deeper than ``max_depth`` are dropped; nodes at ``max_depth``
    keep their labels but lose their subtrees. An ellipsis marker is
    appended to truncated branches so readers can tell content exists
    below the visible level.
    """
    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")

    def build(node: Node, depth: int) -> Node:
        copy = Node(node.text, depth, [])
        if depth < max_depth and node.children:
            for child in node.children:
                copy.children.append(build(child, depth + 1))
        elif depth == max_depth and node.children:
            if len(node.children) == 1:
                copy.text = f"{node.text} (...)".strip()
            else:
                copy.children.append(
                    Node(f"(+{len(node.children)} more)", depth + 1, [])
                )
        return copy

    return build(root, 0)
