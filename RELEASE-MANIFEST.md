# Public Release Manifest

Status: release candidate — publication approved by the owner.

## Included

- `orchestrator/` — sanitized routing and document-intake code.
- `repo_synthesis/super-skill-creator/` — source package only; local virtualenvs and generated caches excluded.
- `web/pages/demo-command-center.php` and `web/assets/demo-command-center.css` — generic commercial demo surface.
- `assets/demo-mockup.png` and `assets/architecture.svg` — public-safe showcase assets.
- `Templates/document-intake-manifest.md` — route-manifest template.

## Excluded by design

- private vault notes and project logs;
- VPS IPs, usernames, SSH paths, deployment records, and migration packets;
- OmniRoute databases, provider accounts, cookies, and API-key material;
- local camera endpoints and camera assets;
- `.env`, runtime rotation state, caches, virtual environments, and generated archives;
- personal filesystem paths and personal agent-directory data.

## Review gate

The owner reviewed this tree and approved publication. Any new file added here
must be scanned again before a subsequent release.
