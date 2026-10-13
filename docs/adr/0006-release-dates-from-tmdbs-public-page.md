# Theatrical release dates come from TMDB's public release page

Radarr has one theatrical date per movie, `inCinemas`, and it is the earliest theatrical release in any country. It is often days or weeks before the release in the viewer's country, and it doesn't tell a limited release from a wide one. Radarr's metadata server has the same single date. TMDB has every country's dates with their release types, but its API needs an account and a key, and this project doesn't want to depend on one.

The collector reads TMDB's public release page (`themoviedb.org/movie/<id>/releases`) instead. The `tmdbId` comes from Radarr. The page is plain HTML with one table per country, and the parser is one small function tested against a saved page. To keep the load low, each movie's page is fetched at most once a day and only for candidates (monitored, not grabbed, `inCinemas` within 90 days). Requests send a descriptive User-Agent; a browser-like one gets HTTP 403 from TMDB's bot protection.

The cost is fragility: a redesign of the page breaks the parser. A page with no release tables raises an error, so In Theaters goes stale and the error banner names TMDB instead of the section quietly emptying. If TMDB blocks these requests or the page keeps changing, revisit this and use the TMDB API with a key.
