#!/usr/bin/env python3
"""Generate architecture SVG from JSON config. No external dependencies.

Usage: python3 generate_svg.py input.json output.svg

JSON format:
{
  "title": "Protocol Architecture",
  "nodes": [{"id": "x", "label": "Name", "subtitle": "Role", "type": "actor|protocol|external", "row": 0}],
  "edges": [{"from": "x", "to": "y", "label": "description"}],
  "groups": [{"label": "Group Name", "nodes": ["id1", "id2"]}]
}

"row" is optional — if omitted, layers are auto-assigned via longest-path.
"subtitle" is optional — shown as second line inside box.
"groups" is optional — draws an enclosure around the listed nodes.
"""

import json, sys, math
from collections import defaultdict, deque

# ── Dimensions ──
ACTOR_H = 14
BOX_H = 20
BOX_RX = 3
PILL_RX = 7
ACCENT_W = 1.4
ACCENT_PAD = 3
CHAR_W = 4.8
LABEL_PAD = 20
MIN_BOX_W = 60
MIN_ACTOR_W = 56
Y0 = 32
TITLE_Y = 11
LEGEND_STRIP_Y = 16
HGAP = 22             # min horizontal gap between nodes
VGAP = 62             # vertical gap between row origins
GROUP_PAD = 10
MARGIN_X = 30
MARGIN_BOTTOM = 20
SAME_ROW_ARC = 22     # how far same-row arcs rise above connection point
BELOW_ARC_GAP = 12    # base gap below boxes for below-routing of crossing same-row edges

# ── Colors ──
BG = "#F8F9FB"
BOX_FILL = "#fff"
BOX_STROKE = "#E2E5EA"
STROKE_W = 0.5
ACCENT_BLUE = "#3B82F6"
ACCENT_AMBER = "#F59E0B"
ARROW_COLOR = "#94A3B8"
ARROW_W = 0.5
TITLE_COLOR = "#1E293B"
LABEL_COLOR = "#1E293B"
SUB_COLOR = "#64748B"
FLOW_COLOR = "#1E293B"
LEGEND_COLOR = "#94A3B8"
HALO_COLOR = BG
HALO_W = 2
FONT_TITLE = 6
FONT_LABEL = 4.8
FONT_SUB = 3.5
FONT_FLOW = 4
FONT_LEGEND = 3
SCALE = 2.5


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def node_w(n):
    t = n.get("type", "protocol")
    label_w = len(n["label"]) * CHAR_W + LABEL_PAD
    sub = n.get("subtitle", "")
    if sub:
        label_w = max(label_w, len(sub) * (CHAR_W * 0.75) + LABEL_PAD)
    if t == "actor":
        return max(MIN_ACTOR_W, label_w)
    return max(MIN_BOX_W, label_w)


def node_h(n):
    return ACTOR_H if n.get("type", "protocol") == "actor" else BOX_H


# ═══════════════════════════════════════════════════════════════
# LAYER ASSIGNMENT
# ═══════════════════════════════════════════════════════════════

def auto_layers(node_ids, fwd, bwd):
    layer = {}
    visited = set()

    def dfs(n):
        if n in visited:
            return layer.get(n, 0)
        visited.add(n)
        if not bwd[n]:
            layer[n] = 0
            return 0
        d = max(dfs(p) for p in bwd[n]) + 1
        layer[n] = d
        return d

    for nid in node_ids:
        if nid not in visited:
            dfs(nid)
    mx = max(layer.values(), default=0)
    for nid in node_ids:
        layer.setdefault(nid, mx + 1)
    return layer


# ═══════════════════════════════════════════════════════════════
# DUMMY NODES for multi-layer edges
# ═══════════════════════════════════════════════════════════════

def insert_dummy_nodes(node_ids, nodes, edges, row_of, fwd, bwd):
    new_edges = []
    dummy_id = 0
    dummy_chains = {}

    for e in edges:
        fi, ti = e["from"], e["to"]
        fr, tr = row_of.get(fi, 0), row_of.get(ti, 0)
        span = abs(tr - fr)

        if span <= 1:
            new_edges.append(e)
            continue

        direction = 1 if tr > fr else -1
        chain = [fi]
        prev = fi
        for step in range(1, span):
            did = f"__d{dummy_id}"
            dummy_id += 1
            r = fr + step * direction
            row_of[did] = r
            nodes[did] = {"id": did, "label": "", "type": "__dummy", "row": r}
            node_ids.append(did)
            chain.append(did)
            new_edges.append({"from": prev, "to": did, "label": ""})
            fwd[prev].append(did)
            bwd[did].add(prev)
            prev = did

        new_edges.append({"from": prev, "to": ti, "label": e.get("label", "")})
        fwd[prev].append(ti)
        bwd[ti].add(prev)
        chain.append(ti)
        dummy_chains[(fi, ti)] = chain

    return node_ids, nodes, new_edges, row_of, fwd, bwd, dummy_chains


