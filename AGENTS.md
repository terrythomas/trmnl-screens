## Screens

Every screen must work on both devices, the TRMNL X and the TRMNL OG. A screen can be designed X-first, but its OG layout is part of the same work, not a follow-up.

### Previews

Don't run preview containers (such as `trmnlp serve`) on the host the screens are deployed to: it is short on memory, and a long-running preview container can push it into killing other services. Show design previews in Claude Artifacts instead.

## Agent skills

### Issue tracker

Issues are tracked in this repo's GitHub Issues via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one root `CONTEXT.md` plus `docs/adr/`. See `docs/agents/domain.md`.
