# PROTOTYPE: Media screen layout (issue #5)

Throwaway layout exploration for the Media screen on the TRMNL X. It lives on the
`prototype/media-layout` branch only; the approved design is rebuilt properly in the
production template (#10). Nothing here is tested or meant for reuse.

- `variants/b2_shelf_generic_icons.liquid`: the approved layout. `a_`, `b_` and `c_` are the first-round alternatives.
- `fixtures.py`: invented fixture variants (counts 1–12, empty sections, stale source, long titles, season drops).
- `render.py`: renders every variant × fixture through a running LaraPaper container, as the X sees it, into `out/`.
- `fetch_posters.py`: caches real grayscale posters from Plex into `poster-cache/` (gitignored, never committed).
- `make_standins.py`: generates abstract stand-in posters for screenshots that are safe to publish.
- `screenshots/`: renders with stand-in posters, used in the decision comment on #5.

```sh
python screens/media/prototype/make_standins.py
PROTOTYPE_POSTERS=standin python screens/media/prototype/render.py 'b2_*'
```
