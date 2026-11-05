"""Auto-balanced two-sided mind map layout math.

Layout model
------------
- The root sits at the horizontal center of the map.
- The root's children are split into a right side and a left side so the
  two sides carry near-equal vertical weight ("auto-balanced").
- Child subtrees stack vertically; a subtree block is as tall as the
  larger of (its own label box, its stacked children), so deep branches
  automatically claim more room. Siblings can never overlap by
  construction: every block is separated by a fixed vertical gap and
  every block contains its parent's box.
- All label boxes at one depth share a column edge per side, keeping
  the map tidy; deeper trees still align perfectly to the grid.
- Coordinates are fully deterministic: same input in, same map out.
"""

from __future__ import annotations

from dataclasses import dataclass

from .metrics import text_width, wrap

LINE_HEIGHT_FACTOR = 1.28
FONT_SIZES = {0: 18.0, 1: 14.0, 2: 12.0, 3: 10.5}
DEFAULT_FONT = 9.5
BOX_PAD_X = 10.0
BOX_PAD_Y = 6.0
H_GAP_1 = 34.0          # root -> depth-1 branch
H_GAP_N = 24.0          # branch -> its next level
V_GAP = 12.0            # vertical gap between sibling blocks
MAX_LINES = 4
TEXT_WIDTH_LEVELS = {0: 240.0, 1: 210.0, 2: 200.0}


# --------------------------------------------------------------------------
# Boxes
# --------------------------------------------------------------------------
@dataclass
class Box:
    text: str
    depth: int
    lines: list = None
    font_size: float = DEFAULT_FONT
    box_w: float = 0.0
    box_h: float = 0.0

    def __post_init__(self):
        if self.lines is None:
            self.lines = []


@dataclass
class PlacedBox:
    box: Box
    side: int          # -1 left, +1 right, 0 root
    x: float = 0.0     # box center
    y: float = 0.0     # box center
    branch: int = -1   # index among root's children (color key)

    @property
    def left(self) -> float:
        return self.x - self.box.box_w / 2.0

    @property
    def right(self) -> float:
        return self.x + self.box.box_w / 2.0

    @property
    def top(self) -> float:
        return self.y - self.box.box_h / 2.0

    @property
    def bottom(self) -> float:
        return self.y + self.box.box_h / 2.0


@dataclass
class Link:
    """Cubic Bezier connector: (start, c1, c2, end)."""

    points: tuple
    depth: int
    branch: int = -1


@dataclass
class LayoutResult:
    placed: list
    links: list
    width: float
    height: float
    min_x: float
    min_y: float


# --------------------------------------------------------------------------
# Measurement helpers (module level, handy for tests)
# --------------------------------------------------------------------------
def font_size_for(depth: int) -> float:
    return FONT_SIZES.get(depth, DEFAULT_FONT)


def max_text_width(depth: int) -> float:
    return TEXT_WIDTH_LEVELS.get(depth, 170.0)


def measure(node, depth: int) -> Box:
    """Wrap ``node.text`` and compute the label box size."""
    size = font_size_for(depth)
    lines = wrap(node.text, max_text_width(depth), size)[:MAX_LINES] or [""]
    widest = max(text_width(line, size) for line in lines)
    box_w = widest + 2 * BOX_PAD_X
    box_h = len(lines) * size * LINE_HEIGHT_FACTOR + 2 * BOX_PAD_Y
    return Box(
        text=node.text, depth=depth, lines=lines, font_size=size,
        box_w=box_w, box_h=box_h,
    )


def subtree_height(node, depth: int = 0) -> float:
    """Height of a subtree block (leaf: label box; parent: max of both)."""
    box = measure(node, depth)
    if not node.children:
        return box.box_h
    child_total = sum(subtree_height(c, depth + 1) for c in node.children)
    if len(node.children) > 1:
        child_total += V_GAP * (len(node.children) - 1)
    return max(box.box_h, child_total)


def balance_sides(weights: list) -> tuple:
    """Split child indices into (right, left) by greedy bin-packing.

    Heavy subtrees are placed first; every following item joins the
    currently lighter side, so both sides end up visually near-equal.
    """
    right, left = [], []
    total_r = total_l = 0.0
    for idx in sorted(range(len(weights)), key=lambda i: -weights[i]):
        w = weights[idx]
        if total_r < total_l or (total_r == total_l and not right):
            right.append(idx)
            total_r += w
        else:
            left.append(idx)
            total_l += w
    return right, left