# ═══════════════════════════════════════════════════════════════
# CROSSING MINIMIZATION
# ═══════════════════════════════════════════════════════════════

def count_crossings(by_row, rows, fwd, row_of):
    total = 0
    for ri in range(len(rows) - 1):
        r, rn = rows[ri], rows[ri + 1]
        top, bot = by_row[r], by_row[rn]
        top_pos = {n: i for i, n in enumerate(top)}
        bot_pos = {n: i for i, n in enumerate(bot)}
        pairs = []
        for n in top:
            for c in fwd.get(n, []):
                if row_of.get(c) == rn and c in bot_pos:
                    pairs.append((top_pos[n], bot_pos[c]))
        for i in range(len(pairs)):
            for j in range(i + 1, len(pairs)):
                if (pairs[i][0] - pairs[j][0]) * (pairs[i][1] - pairs[j][1]) < 0:
                    total += 1
    return total


def barycenter_order(by_row, fwd, bwd, row_of):
    rows = sorted(by_row)
    if len(rows) <= 1:
        return
    order = {}
    for r in rows:
        for i, n in enumerate(by_row[r]):
            order[n] = float(i)

    best_crossings = count_crossings(by_row, rows, fwd, row_of)
    best_order = {r: list(by_row[r]) for r in rows}

    for iteration in range(30):
        for r in rows[1:]:
            for n in by_row[r]:
                pp = [order[p] for p in bwd.get(n, set())
                      if row_of.get(p) == r - 1 and p in order]
                if pp:
                    order[n] = sum(pp) / len(pp)
            by_row[r].sort(key=lambda n: order[n])
            for i, n in enumerate(by_row[r]):
                order[n] = float(i)
        for r in reversed(rows[:-1]):
            for n in by_row[r]:
                cc = [order[c] for c in fwd.get(n, [])
                      if row_of.get(c) == r + 1 and c in order]
                if cc:
                    order[n] = sum(cc) / len(cc)
            by_row[r].sort(key=lambda n: order[n])
            for i, n in enumerate(by_row[r]):
                order[n] = float(i)

        c = count_crossings(by_row, rows, fwd, row_of)
        if c < best_crossings:
            best_crossings = c
            best_order = {r: list(by_row[r]) for r in rows}
        elif iteration > 8 and c > best_crossings:
            break

    for r in rows:
        by_row[r] = list(best_order[r])


# ═══════════════════════════════════════════════════════════════
# COORDINATE ASSIGNMENT
# ═══════════════════════════════════════════════════════════════

