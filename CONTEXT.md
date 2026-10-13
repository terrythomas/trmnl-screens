# TRMNL Screens

Custom e-ink dashboard screens for TRMNL devices, served by a self-hosted LaraPaper server on a home network. Each screen pairs a template with a collector that gathers its data from home services.

## Platform

**Screen**:
One self-contained dashboard design (template plus its collector), e.g. the Media screen. Future screens are added alongside it.
_Avoid_: Plugin (LaraPaper's term for the installed form of a screen), recipe, dashboard

**Collector**:
The process that gathers a screen's data from its sources and pushes it to LaraPaper on a schedule.
_Avoid_: Fetcher, poller, backend

**Source**:
A service a collector reads from (Plex, Sonarr, Radarr, TMDB).
_Avoid_: Integration, provider

**Device**:
A physical TRMNL display. The **X** (large, 16 grays) is the primary target; the **OG** (small, 1–2 bit) gets a reduced, poster-free rendering of the same screen.

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

## Health

**Stale**:
A section showing its last good data because its source failed on the most recent collector run.

**Error banner**:
The on-screen notice that names a failing source and since when; the only alerting channel for collector failures.
