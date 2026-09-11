"""A small two-layer maze router.

Obstacles (pads, tracks, vias, the board edge) are rasterised onto a grid at
GRID mm resolution, dilated by (track_width/2 + clearance) so that a cell is
walkable only if a track centred there keeps full clearance. Connections are
then found with Dijkstra over the two copper layers, with a heavy cost on
layer changes so vias are only used when a route genuinely needs one. The via
cost is deliberately steep: B.Cu carries the ground pour, and every track put
there cuts the plane. Cut it in the wrong place and the pour fragments into
islands, which strands whichever ground pads only reached the plane through a
via in the orphaned piece.

Everything the router emits is re-checked independently by verify.py.
"""
import heapq
import math

import numpy as np

GRID = 0.1                     # mm per cell
F_CU, B_CU = 0, 1
ORTHO, DIAG, VIA, TURN = 10, 14, 1000, 45

# the eight travel directions, indexed by the `d` component of a search state
DIRS = [(1, 0, ORTHO), (-1, 0, ORTHO), (0, 1, ORTHO), (0, -1, ORTHO),
        (1, 1, DIAG), (1, -1, DIAG), (-1, 1, DIAG), (-1, -1, DIAG)]


class Router:
    def __init__(self, x0, y0, x1, y1, clearance=0.2, edge_keepout=0.3):
        self.clearance = clearance
        self.ox = x0 - 1.0
        self.oy = y0 - 1.0
        self.nx = int(math.ceil((x1 - x0 + 2.0) / GRID)) + 1
        self.ny = int(math.ceil((y1 - y0 + 2.0) / GRID)) + 1
        self.obstacles = []       # (net, layers, kind, params)
        self.board = (x0, y0, x1, y1)
        self.edge_keepout = edge_keepout

    # ---- coordinate helpers -------------------------------------------------
    def cell(self, x, y):
        return (int(round((x - self.ox) / GRID)), int(round((y - self.oy) / GRID)))

    def pos(self, i, j):
        return (self.ox + i * GRID, self.oy + j * GRID)

    # ---- obstacle registration ---------------------------------------------
    def add_pad(self, net, gx, gy, w, h, rot, shape, layers):
        if int(round(rot)) % 180 == 90:
            w, h = h, w
        if shape == 'circle':
            self.obstacles.append((net, layers, 'circle', (gx, gy, max(w, h) / 2.0)))
        else:
            # custom pads (solder jumpers) are conservatively taken at full envelope
            if shape == 'custom':
                w, h = max(w, 1.0), max(h, 1.5)
            self.obstacles.append((net, layers, 'rect', (gx, gy, w / 2.0, h / 2.0)))

    def add_track(self, net, x1, y1, x2, y2, width, layer):
        self.obstacles.append((net, {layer}, 'seg', (x1, y1, x2, y2, width / 2.0)))

    def add_via(self, net, gx, gy, dia):
        self.obstacles.append((net, {'F.Cu', 'B.Cu'}, 'circle', (gx, gy, dia / 2.0)))

    # ---- rasterising --------------------------------------------------------
    def _blank(self):
        return np.zeros((2, self.nx, self.ny), dtype=bool)

    def _stamp(self, grid, layer_idx, kind, params, margin):
        """Mark every cell whose centre is within `margin` of the shape."""
        if kind == 'rect':
            cx, cy, hw, hh = params
            lo = self.cell(cx - hw - margin, cy - hh - margin)
            hi = self.cell(cx + hw + margin, cy + hh + margin)
            i0, j0 = max(lo[0], 0), max(lo[1], 0)
            i1, j1 = min(hi[0], self.nx - 1), min(hi[1], self.ny - 1)
            if i0 <= i1 and j0 <= j1:
                for li in layer_idx:
                    grid[li, i0:i1 + 1, j0:j1 + 1] = True
            return
        if kind == 'circle':
            cx, cy, r = params
            rr = r + margin
        else:
            ax, ay, bx, by, hw = params
            rr = hw + margin
            cx, cy = (ax + bx) / 2.0, (ay + by) / 2.0
        if kind == 'circle':
            lo = self.cell(cx - rr, cy - rr)
            hi = self.cell(cx + rr, cy + rr)
        else:
            lo = self.cell(min(ax, bx) - rr, min(ay, by) - rr)
            hi = self.cell(max(ax, bx) + rr, max(ay, by) + rr)
        i0, j0 = max(lo[0], 0), max(lo[1], 0)
        i1, j1 = min(hi[0], self.nx - 1), min(hi[1], self.ny - 1)
        if i0 > i1 or j0 > j1:
            return
        ii = np.arange(i0, i1 + 1) * GRID + self.ox
        jj = np.arange(j0, j1 + 1) * GRID + self.oy
        px = ii[:, None]
        py = jj[None, :]
        if kind == 'circle':
            mask = (px - cx) ** 2 + (py - cy) ** 2 <= rr * rr
        else:
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            if L2 == 0:
                mask = (px - ax) ** 2 + (py - ay) ** 2 <= rr * rr
            else:
                t = np.clip(((px - ax) * dx + (py - ay) * dy) / L2, 0.0, 1.0)
                mask = (px - (ax + t * dx)) ** 2 + (py - (ay + t * dy)) ** 2 <= rr * rr
        for li in layer_idx:
            grid[li, i0:i1 + 1, j0:j1 + 1] |= mask

    def build_blocked(self, net, width):
        """Blocked grid for routing `net` with the given track width."""
        margin = width / 2.0 + self.clearance
        grid = self._blank()
        for onet, layers, kind, params in self.obstacles:
            if onet == net:
                continue
            idx = [i for i, nm in ((F_CU, 'F.Cu'), (B_CU, 'B.Cu')) if nm in layers]
            if idx:
                self._stamp(grid, idx, kind, params, margin)
        # board edge keepout
        x0, y0, x1, y1 = self.board
        keep = self.edge_keepout + width / 2.0
        ii = np.arange(self.nx) * GRID + self.ox
        jj = np.arange(self.ny) * GRID + self.oy
        outx = (ii < x0 + keep) | (ii > x1 - keep)
        outy = (jj < y0 + keep) | (jj > y1 - keep)
        grid[:, outx, :] = True
        grid[:, :, outy] = True
        return grid

    def own_cells(self, net, width, pads):
        """Cells covered by this net's own pads, which are always walkable."""
        margin = -1e-9
        grid = self._blank()
        for gx, gy, w, h, rot, shape, layers in pads:
            if int(round(rot)) % 180 == 90:
                w, h = h, w
            idx = [i for i, nm in ((F_CU, 'F.Cu'), (B_CU, 'B.Cu')) if nm in layers]
            if not idx:
                continue
            if shape == 'circle':
                self._stamp(grid, idx, 'circle', (gx, gy, max(w, h) / 2.0), margin)
            else:
                if shape == 'custom':
                    w, h = max(w, 1.0), max(h, 1.5)
                self._stamp(grid, idx, 'rect', (gx, gy, w / 2.0, h / 2.0), margin)
        return grid

    # ---- search -------------------------------------------------------------
    def search(self, blocked, sources, targets, via_blocked=None):
        """Dijkstra from any source cell to any target cell.

        A search state carries the direction of travel so that changing
        direction can be charged TURN; that keeps routes as long straight runs
        with occasional 45deg corners instead of a staircase of single cells.
        A via is wider than a track, so layer changes are only allowed where
        `via_blocked` (built with the via diameter) is also clear; passing None
        forbids vias entirely.

        sources/targets are sets of (layer, i, j). Returns [(layer, i, j)].
        """
        nx, ny = self.nx, self.ny
        INF = float('inf')
        dist = {}
        prev = {}
        heap = []
        for l, i, j in sources:
            st = (l, i, j, -1)
            dist[st] = 0
            heapq.heappush(heap, (0, st))
        tset = set(targets)
        found = None
        while heap:
            d, node = heapq.heappop(heap)
            if d > dist.get(node, INF):
                continue
            l, i, j, dirn = node
            if (l, i, j) in tset:
                found = node
                break
            for nd, (di, dj, cost) in enumerate(DIRS):
                ni, nj = i + di, j + dj
                if not (0 <= ni < nx and 0 <= nj < ny):
                    continue
                if blocked[l, ni, nj]:
                    continue
                if di and dj:            # keep 45deg corners clear of obstacles
                    if blocked[l, i + di, j] or blocked[l, i, j + dj]:
                        continue
                step = cost + (0 if dirn in (nd, -1) else TURN)
                key = (l, ni, nj, nd)
                ndist = d + step
                if ndist < dist.get(key, INF):
                    dist[key] = ndist
                    prev[key] = node
                    heapq.heappush(heap, (ndist, key))
            if via_blocked is not None:
                ol = 1 - l
                if not (via_blocked[0, i, j] or via_blocked[1, i, j]):
                    key = (ol, i, j, -1)
                    ndist = d + VIA
                    if ndist < dist.get(key, INF):
                        dist[key] = ndist
                        prev[key] = node
                        heapq.heappush(heap, (ndist, key))
        if found is None:
            return None
        chain = [found]
        while chain[-1] in prev:
            chain.append(prev[chain[-1]])
        chain.reverse()
        return [(l, i, j) for l, i, j, _ in chain]

    # ---- path cleanup -------------------------------------------------------
    def line_clear(self, blocked, layer, a, b, ):
        """True if the straight H/V/45deg run a->b stays on walkable cells."""
        di, dj = b[0] - a[0], b[1] - a[1]
        if di == 0 and dj == 0:
            return True
        if not (di == 0 or dj == 0 or abs(di) == abs(dj)):
            return False
        n = max(abs(di), abs(dj))
        si, sj = di // n, dj // n
        for k in range(1, n + 1):
            i, j = a[0] + si * k, a[1] + sj * k
            if blocked[layer, i, j]:
                return False
            if si and sj and (blocked[layer, i - si, j] and blocked[layer, i, j - sj]):
                return False
        return True

    def simplify(self, blocked, path):
        """Greedily replace cell runs with the longest clear straight segments."""
        out = []
        start = 0
        while start < len(path):
            run_end = start
            while run_end + 1 < len(path) and path[run_end + 1][0] == path[start][0]:
                run_end += 1
            layer = path[start][0]
            pts = [(i, j) for _, i, j in path[start:run_end + 1]]
            keep = [pts[0]]
            k = 0
            while k < len(pts) - 1:
                best = k + 1
                for m in range(len(pts) - 1, k, -1):
                    if self.line_clear(blocked, layer, pts[k], pts[m]):
                        best = m
                        break
                keep.append(pts[best])
                k = best
            out += [(layer, i, j) for i, j in keep]
            start = run_end + 1
        return out

