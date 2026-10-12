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
A service a collector reads from (Plex, Sonarr, Radarr).
_Avoid_: Integration, provider

**Device**:
A physical TRMNL display. The **X** (large, 16 grays) is the primary target; the **OG** (small, 1–2 bit) gets a reduced, poster-free rendering of the same screen.

## Media screen

**Section**:
One of the three content groups on the Media screen: Continue Watching, Airing, Releasing Today. A section with no items is removed entirely.

**Continue Watching**:
The items Plex's home-screen "Continue Watching" row holds for the configured account on the configured Plex server: in-progress items, next-up episodes, and newly available season premieres. Shown as the hero section.
_Avoid_: On Deck, queue, playlist

**Neglect order**:
Continue Watching sorted by least-recently watched first, so the item left untouched the longest is the most prominent. Deliberately the reverse of Plex's own ordering.

**Hero**:
The most visually prominent item on a screen; on the Media screen, the first Continue Watching item in neglect order.

**Airing**:
Episodes of monitored Sonarr series whose air time falls within the airing window.
_Avoid_: Today's episodes, calendar

**Airing window**:
The 24-hour span from 12 hours before to 12 hours after the moment the collector runs.

**Grabbed**:
Whether the file for an episode or movie is already on the server.
_Avoid_: Downloaded, available, hasFile

**Releasing Today**:
Movies in Radarr with a theatrical release today (always shown) or a digital release today (shown only when not yet grabbed). Physical releases are ignored.
_Avoid_: Upcoming movies, this week's movies

## Health

**Stale**:
A section showing its last good data because its source failed on the most recent collector run.

**Error banner**:
The on-screen notice that names a failing source and since when; the only alerting channel for collector failures.
