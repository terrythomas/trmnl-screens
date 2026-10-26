# Circuit outlines turn to fit, by one rule, with a north arrow

The F1 screen's circuit outline is its largest element, but drawn north-up many circuits leave much of their space empty. The collector now turns each outline to the angle that draws it largest around the name block, on both devices at once. It keeps the angle only if the outline gets at least 20% larger, and never turns it more than 90° either way. A north arrow on every Grand Prix shows where north is. The angle is computed, never chosen per circuit, so a new season or a new track needs no work.

The cost is that a turned outline can look different from the maps fans know. The quarter-turn limit keeps every outline from being upside down, and the 20% threshold leaves outlines that already fit at north-up. This refines [ADR-0010](0010-circuit-outlines-drawn-from-geojson.md), which listed north-up drawings as a cost.

## Considered Options

- **North-up always**: familiar, no arrow needed, but on the 2026 calendar some outlines would be drawn at only half the size they could have.
- **Best angle with no limits**: the largest drawings, but some outlines nearly upside down (Miami at 178°, Monaco at −141°).
- **An angle chosen per circuit**: could match broadcast maps, but needs a table that someone keeps up each season.
