# TRMNL Screens

Custom e-ink dashboard screens for TRMNL devices, served by a self-hosted LaraPaper server on a home network. Each screen pairs a template with a collector that gathers its data from home services.

## Platform

**Screen**:
One self-contained dashboard design: a template plus whatever feeds it data (a collector, or a calendar sync), e.g. the Media screen or the Calendar screen.
_Avoid_: Plugin (LaraPaper's term for the installed form of a screen), recipe, dashboard

**Collector**:
The process that gathers a screen's data from its sources and pushes it to LaraPaper on a schedule.
_Avoid_: Fetcher, poller, backend

**Source**:
A service a collector reads from (Plex, Sonarr, Radarr, TMDB).
_Avoid_: Integration, provider

**Calendar sync**:
The phone pushing the day's events to the Calendar screen. Unlike a collector, it runs on the phone, not in this repo.
_Avoid_: Collector, companion

**Device**:
A physical TRMNL display: the **X** (large, 16 grays) or the **OG** (small, 1–2 bit). Every screen supports both. Each screen still picks its primary device, the one its design starts from; the Media screen targets the X, the Calendar screen the OG.

## Media screen

**Section**:
One of the content groups on the Media screen: Continue Watching, Airing, In Theaters, Streaming. A section with no items is removed entirely.

**Continue Watching**:
The items Plex's home-screen "Continue Watching" row holds for the configured account on the configured Plex server: in-progress items, next-up episodes, and newly available season premieres. Shown first on the screen, grouped by item state.
_Avoid_: On Deck, queue, playlist

**Item state**:
Where a Continue Watching item stands for the viewer. One of **New**, **In progress** or **Next**, shown in that order.

**New**:
An unstarted item that brings something new to the viewer: an unstarted movie, a show the viewer has never watched, or the first episode of a season of a show the viewer has not watched for 30 days or more.
_Avoid_: Unwatched, fresh

**In progress**:
An item the viewer has started and not finished. Shown with how much time is left.
_Avoid_: Partially watched, resume

**Next**:
Any other unstarted episode: the next episode of a show the viewer is watching, including the first episode of the following season when binge-watching.
_Avoid_: Up next, on deck

**Neglect order**:
Least-recently watched first, so the item left untouched the longest comes first. Applied within each item state, not across the whole of Continue Watching.

**Airing**:
Episodes of monitored Sonarr series whose air time falls within the airing window.
_Avoid_: Today's episodes, calendar

**Airing window**:
The 24-hour span from 12 hours before to 12 hours after the moment the collector runs.

**Also waiting**:
The Continue Watching items beyond the first six, listed as text below the posters.

**Milestone**:
An Airing row that opens or closes something: a series premiere, season premiere, midseason finale, season finale or series finale. A row that delivers a whole season at once, from its first episode to its finale, is an **entire season** instead.
_Avoid_: Special, event

**Grabbed**:
Whether the file for an episode or movie is already on the server.
_Avoid_: Downloaded, available, hasFile

**In Theaters**:
Monitored, not-grabbed Radarr movies that are in their **theater run** in the **release country**.
_Avoid_: Releasing today, upcoming movies, now playing

**Release country**:
The country whose release dates count for In Theaters (`RELEASE_COUNTRY`, default `US`). Radarr's own theatrical date is the earliest in any country, so the release country's dates come from TMDB.

**Wide release**:
The release country's "Theatrical" date on TMDB. Shown without a badge.
_Avoid_: Theatrical release, opening

**Limited release**:
A "Theatrical (limited)" date that comes before the wide release by at most 7 days, such as an early IMAX run. Other limited dates (re-releases, one-off screenings) are ignored. Shown with a "limited" badge and TMDB's note, until the wide release.

**Theater run**:
From the limited release (or the wide release when there is none) through the end of the Sunday on or after the wide release, in local time. A movie with no wide release in the release country has no run.
_Avoid_: Opening weekend, window

**Streaming**:
Monitored Radarr movies with a digital release today that aren't grabbed yet. Shown for that day only. Physical releases are ignored.
_Avoid_: Digital, releasing today, VOD

## Calendar screen

**Calendar**:
One of the calendars chosen for the calendar sync, e.g. work or personal. Every event shows which calendar it belongs to.

**Agenda**:
The events left today: anything not yet over, through midnight. Declined events are never shown. When no timed events are left, the Calendar screen leaves the playlist, unless the last calendar sync was before today.
_Avoid_: Schedule, timeline

**Now**:
The event in progress, shown as the hero. With none, the hero counts down to Next instead: time until the next meeting, then "starts in" for the last 15 minutes. An event hands the hero to Next 5 minutes before it ends.
_Avoid_: Current meeting

**Next**:
The first event starting after Now.
_Avoid_: Up next, upcoming

**Reply**:
Your answer to an invitation. **Pending** (not answered yet) gets a prominent badge, **tentative** a light "maybe" mark, accepted none. Declined events are hidden. Events without attendees have no reply.
_Avoid_: RSVP, response, status

**All-day event**:
An event with no start time. Shown on one line above the agenda; never counted for conflicts or free blocks.

**Conflict**:
Two or more events, from any calendars, that overlap by any amount. Events awaiting a reply count; declined and all-day events do not.
_Avoid_: Clash, double-booking

**Workday**:
The hours free blocks are found in, 9:00 to 17:00 by default; both ends are plugin settings.

**Free block**:
A gap of more than 30 minutes with no events, between now and the end of the workday.
_Avoid_: Free time, gap, availability

## Game Time screen

**Followed team**:
A team the screen tracks, chosen in the collector's settings. Only games involving a followed team are shown.
_Avoid_: Favorite team, my team

**Game window**:
Today and tomorrow, each from midnight to midnight in local time. A game belongs to the day it starts. The screen shows a Today section and a Tomorrow section, hides whichever is empty, and leaves the playlist when both are. A game that starts before midnight and is still live after it stays in Today.
_Avoid_: Lookahead, range

**Game row**:
One game on the screen: the followed team first, then "vs" (home) or "@" (away) and the opponent, with the start time and channels. When two followed teams meet, the game gets one row, away team "@" home team.
_Avoid_: Matchup, card, fixture

**Featured game**:
A game shown large at the top of the screen on a quiet day (four games or fewer). One or two of today's games are featured: all of them if there are only one or two, otherwise the live ones, otherwise the next to start. A game tomorrow is never featured. On busier days every game is a game row.
_Avoid_: Hero, spotlight game

**Live**:
A game that has started and is not yet final. It stays on the screen with its score and current period (quarter, half, inning, period, overtime) until the league calls it final; there is no assumed end time.
_Avoid_: In progress, ongoing

**Final**:
A game the league has called finished. Today's finals stay in the Today section with the final score.
_Avoid_: Completed, result

**Postponed**:
A game in the game window that will not be played as scheduled. It stays in its section, marked postponed, with no channels.
_Avoid_: Cancelled, delayed, rained out

**Channel**:
Anything a game can be watched on: a TV network, a streaming service or an out-of-market package. A game shows its local channels, or national channels when it has no local ones, plus any streaming; the opponent's local channels and out-of-market packages appear only when nothing else would.
_Avoid_: Broadcast, network, station

**Local channel**:
A followed team's own channel, whichever side of the game the team is on. The other team's own channel is the opponent's local channel.
_Avoid_: Regional, home channel

**Out-of-market package**:
A subscription that carries games outside a team's own market and blacks them out inside it, such as NBA League Pass or MLB.TV. Never counted as streaming.
_Avoid_: Streaming, league pass

**Unknown channel**:
A channel the screen doesn't recognise. Shown by name, and recorded once so it can be added later. A channel the screen knows but deliberately shows as text (one with no usable icon) is not unknown.
_Avoid_: Missing logo

## F1 screen

**Grand Prix**:
One round of the Formula 1 championship and its weekend of sessions. The F1 screen shows one at a time: the one with a session starting that day. Pre-season testing is not a Grand Prix.
_Avoid_: Race weekend, event, round

**Session**:
One timed part of a Grand Prix: Practice 1–3, Sprint Qualifying, the Sprint, Qualifying or the Race. A conventional weekend has three practices; a sprint weekend has one practice plus Sprint Qualifying and the Sprint.
_Avoid_: Event, run

**Session end**:
A session's start plus a fixed length: 1 hour for every session except the race, which gets 2. Delays and red flags are ignored.

**Over**:
A session whose session end has passed. Over sessions stay on the schedule, struck through.
_Avoid_: Finished, completed, done

**Next session**:
The first session of the shown Grand Prix that is not over. There is none after the race.
_Avoid_: Up next, current session

**Session day**:
A local date on which at least one session starts. The F1 screen is in the playlist only on session days, for the whole day.
_Avoid_: Race week, race weekend

**Circuit outline**:
The line drawing of the track the shown Grand Prix runs on, turned by up to 90° when that draws it noticeably larger.
_Avoid_: Track map, layout

**North arrow**:
The "N" and arrow beside the circuit outline, pointing to north. Shown on every Grand Prix, whether or not the outline is turned.
_Avoid_: Compass

**Spoiler**:
Anything that could reveal how a session went: results, positions, the grid, standings or live status. The F1 screen never shows one, because the household often watches delayed.

## Health

**Stale**:
A section showing its last good data because its source failed on the most recent collector run.

**Error banner**:
The on-screen notice that names a failing source and since when; the only alerting channel for collector failures.
