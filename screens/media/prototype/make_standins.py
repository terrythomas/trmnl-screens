"""PROTOTYPE: generate abstract grayscale stand-in posters (no real artwork) for public screenshots."""
import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).parent / "standin-posters"


def png(w, h, pixel):
    rows = b"".join(b"\0" + bytes(pixel(x, y) for x in range(w)) for y in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def art(n, w, h):
    kind = n % 4
    def px(x, y):
        u, v = x / w, y / h
        if kind == 0:   # diagonal bands
            return 40 if int((u + v) * 7) % 2 else 200
        if kind == 1:   # concentric rings
            return 30 + int(200 * (0.5 + 0.5 * math.sin(math.hypot(u - .5, v - .4) * 40)))
        if kind == 2:   # horizon with sun
            return 235 if math.hypot(u - .5, v - .35) < .18 else (90 if v > .6 else 170)
        return 60 if (int(u * 6) + int(v * 9)) % 2 else 190   # checker
    shade = 40 * (n // 4)
    return png(w, h, lambda x, y: max(0, min(255, px(x, y) - shade // 3)))


OUT.mkdir(exist_ok=True)
for n in range(1, 15):
    for size, (w, h) in {"thumb": (234, 351)}.items():
        (OUT / f"{n:02d}-{size}.png").write_bytes(art(n, w, h))
print("stand-ins written to", OUT)
