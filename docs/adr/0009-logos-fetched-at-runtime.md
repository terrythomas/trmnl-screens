# Logos and channel icons are fetched at runtime, never committed

The Game Time screen shows team logos and channel icons. That artwork is copyrighted, trademarked or both, and much of the channel art comes from a collection with no licence. This repository is public. So no logo or icon file is committed anywhere in it, not even in tests or fixtures. The collector downloads the artwork when it runs: team logos from ESPN, channel icons from Simple Icons or the tv-logos collection. It converts each image for the device and caches the result in the state directory. What the repository does commit is a channel map, which says where each channel's icon comes from, with no artwork. Tests and fixtures use invented images.

Conversion happens in the collector because the OG's 1-bit dithering ruins gray logos. The collector makes true 1-bit images at the exact device size, chooses the threshold per logo, and falls back to the device's dithering when a logo is built from mid-tones or comes out mostly solid black.

The cost is a runtime dependency on third-party image hosts and a conversion step that needs its own tests. A missing image falls back to text, so an outage only makes the screen plainer. Removing artwork that has already been committed would mean rewriting public history, which is why the rule is "never commit" and not "commit, then clean up".

## Considered Options

- **Commit a curated icon set**: simple and offline, but it publishes other companies' trademarks and unlicensed artwork.
- **Fetch logos without converting them**, letting the device dither: less code, but most logos and channel marks turn to noise on the OG.
- **Text only**: no licensing exposure, but the screen loses the logos that make it readable at a glance.