def path_to_geometry(router, path, width, net):
    """Turn a cell path into merged track segments plus vias at layer changes."""
    segs, vias = [], []
    run = [path[0]]
    for node in path[1:]:
        if node[0] != run[-1][0]:                 # layer change -> via
            segs += _emit_run(router, run, width, net)
            l, i, j = run[-1]
            x, y = router.pos(i, j)
            vias.append((x, y))
            run = [node]
        else:
            run.append(node)
    segs += _emit_run(router, run, width, net)
    return segs, vias


def _emit_run(router, run, width, net):
    """Collapse a same-layer cell run into straight segments."""
    if len(run) < 2:
        return []
    layer = 'F.Cu' if run[0][0] == F_CU else 'B.Cu'
    pts = [router.pos(i, j) for _, i, j in run]
    keep = [pts[0]]
    for k in range(1, len(pts) - 1):
        ax, ay = keep[-1]
        bx, by = pts[k]
        cx, cy = pts[k + 1]
        if (bx - ax) * (cy - by) != (by - ay) * (cx - bx):   # direction changed
            keep.append((bx, by))
    keep.append(pts[-1])
    out = []
    for a, b in zip(keep, keep[1:]):
        if a != b:
            out.append((a[0], a[1], b[0], b[1], width, layer, net))
    return out