def assign_coordinates(by_row, nodes, row_of, fwd, bwd):
    """Two-phase coordinate assignment:
    Phase 1: Place real nodes using parent barycenters, then compact.
    Phase 2: Place dummy nodes at interpolated positions along their edge.
    """
    rows = sorted(by_row)
    dims = {}
    for r in rows:
        for nid in by_row[r]:
            n = nodes[nid]
            if n.get("type") == "__dummy":
                dims[nid] = (0, 0)
            else:
                dims[nid] = (node_w(n), node_h(n))

    pos_x = {}

    # Phase 1: Place real nodes top-down using parent barycenters
    for ri, r in enumerate(rows):
        real_ns = [n for n in by_row[r] if nodes[n].get("type") != "__dummy"]
        dummy_ns = [n for n in by_row[r] if nodes[n].get("type") == "__dummy"]

        if ri == 0:
            # First row: place evenly
            _place_evenly(real_ns, pos_x, dims)
        else:
            # Compute target x from parents in the row above
            target = {}
            for nid in real_ns:
                parents = [p for p in bwd.get(nid, set())
                           if row_of.get(p) == r - 1 and p in pos_x]
                if parents:
                    target[nid] = sum(pos_x[p] for p in parents) / len(parents)
                else:
                    # No parent in row above; try grandparents or use default
                    all_parents = [p for p in bwd.get(nid, set()) if p in pos_x]
                    if all_parents:
                        target[nid] = sum(pos_x[p] for p in all_parents) / len(all_parents)
                    else:
                        target[nid] = None

            # Sort real nodes by target (keeping order for those without targets)
            orig_idx = {n: i for i, n in enumerate(real_ns)}
            def sort_key(n):
                if target.get(n) is not None:
                    return target[n]
                return orig_idx[n] * 1000  # preserve relative order
            real_ns.sort(key=sort_key)

            # Place left-to-right, pulling toward target
            _place_with_targets(real_ns, pos_x, dims, target)

        # Phase 2: Place dummies between their source and target positions
        for did in dummy_ns:
            parents = [p for p in bwd.get(did, set()) if p in pos_x]
            children = [c for c in fwd.get(did, []) if c in pos_x]
            xs = [pos_x[p] for p in parents] + [pos_x[c] for c in children]
            if xs:
                pos_x[did] = sum(xs) / len(xs)
            else:
                # Fallback: interpolate from all neighbors
                pos_x[did] = MARGIN_X

    # Bottom-up refinement: gently pull parents toward children
    for _ in range(3):
        for r in reversed(rows[:-1]):
            real_ns = [n for n in by_row[r] if nodes[n].get("type") != "__dummy"]
            target = {}
            for nid in real_ns:
                children = [c for c in fwd.get(nid, [])
                            if row_of.get(c) == r + 1 and c in pos_x]
                parents = [p for p in bwd.get(nid, set())
                           if row_of.get(p) == r - 1 and p in pos_x]
                xs = [pos_x[c] for c in children] + [pos_x[p] for p in parents]
                if xs:
                    target[nid] = sum(xs) / len(xs)
                else:
                    target[nid] = pos_x[nid]
            # Blend: move 30% toward target
            blended = {}
            for nid in real_ns:
                blended[nid] = pos_x[nid] * 0.7 + target[nid] * 0.3
            real_ns_sorted = sorted(real_ns, key=lambda n: blended[n])
            _place_with_targets(real_ns_sorted, pos_x, dims, blended)
            by_row[r] = _merge_order(by_row[r], real_ns_sorted, nodes)

        # Also update dummies after each pass
        for r in rows:
            for did in by_row[r]:
                if nodes[did].get("type") != "__dummy":
                    continue
                parents = [p for p in bwd.get(did, set()) if p in pos_x]
                children = [c for c in fwd.get(did, []) if c in pos_x]
                xs = [pos_x[p] for p in parents] + [pos_x[c] for c in children]
                if xs:
                    pos_x[did] = sum(xs) / len(xs)

    # Center the whole diagram
    all_xs = []
    for nid in pos_x:
        if nodes[nid].get("type") == "__dummy":
            continue
        w = dims[nid][0]
        all_xs.append(pos_x[nid] - w/2)
        all_xs.append(pos_x[nid] + w/2)
    if all_xs:
        content_left = min(all_xs)
        content_right = max(all_xs)
        content_mid = (content_left + content_right) / 2
        desired_mid = MARGIN_X + (content_right - content_left) / 2
        shift = desired_mid - content_mid
        for nid in pos_x:
            pos_x[nid] += shift

    # Assign y positions
    pos = {}
    for ri, r in enumerate(rows):
        y = Y0 + ri * VGAP
        for nid in by_row[r]:
            pos[nid] = (pos_x[nid], y)

    return pos, dims


def _place_evenly(ns, pos_x, dims):
    """Place nodes evenly starting from MARGIN_X."""
    cx = MARGIN_X
    for nid in ns:
        w = dims[nid][0]
        pos_x[nid] = cx + w / 2
        cx += w + HGAP


def _place_with_targets(ns, pos_x, dims, target):
    """Place nodes left-to-right, pulling toward target positions."""
    if not ns:
        return
    min_x = MARGIN_X
    for nid in ns:
        w = dims[nid][0]
        t = target.get(nid)
        if t is None:
            t = min_x + w / 2
        actual = max(t, min_x + w / 2)
        pos_x[nid] = actual
        min_x = actual + w / 2 + HGAP


def _merge_order(full_row, sorted_real, nodes):
    """Merge sorted real nodes back with dummies preserving dummy relative positions."""
    result = []
    real_iter = iter(sorted_real)
    for nid in full_row:
        if nodes[nid].get("type") == "__dummy":
            result.append(nid)
        else:
            result.append(next(real_iter))
    # Add any remaining real nodes
    for nid in real_iter:
        result.append(nid)
    return result


# ═══════════════════════════════════════════════════════════════
# EDGE ROUTING
# ═══════════════════════════════════════════════════════════════

