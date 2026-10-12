# trmnl-screens

Custom e-ink dashboard screens for [TRMNL](https://usetrmnl.com) devices, served by a self-hosted [LaraPaper](https://github.com/usetrmnl/larapaper) instance. Each screen pairs a Liquid template with a Python collector that gathers data from home services and pushes it to a LaraPaper webhook.

The first screen is the **Media screen**: what to keep watching from Plex, what is airing in Sonarr, and what is releasing today in Radarr.

## Docs

- [CONTEXT.md](CONTEXT.md): glossary of the project's terms
- [docs/specs/media-screen.md](docs/specs/media-screen.md): Media screen spec
- [docs/adr/](docs/adr/): architecture decisions

## Secrets

The repo is public, so tokens, webhook UUIDs, IPs and hostnames live only in an untracked `.env` ([ADR-0003](docs/adr/0003-public-repo-secrets-policy.md)). Copy `.env.example` to get started, and install the gitleaks pre-commit hook:

```sh
pre-commit install
```

## License

See [LICENSE](LICENSE).