# --------------------------------------------------------------------------
# Full layout
# --------------------------------------------------------------------------
def build_layout(root, max_depth: int = 99) -> LayoutResult:
    """Compute placements and connectors for a parsed (pre-clamped) tree.

    ``max_depth`` is ignored here beyond the tree already being clamped
    by the caller; it exists so callers can pass the value through.
    """
    measured: dict = {}

    def m(node) -> Box:
        key = id(node)
        if key not in measured:
            measured[key] = measure(node, node.depth)
        return measured[key]

    root_box = m(root)
    placed: list = [PlacedBox(root_box, 0, 0.0, 0.0, -1)]
    links: list = []
    node_to_placed: dict = {id(root): placed[0]}
    n_top = len(root.children)

    def branch_id_of(node) -> int:
        for i, top in enumerate(root.children):
            if node is top or _is_descendant(top, node):
                return i
        return -1

    def _is_descendant(ancestor, node) -> bool:
        for child in ancestor.children:
            if child is node or _is_descendant(child, node):
                return True
        return False

    # --- column edges (per side) -----------------------------------------
    # All boxes at a depth share one column edge; widths use the widest
    # box at each depth so both sides get symmetric, aligned columns.
    global_max_w: dict = {0: root_box.box_w}
    for node in root.walk():
        if node.depth >= 1:
            box = m(node)
            global_max_w[box.depth] = max(
                global_max_w.get(box.depth, 0.0), box.box_w)

    def col_right(depth: int) -> float:
        if depth <= 0:
            return root_box.box_w / 2.0
        if depth == 1:
            return col_right(0) + H_GAP_1
        return col_right(depth - 1) + global_max_w.get(depth - 1, 0.0) + H_GAP_N

    def col_left(depth: int) -> float:
        if depth <= 0:
            return -root_box.box_w / 2.0
        if depth == 1:
            return col_left(0) - H_GAP_1
        return col_left(depth - 1) - global_max_w.get(depth - 1, 0.0) - H_GAP_N

    def box_x_for(box: Box, side: int) -> float:
        col = col_right(box.depth) if side > 0 else col_left(box.depth)
        return col + box.box_w / 2.0 if side > 0 else col - box.box_w / 2.0

    # --- recursive placement ----------------------------------------------
    def place(node, side: int, y: float) -> PlacedBox:
        """Place ``node`` at (side column, y), then its children below it."""
        box = m(node)
        x = box_x_for(box, side) if side != 0 else 0.0
        placed_box = PlacedBox(box, side, x, y, branch_id_of(node))
        placed.append(placed_box)
        node_to_placed[id(node)] = placed_box

        if not node.children:
            return placed_box
        blocks = [(c, subtree_height(c, c.depth)) for c in node.children]
        total = sum(h for _, h in blocks) + V_GAP * (len(blocks) - 1)
        cursor = y - total / 2.0
        for child, h in blocks:
            child_y = cursor + h / 2.0
            cursor += h + V_GAP
            place(child, side, child_y)
        return placed_box

    # --- sides --------------------------------------------------------------
    if root.children:
        weights = [subtree_height(child, 1) for child in root.children]
        right_ids, left_ids = balance_sides(weights)
        right_children = [root.children[i] for i in right_ids]
        left_children = [root.children[i] for i in left_ids]

        b_right = [(c, subtree_height(c, 1)) for c in right_children]
        b_left = [(c, subtree_height(c, 1)) for c in left_children]
        total_r = sum(h for _, h in b_right) + V_GAP * (len(b_right) - 1)
        total_l = sum(h for _, h in b_left) + V_GAP * (len(b_left) - 1)

        cursor = -total_r / 2.0
        for child, h in b_right:
            place(child, 1, cursor + h / 2.0)
            cursor += h + V_GAP

        cursor = -total_l / 2.0
        for child, h in b_left:
            place(child, -1, cursor + h / 2.0)
            cursor += h + V_GAP

    # --- connectors ---------------------------------------------------------
    for node in root.walk():
        if not node.children:
            continue
        parent = node_to_placed.get(id(node))
        if parent is None:
            continue
        for child in node.children:
            child_p = node_to_placed.get(id(child))
            if child_p is not None:
                links.append(_link_between(parent, child_p))

    min_x = min(p.left for p in placed)
    max_x = max(p.right for p in placed)
    min_y = min(p.top for p in placed)
    max_y = max(p.bottom for p in placed)
    return LayoutResult(
        placed=placed,
        links=links,
        width=max_x - min_x,
        height=max_y - min_y,
        min_x=min_x,
        min_y=min_y,
    )


def _link_between(parent: PlacedBox, child: PlacedBox) -> Link:
    """Horizontal S-curve: parent's near edge -> child's near edge."""
    if child.side >= 0:
        sx = parent.right
        ex = child.left
        direction = 1.0
    else:
        sx = parent.left
        ex = child.right
        direction = -1.0

    span = max(abs(ex - sx), 8.0)
    slack = 0.45 if child.side >= 0 else 0.45
    c1 = (sx + direction * span * slack, parent.y)
    c2 = (ex - direction * span * slack, child.y)
    return Link(((sx, parent.y), c1, c2, (ex, child.y)),
                child.box.depth, child.branch)
