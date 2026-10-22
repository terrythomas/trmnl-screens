# Local channels come from league sources, not ESPN alone

The Game Time screen needs each followed team's own local channel, since that is usually where a regular-season game airs. ESPN's free site API has schedules, statuses and channels for every league, but its local channel data has two gaps. For NBA games it often leaves out the team's own regional network, listing only the opponent's or nothing. For MLB games it sometimes puts a channel on the wrong side of the game, so a team's local channel is shown as the opponent's. The NHL, NFL and MLS data was correct in the checks made.

So ESPN stays the base source and two league sources replace its TV channels for their leagues. MLB channels come from the official MLB Stats API, which marks each broadcast home, away or national. NBA channels come from the team schedule page on nba.com, which embeds the team's whole season, with national, home and away channels per game, as JSON in the HTML. The league-wide NBA schedule file on `cdn.nba.com` would be simpler, but it returns HTTP 403 to non-browser clients, and the league schedule page loads its games in the browser. Each followed team's page is fetched once a day and cached.

The cost is fragility: a redesign of nba.com's pages breaks the NBA reader. A failure falls back to ESPN's channels and marks those games as possibly incomplete instead of failing the screen. If nba.com blocks these requests or keeps changing, revisit this.

## Considered Options

- **ESPN alone**: one source and one parser, but NBA games miss the team's own channel and MLB games can show the wrong side's channel.
- **A paid listings feed** (such as an XMLTV guide from a listings service): covers every channel, but costs money and lists channels, not games, so games still have to be matched by title.
- **The free public XMLTV guide**: lists games under per-team placeholder channels with wrong times, and names the real channel only in free text.
- **A per-team fallback channel in configuration**: easy, but it is a guess shown as fact, and it doesn't carry over to other users.
