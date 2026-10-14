# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
The household running the home server, reading screens on TRMNL e-ink devices around the house. Second, people reading the public repo as a reference for building their own screens.

## Product Purpose
Ambient dashboards that answer one question each at a glance, so nobody has to open an app. The Media screen answers "what should I watch"; the Calendar screen answers "what am I doing now, what's next, and where is there time to get other work done".

## Positioning
Screens are tuned to one real home's sources and habits, then published generically. Data comes from self-hosted services or the owner's phone, never from a cloud account.

## Operating Context
- Devices: TRMNL **OG** (800×480, 1–2 bit) and **X** (16 grays). Each screen picks its primary device; the Calendar screen is primarily read on an OG on a desk, glanced at mid-task from about a metre away.
- Rendering: a self-hosted LaraPaper server renders each screen's Liquid template (trmnlp format, TRMNL framework CSS) to an image on a playlist cycle. Nothing is interactive.
- Data: collectors in this repo push to LaraPaper webhooks; the Calendar screen is fed by an iOS Shortcut (docs/calendar-sync.md).

## Capabilities and Constraints
- One Liquid template per screen serves both devices, switching on bit depth (ADR-0005); the Calendar screen also has a `half_vertical` layout.
- Vocabulary lives in CONTEXT.md and is binding for on-screen copy.
- No fonts or images beyond what the TRMNL framework and the payload provide; no interaction, no motion.

## Evidence on Hand
Fixtures in `screens/*/fixtures` hold invented data only (ADR-0003). There is no real-world content in the repo, and none may be added.

## Product Principles
1. Answer the screen's question in a two-second glance; everything else is secondary.
2. Show only what is still actionable: past events, finished items and empty sections disappear.
3. Say when the data might be wrong (stale source, old sync) instead of looking confidently empty.
4. Same structure on every device; bigger devices get more room, not more sections.
