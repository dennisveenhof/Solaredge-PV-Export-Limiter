# Release process — for the maintainer (Dennis)

This document describes how to publish, version, and submit the integration once the
repository is on GitHub.

## One-time GitHub setup

1. **Create the repository** on GitHub:
   ```
   gh repo create Solaredge-PV-Export-Limiter --public --description \
     "Dynamic SolarEdge export limiter for Home Assistant"
   ```
   *(Repo already created at https://github.com/dennisveenhof/Solaredge-PV-Export-Limiter)*

2. **Push the local repo**:
   ```bash
   cd ha-pv-export-limiter
   git init -b main
   git add .
   git commit -m "Initial v0.1.0"
   git remote add origin git@github.com:dennisveenhof/Solaredge-PV-Export-Limiter.git
   git push -u origin main
   ```
3. **Verify CI passes** on the first push — check the Actions tab for green Validate / Tests / Lint.

## Publishing v0.1.0

1. Confirm `CHANGELOG.md` has a populated `[0.1.0]` section.
2. Tag the release:
   ```bash
   git tag v0.1.0 -m "Release v0.1.0"
   git push --tags
   ```
3. The `release.yml` workflow auto-runs and:
   - Updates `manifest.json` version from the tag
   - Builds `solaredge_pv_export_limiter.zip`
   - Publishes a GitHub Release with auto-generated notes

## Versioning rules (SemVer)

- **Patch** (`0.1.x`) — bug fixes, no behavior change
- **Minor** (`0.x.0`) — new features (e.g. new mode, new sensor)
- **Major** (`x.0.0`) — breaking changes that require user re-config

For < 1.0.0, breaking changes can also be in minor versions — call them out
loudly in `CHANGELOG.md`.

## Submitting to the HACS default registry

This makes your integration installable in one click for any HACS user (no need
to manually add as a custom repository).

### Step 1 — Brand

Add your integration to the HA brands repo:

1. Fork [home-assistant/brands](https://github.com/home-assistant/brands)
2. Create `custom_integrations/solaredge_pv_export_limiter/icon.png`
   (256×256 px, transparent background)
3. Create `custom_integrations/solaredge_pv_export_limiter/logo.png`
   (any reasonable size, transparent background)
4. Open a PR titled `Add solaredge_pv_export_limiter`

### Step 2 — HACS default

1. Verify the repo passes the [HACS requirements](https://hacs.xyz/docs/publish/include):
   - [x] `hacs.json` present
   - [x] Public repo
   - [x] At least one release with attached ZIP
   - [x] `info.md` or rendered README
   - [x] `manifest.json` valid
2. Open a PR to [hacs/default](https://github.com/hacs/default):
   - Edit `integration` file
   - Add a line with your repo: `dennisveenhof/Solaredge-PV-Export-Limiter`
   - Use the PR template
3. Maintainers respond within ~1-2 weeks.

### Step 3 — Announce

After approval:

- Post in [HA Community → Custom Integrations](https://community.home-assistant.io/c/projects/custom-integrations/29)
- Tweet / share on r/homeassistant if relevant
- Optional: link from your blog or YouTube

## Maintenance cadence

Suggested:

- **Weekly**: triage new issues, label as `bug` / `enhancement` / `question`
- **Monthly**: review Dependabot PRs for GitHub Action updates
- **Per HA release**: check the breaking-change blog post, run validation, fix any
  deprecated API usage
- **Quarterly**: review feature request issues, plan next minor version

## Pre-release checklist

Before tagging any release:

- [ ] All CI workflows green on `main`
- [ ] `CHANGELOG.md` updated with new version section
- [ ] Manual install test in a fresh HA Docker container
- [ ] Live test on production HA: mode switch, voltage protection, sensor loss reset
- [x] No `<gh-user>` placeholders remaining in the repo
- [ ] README screenshots up-to-date
- [ ] Version bump in `manifest.json` (or rely on `release.yml` to do it)
