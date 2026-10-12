# The repo is public, so every environment-specific value is treated as a secret

The repo is public and intended as a reference for others building their own screens. Besides the obvious API keys and the Plex token, LaraPaper webhook UUIDs are treated as secrets because anyone holding one can write to a screen. LAN IPs and private hostnames are also kept out so the repo never describes a specific deployment's network. All of these live only in an untracked `.env`. The repo ships a `.env.example`, fixtures contain invented data only, and a gitleaks pre-commit hook acts as a backstop.
