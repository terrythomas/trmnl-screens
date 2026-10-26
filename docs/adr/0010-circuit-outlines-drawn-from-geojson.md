# Circuit outlines are drawn by the collector from bacinger GeoJSON

The F1 screen shows each Grand Prix's circuit outline. The collector fetches the circuit's line from the bacinger/f1-circuits GeoJSON set (MIT) at runtime, projects it to an SVG path and caches it in the state directory. It finds the circuit by nearest location to Jolpica's coordinates, so there is no id table to keep. As with [ADR-0009](0009-logos-fetched-at-runtime.md), no outline is committed; tests use invented lines.

Drawing beats fetching a ready-made image because it is the only option that is licensed, covers the whole current calendar (including new circuits such as Madrid's) and gives a clean line that looks the same on the X and the OG. The cost is a projection step in the collector and outlines drawn north-up, which can face differently from F1's broadcast maps.

## Considered Options

- **OpenF1 `circuit_image`**: no work, but F1's 2023 images, Madrid's showing the old Barcelona layout and some returning 404.
- **MultiViewer circuit API**: x/y track points with rotation and turn numbers, but no stated licence and no data for new circuits.
- **Ready-made SVG sets** (julesr0y, MisterSix2295): the first is gone, the second stopped in 2025 without Madrid.