def _segments_intersect(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    def on_seg(p, q, r):
        return (min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and
                min(p[1], r[1]) <= q[1] <= max(p[1], r[1]))
    p1, p2, p3, p4 = (ax1,ay1),(ax2,ay2),(bx1,by1),(bx2,by2)
    d1 = cross(p3,p4,p1); d2 = cross(p3,p4,p2)
    d3 = cross(p1,p2,p3); d4 = cross(p1,p2,p4)
    if ((d1>0 and d2<0) or (d1<0 and d2>0)) and \
       ((d3>0 and d4<0) or (d3<0 and d4>0)):
        return True
    if d1==0 and on_seg(p3,p1,p4): return True
    if d2==0 and on_seg(p3,p2,p4): return True
    if d3==0 and on_seg(p1,p3,p2): return True
    if d4==0 and on_seg(p1,p4,p2): return True
    return False


def line_rect_intersects(x1, y1, x2, y2, rx, ry, rw, rh, pad=3):
    rx -= pad; ry -= pad; rw += 2*pad; rh += 2*pad
    if rx <= x1 <= rx+rw and ry <= y1 <= ry+rh: return True
    if rx <= x2 <= rx+rw and ry <= y2 <= ry+rh: return True
    edges = [(rx,ry,rx+rw,ry),(rx,ry+rh,rx+rw,ry+rh),
             (rx,ry,rx,ry+rh),(rx+rw,ry,rx+rw,ry+rh)]
    for ex1,ey1,ex2,ey2 in edges:
        if _segments_intersect(x1,y1,x2,y2,ex1,ey1,ex2,ey2):
            return True
    return False


def route_edge(x1, y1, x2, y2, boxes, edge_idx):
    """Route an edge avoiding intermediate boxes. Returns waypoints."""
    waypoints = [(x1, y1)]
    collisions = [b for b in boxes
                  if line_rect_intersects(x1, y1, x2, y2, b[0], b[1], b[2], b[3])]
    if not collisions:
        waypoints.append((x2, y2))
        return waypoints

    collisions.sort(key=lambda b: (b[0]+b[2]/2-x1)**2 + (b[1]+b[3]/2-y1)**2)
    cx, cy = x1, y1
    for bx, by, bw, bh, bid in collisions:
        box_cx = bx + bw/2
        offset = 8 + (edge_idx % 3) * 2
        if (cx + x2)/2 < box_cx:
            wp_x = bx - offset
        else:
            wp_x = bx + bw + offset
        waypoints.append((wp_x, by + bh/2))
        cx, cy = wp_x, by + bh/2
    waypoints.append((x2, y2))
    return waypoints


def build_path_svg(x1, y1, x2, y2, same_row, edge_idx):
    """Build SVG path string for an edge. Returns (path_d, label_x, label_y)."""
    if same_row:
        # Horizontal arc above the boxes
        arc_y = min(y1, y2) - SAME_ROW_ARC
        mx = (x1 + x2) / 2
        # Quadratic bezier through the arc peak
        d = f"M{x1:.1f},{y1:.1f} Q{mx:.1f},{arc_y:.1f} {x2:.1f},{y2:.1f}"
        # Label at the arc apex
        lx = mx
        ly = arc_y + 4  # slightly below the peak for readability
        return d, lx, ly
    else:
        # S-curve (cubic bezier)
        ym = (y1 + y2) / 2
        d = f"M{x1:.1f},{y1:.1f} C{x1:.1f},{ym:.1f} {x2:.1f},{ym:.1f} {x2:.1f},{y2:.1f}"
        # Bezier midpoint
        lx = (x1 + 3*x1 + 3*x2 + x2) / 8
        ly = (y1 + 3*ym + 3*ym + y2) / 8
        return d, lx, ly


def build_below_arc_svg(x1, y1, x2, y2, row_bottom, edge_idx):
    """Build SVG path arcing BELOW boxes for same-row edges that cross intermediate nodes.

    Used when an above-arc would visually cross over boxes between source and target.
    Creates a smooth U-curve below the row, in the gap between layer bands.
    """
    gap = BELOW_ARC_GAP + (edge_idx % 3) * 4  # stagger depth for parallel below-arcs
    arc_y = row_bottom + gap
    cx1 = x1 + (x2 - x1) * 0.3
    cx2 = x1 + (x2 - x1) * 0.7
    d = f"M{x1:.1f},{y1:.1f} C{cx1:.1f},{arc_y:.1f} {cx2:.1f},{arc_y:.1f} {x2:.1f},{y2:.1f}"
    lx = (x1 + x2) / 2
    ly = arc_y + 4  # label below the arc peak
    return d, lx, ly


def build_routed_path_svg(waypoints):
    """Build SVG path from routed waypoints (>2 points)."""
    if len(waypoints) == 2:
        x1, y1 = waypoints[0]
        x2, y2 = waypoints[1]
        ym = (y1 + y2) / 2
        return f"M{x1:.1f},{y1:.1f} C{x1:.1f},{ym:.1f} {x2:.1f},{ym:.1f} {x2:.1f},{y2:.1f}"
    if len(waypoints) == 3:
        x1, y1 = waypoints[0]
        mx, my = waypoints[1]
        x2, y2 = waypoints[2]
        return f"M{x1:.1f},{y1:.1f} Q{mx:.1f},{my:.1f} {x2:.1f},{y2:.1f}"
    parts = [f"M{waypoints[0][0]:.1f},{waypoints[0][1]:.1f}"]
    for i in range(1, len(waypoints)):
        parts.append(f"L{waypoints[i][0]:.1f},{waypoints[i][1]:.1f}")
    return " ".join(parts)


def routed_path_midpoint(waypoints):
    """Find midpoint along a polyline path."""
    total = 0
    segs = []
    for i in range(len(waypoints) - 1):
        dx = waypoints[i+1][0] - waypoints[i][0]
        dy = waypoints[i+1][1] - waypoints[i][1]
        sl = math.sqrt(dx*dx + dy*dy)
        segs.append(sl)
        total += sl
    if total == 0:
        return waypoints[0]
    half = total / 2
    accum = 0
    for i, sl in enumerate(segs):
        if accum + sl >= half:
            t = (half - accum) / sl if sl > 0 else 0
            x = waypoints[i][0] + t * (waypoints[i+1][0] - waypoints[i][0])
            y = waypoints[i][1] + t * (waypoints[i+1][1] - waypoints[i][1])
            return (x, y)
        accum += sl
    return waypoints[-1]


# ═══════════════════════════════════════════════════════════════
# LABEL PLACEMENT with collision avoidance
# ═══════════════════════════════════════════════════════════════

def find_label_pos(mx, my, text, box_rects, placed, is_same_row=False):
    """Find collision-free position for an edge label."""
    tw = len(text) * FONT_FLOW * 0.6 + 4
    th = FONT_FLOW + 2

    if is_same_row:
        # For same-row arcs: label at arc peak, try shifts outward
        candidates = [
            (mx, my),
            (mx, my - 4),
            (mx + 14, my),
            (mx - 14, my),
            (mx, my - 8),
            (mx + 22, my - 4),
            (mx - 22, my - 4),
            (mx + 30, my),
            (mx - 30, my),
            (mx, my - 12),
        ]
    else:
        # Labels sit ON the arrow (at the bezier midpoint).
        # First candidate is the exact midpoint; fallbacks slide along the arrow
        # direction rather than perpendicular, keeping text on the path.
        candidates = [
            (mx, my),
            (mx, my - 4),
            (mx, my + 4),
            (mx + 8, my - 2),
            (mx - 8, my - 2),
            (mx + 8, my + 2),
            (mx - 8, my + 2),
            (mx, my - 8),
            (mx, my + 8),
            (mx + 16, my),
            (mx - 16, my),
            (mx + 16, my - 4),
            (mx - 16, my - 4),
            (mx, my + 12),
            (mx, my - 12),
        ]

    for cx, cy in candidates:
        lx = cx - tw/2
        ly = cy - th/2
        ok = True
        # Check boxes
        for bx, by, bw, bh, _ in box_rects:
            if (lx < bx + bw + 3 and lx + tw > bx - 3 and
                ly < by + bh + 3 and ly + th > by - 3):
                ok = False
                break
        # Check other labels
        if ok:
            for plx, ply, plw, plh in placed:
                if (lx < plx + plw + 2 and lx + tw > plx - 2 and
                    ly < ply + plh + 1 and ly + th > ply - 1):
                    ok = False
                    break
        if ok:
            placed.append((lx, ly, tw, th))
            return (cx, cy)

    # Fallback
    cx, cy = candidates[0]
    placed.append((cx - tw/2, cy - th/2, tw, th))
    return (cx, cy)


# ═══════════════════════════════════════════════════════════════
# MAIN GENERATE
# ═══════════════════════════════════════════════════════════════

def generate(cfg):
    nodes_list = cfg["nodes"]
    nodes = {n["id"]: n for n in nodes_list}
    edges = cfg["edges"]
    groups = cfg.get("groups", [])
    title = cfg.get("title", "Architecture")
    node_ids = [n["id"] for n in nodes_list]

    # Build adjacency
    fwd = defaultdict(list)
    bwd = defaultdict(set)
    for e in edges:
        fwd[e["from"]].append(e["to"])
        bwd[e["to"]].add(e["from"])

    # Layer assignment
    if all("row" in n for n in nodes_list):
        row_of = {n["id"]: n["row"] for n in nodes_list}
    else:
        row_of = auto_layers(node_ids, fwd, bwd)

    # Insert dummy nodes
    original_edges = list(edges)
    node_ids, nodes, edges, row_of, fwd, bwd, dummy_chains = \
        insert_dummy_nodes(node_ids, nodes, edges, row_of, fwd, bwd)

    # Group by row
    by_row = defaultdict(list)
    for nid in node_ids:
        by_row[row_of[nid]].append(nid)

    # Crossing minimization
    barycenter_order(by_row, fwd, bwd, row_of)

    # Coordinate assignment
    pos, dims = assign_coordinates(by_row, nodes, row_of, fwd, bwd)

    # Canvas size
    max_x = max((pos[n][0] + dims[n][0]/2) for n in pos if nodes[n].get("type") != "__dummy")
    max_y = max((pos[n][1] + dims[n][1]) for n in pos if nodes[n].get("type") != "__dummy")
    W = max(max_x + MARGIN_X, 200)
    H = max_y + MARGIN_BOTTOM

    pw = int(W * SCALE)
    ph = int(H * SCALE)

    # Collect real node boxes for collision detection
    box_rects = []  # (x, y, w, h, id)
    for nid in node_ids:
        if nodes[nid].get("type") == "__dummy":
            continue
        cx, cy = pos[nid]
        w, h = dims[nid]
        box_rects.append((cx - w/2, cy, w, h, nid))

    # ── SVG Output ──
    o = []
    a = o.append

    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{pw}" height="{ph}"'
      f' viewBox="0 0 {W:.0f} {H:.0f}" font-family="Arial, sans-serif">')
    a('  <defs>')
    a('    <marker id="ah" viewBox="0 0 8 6" refX="8" refY="3"')
    a('      markerWidth="4" markerHeight="3" orient="auto">')
    a(f'      <path d="M0.5,0.5 L7,3 L0.5,5.5" fill="none" stroke="{ARROW_COLOR}"')
    a('        stroke-width="1.2" stroke-linejoin="round" stroke-linecap="round"/>')
    a('    </marker>')
    a('    <filter id="shadow" x="-6%" y="-8%" width="112%" height="128%">')
    a('      <feDropShadow dx="0" dy="0.5" stdDeviation="0.8"')
    a('        flood-color="#000" flood-opacity="0.05"/>')
    a('    </filter>')
    a('  </defs>')
    a(f'  <rect width="{W:.0f}" height="{H:.0f}" fill="{BG}" rx="3"/>')

    # Title
    a(f'  <text x="{W/2:.0f}" y="{TITLE_Y}" text-anchor="middle"'
      f' font-size="{FONT_TITLE}" font-weight="700"'
      f' fill="{TITLE_COLOR}">{esc(title)}</text>')

    # Legend
    lw = 150
    lcx = W / 2
    lsy = LEGEND_STRIP_Y
    a(f'  <rect x="{lcx-lw/2:.0f}" y="{lsy}" width="{lw}" height="10"'
      f' rx="3" fill="{BOX_FILL}" stroke="{BOX_STROKE}" stroke-width="0.4"/>')
    sx = lcx - lw/2 + 5
    a(f'  <rect x="{sx:.0f}" y="{lsy+2.5}" width="5" height="5" rx="2.5"'
      f' fill="{BOX_FILL}" stroke="{BOX_STROKE}" stroke-width="0.4"/>')
    a(f'  <text x="{sx+8:.0f}" y="{lsy+6.5}" font-size="{FONT_SUB}"'
      f' fill="{FLOW_COLOR}">Actor</text>')
    sx += 40
    a(f'  <rect x="{sx:.0f}" y="{lsy+2.5}" width="5" height="5" rx="1.5"'
      f' fill="{BOX_FILL}" stroke="{BOX_STROKE}" stroke-width="0.4"/>')
    a(f'  <rect x="{sx+1:.0f}" y="{lsy+3.5}" width="0.8" height="3"'
      f' rx="0.4" fill="{ACCENT_BLUE}"/>')
    a(f'  <text x="{sx+8:.0f}" y="{lsy+6.5}" font-size="{FONT_SUB}"'
      f' fill="{FLOW_COLOR}">Protocol</text>')
    sx += 48
    a(f'  <rect x="{sx:.0f}" y="{lsy+2.5}" width="5" height="5" rx="1.5"'
      f' fill="{BOX_FILL}" stroke="{BOX_STROKE}" stroke-width="0.4"/>')
    a(f'  <rect x="{sx+1:.0f}" y="{lsy+3.5}" width="0.8" height="3"'
      f' rx="0.4" fill="{ACCENT_AMBER}"/>')
    a(f'  <text x="{sx+8:.0f}" y="{lsy+6.5}" font-size="{FONT_SUB}"'
      f' fill="{FLOW_COLOR}">External</text>')

    # Group enclosures (largest first, behind everything)
    # Compute uniform left/right boundary across all groups for visual consistency
    group_rects = []
    group_bounds = []
    for grp in groups:
        gnodes = [nid for nid in grp["nodes"] if nid in pos]
        if not gnodes:
            continue
        gx1 = min(pos[n][0] - dims[n][0]/2 for n in gnodes) - GROUP_PAD
        gy1 = min(pos[n][1] for n in gnodes) - GROUP_PAD
        gx2 = max(pos[n][0] + dims[n][0]/2 for n in gnodes) + GROUP_PAD
        gy2 = max(pos[n][1] + dims[n][1] for n in gnodes) + GROUP_PAD
        group_bounds.append((gx1, gy1, gx2, gy2, grp.get("label", "")))
    # Align all groups to the same left edge and width
    if group_bounds:
        uniform_x1 = min(b[0] for b in group_bounds)
        uniform_x2 = max(b[2] for b in group_bounds)
        for gx1, gy1, gx2, gy2, glabel in group_bounds:
            gw = uniform_x2 - uniform_x1
            gh = gy2 - gy1
            group_rects.append((uniform_x1, gy1, gw, gh, glabel))

    # Sort by area descending (largest background first)
    group_rects.sort(key=lambda g: g[2] * g[3], reverse=True)
    for gx, gy, gw, gh, glabel in group_rects:
        a(f'  <rect x="{gx:.1f}" y="{gy:.1f}" width="{gw:.1f}"'
          f' height="{gh:.1f}" rx="5" fill="#EDEEF2"/>')
        # Label at top-right to avoid content overlap
        a(f'  <text x="{gx + gw - 3:.1f}" y="{gy + 5:.1f}"'
          f' text-anchor="end" font-size="{FONT_SUB}"'
          f' fill="{LEGEND_COLOR}" font-weight="500">{esc(glabel)}</text>')

    # ── Edges ──
    edge_data = []  # (path_d, label_text, label_x, label_y, is_same_row)

    for i, e in enumerate(edges):
        fi, ti = e["from"], e["to"]
        if fi not in pos or ti not in pos:
            edge_data.append(None)
            continue

        fx, fy = pos[fi]
        tx, ty = pos[ti]
        fw, fh = dims[fi]
        tw, th = dims[ti]
        lbl = e.get("label", "")

        same_row = (row_of[fi] == row_of[ti])

        if same_row:
            # Connect at sides
            if fx < tx:
                x1 = fx + fw/2 if fw > 0 else fx
                x2 = tx - tw/2 if tw > 0 else tx
            else:
                x1 = fx - fw/2 if fw > 0 else fx
                x2 = tx + tw/2 if tw > 0 else tx
            y1 = fy + fh/2  # vertical center of source
            y2 = ty + th/2  # vertical center of target

            # Check if above-arc would cross intermediate boxes
            edge_left, edge_right = min(x1, x2), max(x1, x2)
            crosses_box = False
            for b in box_rects:
                if b[4] == fi or b[4] == ti:
                    continue
                bx, by, bw, bh, _ = b
                # Box is between source and target horizontally?
                if bx + bw > edge_left and bx < edge_right:
                    crosses_box = True
                    break

            if crosses_box:
                # Route BELOW boxes to avoid crossing
                by1 = fy + fh - 2  # near bottom of source
                by2 = ty + th      # bottom of target
                row_bottom = max(fy + fh, ty + th)
                path_d, lx, ly = build_below_arc_svg(x1, by1, x2, by2, row_bottom, i)
                edge_data.append((path_d, lbl, lx, ly, False))
            else:
                # Normal above-arc (no intermediate boxes to cross)
                path_d, lx, ly = build_path_svg(x1, y1, x2, y2, True, i)
                edge_data.append((path_d, lbl, lx, ly, True))
        else:
            # Vertical: bottom of source → top of target
            if fy < ty:
                x1, y1 = fx, fy + fh
                x2, y2 = tx, ty
            else:
                x1, y1 = fx, fy
                x2, y2 = tx, ty + th

            # Check for intermediate box collisions
            intermediate = [b for b in box_rects if b[4] != fi and b[4] != ti]
            needs_routing = any(
                line_rect_intersects(x1, y1, x2, y2, b[0], b[1], b[2], b[3])
                for b in intermediate
            )

            if needs_routing:
                wps = route_edge(x1, y1, x2, y2, intermediate, i)
                path_d = build_routed_path_svg(wps)
                mx, my = routed_path_midpoint(wps)
                edge_data.append((path_d, lbl, mx, my, False))
            else:
                path_d, lx, ly = build_path_svg(x1, y1, x2, y2, False, i)
                edge_data.append((path_d, lbl, lx, ly, False))

    # Render edge paths
    for ed in edge_data:
        if ed is None:
            continue
        path_d = ed[0]
        a(f'  <path d="{path_d}" fill="none" stroke="{ARROW_COLOR}"'
          f' stroke-width="{ARROW_W}" marker-end="url(#ah)"/>')

    # Render nodes (on top of edges)
    for nid in node_ids:
        n = nodes[nid]
        if n.get("type") == "__dummy":
            continue
        cx, cy = pos[nid]
        w, h = dims[nid]
        t = n.get("type", "protocol")

        if t == "actor":
            a(f'  <g filter="url(#shadow)">')
            a(f'    <rect x="{cx-w/2:.1f}" y="{cy:.1f}" width="{w:.1f}"'
              f' height="{h}" rx="{PILL_RX}" fill="{BOX_FILL}"'
              f' stroke="{BOX_STROKE}" stroke-width="{STROKE_W}"/>')
            a(f'    <text x="{cx:.1f}" y="{cy+h/2+1.8:.1f}"'
              f' text-anchor="middle" font-size="{FONT_LABEL}"'
              f' font-weight="600" fill="{LABEL_COLOR}">'
              f'{esc(n["label"])}</text>')
            a(f'  </g>')
        else:
            accent = ACCENT_AMBER if t == "external" else ACCENT_BLUE
            subtitle = n.get("subtitle", "")
            a(f'  <g filter="url(#shadow)">')
            a(f'    <rect x="{cx-w/2:.1f}" y="{cy:.1f}" width="{w:.1f}"'
              f' height="{h}" rx="{BOX_RX}" fill="{BOX_FILL}"'
              f' stroke="{BOX_STROKE}" stroke-width="{STROKE_W}"/>')
            a(f'    <rect x="{cx-w/2+ACCENT_PAD:.1f}" y="{cy+3:.1f}"'
              f' width="{ACCENT_W}" height="{h-6}" rx="0.6"'
              f' fill="{accent}"/>')
            if subtitle:
                a(f'    <text x="{cx:.1f}" y="{cy+h/2-0.5:.1f}"'
                  f' text-anchor="middle" font-size="{FONT_LABEL}"'
                  f' font-weight="600" fill="{LABEL_COLOR}">'
                  f'{esc(n["label"])}</text>')
                a(f'    <text x="{cx:.1f}" y="{cy+h/2+4.5:.1f}"'
                  f' text-anchor="middle" font-size="{FONT_SUB}"'
                  f' fill="{SUB_COLOR}">{esc(subtitle)}</text>')
            else:
                a(f'    <text x="{cx:.1f}" y="{cy+h/2+1.8:.1f}"'
                  f' text-anchor="middle" font-size="{FONT_LABEL}"'
                  f' font-weight="600" fill="{LABEL_COLOR}">'
                  f'{esc(n["label"])}</text>')
            a(f'  </g>')

    # Render edge labels (on top, with collision avoidance + background gap)
    placed = []
    for ed in edge_data:
        if ed is None:
            continue
        _, lbl, lx, ly, is_sr = ed
        if not lbl:
            continue
        fx, fy = find_label_pos(lx, ly, lbl, box_rects, placed, is_sr)
        # Background rect to create a visual gap in the arrow behind the label
        tw = len(lbl) * FONT_FLOW * 0.6 + 4
        th = FONT_FLOW + 2
        # Determine fill: use group fill if label center is inside a group rect
        bg_fill = BG
        for gx, gy, gw, gh, _ in group_rects:
            if gx <= fx <= gx + gw and gy <= fy <= gy + gh:
                bg_fill = "#EDEEF2"
                break
        a(f'  <rect x="{fx - tw/2:.1f}" y="{fy - th + 1:.1f}"'
          f' width="{tw:.1f}" height="{th:.1f}" rx="1" fill="{bg_fill}"/>')
        a(f'  <text x="{fx:.1f}" y="{fy:.1f}" font-size="{FONT_FLOW}"'
          f' fill="{FLOW_COLOR}" font-weight="500"'
          f' text-anchor="middle">{esc(lbl)}</text>')

    a('</svg>')
    return '\n'.join(o)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} input.json output.svg", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1]) as f:
        cfg = json.load(f)
    with open(sys.argv[2], 'w') as f:
        f.write(generate(cfg))
