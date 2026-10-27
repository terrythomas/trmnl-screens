"""How the Poster lays out a circuit outline: the angle that draws it largest, its width on each device and
where the north arrow goes (spec: Outline angle and north arrow; ADR-0011).

The numbers in DEVICES are measured from the Poster CSS in src/full.liquid. Change either and bump LAYOUT,
so cached outlines are laid out again.
"""

import math

LAYOUT = 1
# The longer side of a drawn outline, in path units.
SIZE = 1000
# No outline turns further than this from north-up, and it only turns if that makes it this much larger.
MAX_TURN, MIN_GAIN = 90, 1.2
# Per device, in CSS px: the outline area above the tickets (w, h) and the smallest name block in its top-left
# corner (name_w, name_h); the line width; the name's capital size and the location's text size, for estimating
# their widths; the north arrow's radius (its box at any angle), the white gap it keeps and the search step.
DEVICES = {
    "x": {"w": 968, "h": 604, "name_w": 416, "name_h": 252, "line": 14, "caps": 104, "text": 22,
          "arrow": 64, "gap": 30, "step": 8},
    "og": {"w": 760, "h": 367, "name_w": 276, "name_h": 167, "line": 9, "caps": 68, "text": 16,
           "arrow": 39, "gap": 16, "step": 6},
}


def layout(coordinates: list[list[float]], name: str, location: str) -> dict:
    """The outline as the payload carries it: a path turned to its angle, with each device's width and arrow."""
    boxes = {dev: _box(d, name, location) for dev, d in DEVICES.items()}
    line = _dense(coordinates)

    def scales(angle):
        pts = _normalise(_project(line, angle))
        return {dev: _scale(pts, box) for dev, box in boxes.items()}

    def score(angle):
        return math.prod(scales(angle).values())

    best = max(range(-MAX_TURN, MAX_TURN + 1), key=lambda a: (round(score(a), 9), -abs(a)))
    # The score multiplies the two devices' scales, so the gain is compared squared.
    angle = best if score(best) >= score(0) * MIN_GAIN ** 2 else 0

    pts = _normalise(_project(coordinates, angle))
    w, h = max(x for x, _ in pts), max(y for _, y in pts)
    out = {"d": "M" + "L".join(f"{x:.0f} {y:.0f}" for x, y in pts) + "Z", "w": round(w), "h": round(h), "angle": angle}
    for dev, s in scales(angle).items():
        box = boxes[dev]
        area_w, area_h = box["w"] - box["line"], box["h"] - box["line"]
        # The template anchors the outline to the bottom-right corner of the area, at this share of its width.
        placed = [(area_w - w * s + x * s, area_h - h * s + y * s) for x, y in pts]
        north = _arrow(placed, box, area_w, area_h)
        out[dev] = {"width": round(s * w / area_w * 100, 2),
                    "north": [round(north[0] / area_w * 100, 2), round(north[1] / area_h * 100, 2)] if north else None}
    return out


def _box(device, name, location):
    """The device's numbers, with the name block widened to fit this Grand Prix's name and location."""
    first = name.split(" Grand Prix")[0]
    # shortcut: widths are estimated from letter counts (0.62 em per heavy capital, 0.56 em per location
    # letter); measure the rendered text instead if a long name ever clips.
    name_w = max(device["name_w"], round(0.62 * device["caps"] * len(first)) + 24,
                 round(0.56 * device["text"] * len(location)) + 24)
    return {**device, "name_w": name_w}


def _project(coordinates, angle):
    """[lon, lat] points to screen points, north-up then turned clockwise by angle degrees.
    Longitude is scaled by cos(latitude) so the shape is true; y grows downwards."""
    k = math.cos(math.radians(sum(lat for _, lat in coordinates) / len(coordinates)))
    a = math.radians(angle)
    cos, sin = math.cos(a), math.sin(a)
    return [(lon * k * cos + lat * sin, lon * k * sin - lat * cos) for lon, lat in coordinates]


def _normalise(pts):
    left, top = min(x for x, _ in pts), min(y for _, y in pts)
    scale = SIZE / max(max(x for x, _ in pts) - left, max(y for _, y in pts) - top)
    return [((x - left) * scale, (y - top) * scale) for x, y in pts]


def _dense(coordinates, k=4):
    """The closed line with k points per segment, so no corner of the track slips between two points."""
    ring = coordinates if coordinates[0] == coordinates[-1] else [*coordinates, coordinates[0]]
    return [[a[0] + (b[0] - a[0]) * i / k, a[1] + (b[1] - a[1]) * i / k] for a, b in zip(ring, ring[1:]) for i in range(k)]


def _scale(pts, box):
    """The largest scale for pts anchored bottom-right in the area that keeps the line out of the name block.
    A point clears the block if it sits right of it or below it, and each gives a largest scale directly."""
    area_w, area_h = box["w"] - box["line"], box["h"] - box["line"]  # the line's half-width stays inside
    x1, y1 = max(x for x, _ in pts), max(y for _, y in pts)
    best = min(area_w / x1 if x1 else math.inf, area_h / y1 if y1 else math.inf)
    for x, y in pts:
        right = (area_w - box["name_w"]) / (x1 - x) if x < x1 else math.inf
        below = (area_h - box["name_h"]) / (y1 - y) if y < y1 else math.inf
        best = min(best, max(right, below))
    return best


def _arrow(line, box, area_w, area_h):
    """The arrow's centre: outside the circuit, clear of the line and the name block by the gap, as close to the
    line as that allows; among equally close spots, the one furthest from the name. None if nowhere fits."""
    r, gap, step = box["arrow"], box["gap"], box["step"]
    segments = list(zip(line, line[1:] + line[:1]))
    best = None
    for cy in range(r, int(area_h - r) + 1, step):
        for cx in range(r, int(area_w - r) + 1, step):
            to_name = math.hypot(max(cx - box["name_w"], 0), max(cy - box["name_h"], 0)) - r
            if to_name < gap:
                continue
            to_line = min(_to_segment(cx, cy, a, b) for a, b in segments) - box["line"] / 2 - r
            if to_line < gap or _inside(cx, cy, segments):
                continue
            key = (round(to_line / 8), -to_name)
            if best is None or key < best[0]:
                best = (key, (cx, cy))
    return best[1] if best else None


def _to_segment(px, py, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = ((px - a[0]) * dx + (py - a[1]) * dy) / (dx * dx + dy * dy) if dx or dy else 0
    t = min(max(t, 0), 1)
    return math.hypot(px - a[0] - t * dx, py - a[1] - t * dy)


def _inside(px, py, segments):
    """Even-odd ray cast: is the point inside the closed circuit?"""
    crossings = 0
    for (x0, y0), (x1, y1) in segments:
        if (y0 > py) != (y1 > py) and px < x0 + (py - y0) * (x1 - x0) / (y1 - y0):
            crossings += 1
    return crossings % 2 == 1
