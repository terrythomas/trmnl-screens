# The Calendar screen is fed by the phone and kept fresh by a collector

The work calendar can't be reached from any server, only from the phone's calendar, so a calendar sync (an iOS Shortcut) pushes the day's events and replies straight to the screen's LaraPaper webhook. The template works out Now, Next, conflicts and free blocks against the render time, so a push shows up the moment it lands. LaraPaper only re-renders a webhook plugin for an hour after its last push, though, so the Calendar collector sends an empty `deep_merge` to the webhook on every tick. That keeps the template re-evaluating against the clock and never touches the events, so it can't overwrite a newer push.

## Considered Options

- **TRMNL Companion app**: no attendees, no replies, no way to hide declined events, and background sync at most hourly.
- **Collector computes Now/Next/conflicts in Python**: easier to test, but a fresh push would show stale results until the next tick.
- **Relying on frequent phone pushes alone**: the screen freezes as soon as the phone stops pushing, e.g. when it leaves home.
