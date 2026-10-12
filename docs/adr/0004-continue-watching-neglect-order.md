# Continue Watching is grouped by item state, with neglect order inside each group

Plex orders Continue Watching most-recent first. The Media screen reorders it into three groups, shown in this order: **New** items first, then **In progress**, then **Next**. Within each group, items are in neglect order: the one left untouched the longest comes first.

New things lead because they are the reason to look at the screen. A new season of a show you follow, or a show appearing for the first time, is easy to miss in Plex's own row. Half-watched items come next, because they are the cheapest to pick up. Next episodes come last. Neglect order inside each group still resurfaces stalled titles, which was the point of the original pure neglect order.

## Considered options

- **Pure neglect order** (the earlier version of this decision): one list, least-recently watched first. Rejected because a new season premiere could end up behind a dozen half-watched items, and new arrivals are what the maintainer most wants to spot.
- **Plex's order** (most-recent first): mirrors what is already front of mind, which the screen is meant to complement, not repeat.

## Consequences

- The collector, not the template, decides each item's state and the final order, so the rule is unit-tested in one place.
- There is no hero item. Up to six items are shown as equal posters; the rest are listed as text.
- Do not "fix" this order back to Plex's.
