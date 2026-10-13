# One responsive Liquid template per screen serves both the X and the OG

Each screen has a single `full.liquid` in the trmnlp format. It uses TRMNL framework breakpoint and bit-depth classes to adapt per device: the X gets posters and more items, and the OG drops posters for a dense typographic list because dithered posters at 1-bit and 800×480 look muddy. Liquid was chosen over LaraPaper-only Blade so screens stay portable to TRMNL cloud, trmnlp previews, and other people's servers. Mashup layouts (`half_*`, `quadrant`) are out of scope; the Media screen has too much data for them.

Update (#11): the switch is bit depth alone (`screen--1bit` / `screen--2bit`). LaraPaper sets no size class on `.screen`, so the framework's breakpoint classes never match there.
