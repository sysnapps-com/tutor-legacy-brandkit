# tutor-legacy-brandkit

A **brand-agnostic** Tutor plugin for the Open edX branding surfaces that Paragon design tokens
do not reach:

- the legacy, server-rendered LMS pages (header logo, footer logo, favicon) and the legacy dashboard,
- ACE transactional / automated emails (logo, and button/link colours),
- the standard `MFE_CONFIG` logo/favicon keys (for parity with frontend-platform conventions),
- plus a documented audit method for third-party MFEs ([docs/THIRD_PARTY_MFE_AUDIT.md](docs/THIRD_PARTY_MFE_AUDIT.md)).

Nothing in the code names a brand. Every asset and colour comes from Tutor settings; unset
means "stock Open edX behaviour, untouched".

**Not in scope:** Paragon/design-token theming (use a separate plugin), Studio (CMS) header/footer
branding, and any programmatic fix for third-party MFEs.

> **Read [docs/VERIFICATION.md](docs/VERIFICATION.md) before relying on this.** It separates what
> was executed, what was only read from upstream source, and what is unverified (notably: the
> Docker image build and a running LMS were not available where this was developed).

## Requirements

Tutor 21.x (Ulmo) or 22.x (Verawood); Python >= 3.9. `tutor-mfe` is optional: the MFE patch is
only rendered when tutor-mfe is installed.

## Install

```bash
pip install ./tutor_legacy_brandkit-0.1.0-py3-none-any.whl    # or: pip install tutor-legacy-brandkit, once published
tutor plugins enable legacy-brandkit
```

## Configure

```bash
tutor config save \
  --set BRANDKIT_LOGO_PNG_URL=https://assets.example.org/brand/logo.png \
  --set BRANDKIT_LOGO_SVG_URL=https://assets.example.org/brand/logo.svg \
  --set BRANDKIT_LOGO_WHITE_SVG_URL=https://assets.example.org/brand/logo-white.svg \
  --set BRANDKIT_LOGO_TRADEMARK_SVG_URL=https://assets.example.org/brand/logo-trademark.svg \
  --set BRANDKIT_FAVICON_URL=https://assets.example.org/brand/favicon.ico \
  --set BRANDKIT_COLOR_PRIMARY='#112233' \
  --set BRANDKIT_COLOR_SECONDARY='#445566'
```

URLs must be absolute `http(s)` URLs with no whitespace, quotes, backslashes, `<`, `>`, backticks
or `$`. Colours must be `#RRGGBB`. Invalid values fail `tutor config save` with a clear error.
Use HTTPS on a publicly reachable host: email clients fetch the logo from *their* network.

| Setting | Default | Effect |
|---|---|---|
| `BRANDKIT_ENABLE_LMS` | `true` | Legacy LMS logo/footer/favicon settings |
| `BRANDKIT_ENABLE_EMAIL` | `true` | ACE email logo (and colours, if set) |
| `BRANDKIT_ENABLE_MFE` | `true` | `MFE_CONFIG` keys (needs tutor-mfe) |
| `BRANDKIT_LOGO_PNG_URL` | `""` | Legacy header logo (preferred over SVG) and the **email** logo |
| `BRANDKIT_LOGO_SVG_URL` | `""` | MFE `LOGO_URL` (falls back to PNG); legacy header if no PNG |
| `BRANDKIT_LOGO_WHITE_SVG_URL` | `""` | MFE `LOGO_WHITE_URL` |
| `BRANDKIT_LOGO_TRADEMARK_SVG_URL` | `""` | MFE `LOGO_TRADEMARK_URL` and the legacy footer logo (falls back to the header logo) |
| `BRANDKIT_FAVICON_URL` | `""` | `FAVICON_URL` for legacy pages and MFEs |
| `BRANDKIT_EMAIL_LOGO_URL` | `""` | Optional email-logo override (default: the PNG) |
| `BRANDKIT_COLOR_PRIMARY` | `""` | Email CTA button colour (image rebuild) |
| `BRANDKIT_COLOR_SECONDARY` | `""` | Email footer action-link colour (image rebuild) |
| `BRANDKIT_COLOR_ACCENT` | `""` | Validated and accepted; **no v1 surface consumes it** |
| `BRANDKIT_BAKE_STATIC_ASSETS` | `false` | Opt-in Tier 1: download the PNG/ICO into the image at build time |

**Email logo needs a PNG.** With only SVGs set, the email logo is left at Tutor's stock value on
purpose (many mail clients do not render SVG, and a blank logo is worse than a stock one). Set
`BRANDKIT_LOGO_PNG_URL` or `BRANDKIT_EMAIL_LOGO_URL`.

## Escalation hierarchy and why each surface sits where it does

The rule: **asset-first, settings-first, exception-driven.** Escalate one tier only when the
previous tier is demonstrably insufficient, and document the reason.

| Tier | Mechanism | Used for | Why this tier |
|---|---|---|---|
| **1** Asset substitution | Opt-in: at image build, download the PNG/ICO to `lms/static/images/` | Root `/favicon.ico` and pages built on `main_django.html` (logout, wiki, OAuth authorize); the stock `/theming/asset/images/logo.png` | A URL *setting* cannot reach a static-file path. Off by default because it needs build-time network and an image rebuild. |
| **2** Settings only | `LOGO_URL`, `LOGO_TRADEMARK_URL`, `FAVICON_URL`, `LOGO_URL_PNG_FOR_EMAIL`, `DEFAULT_EMAIL_LOGO_URL`, `NOTIFICATION_DIGEST_LOGO`, `MFE_CONFIG[...]` in the production / `mfe-lms-common` patches | Legacy header, footer, dashboard (inherits header), favicon on `main.html` pages, all ACE email logos, MFE keys | The platform already reads these; no template needs to change. Restart only. |
| **3** Shared template | Build-time substitution of **one stock colour** in the two shared ACE templates, with a failing assertion if it is gone | Email colours | ACE templates hardcode hex values and read none from context, so settings cannot reach them. A substitution with an assertion is smaller and safer than forking ~260 lines of upstream HTML. |
| **4** Page/message-specific template | **Not implemented** | - | The audit found no surface that needed it. `header.html`, `footer.html`, `dashboard.html` and per-message ACE templates stay stock. Add one only as a narrowly-scoped, documented exception. |

### Why `openedx-lms-production-settings`

Tutor's own `partials/common_lms.py` assigns `DEFAULT_EMAIL_LOGO_URL`, and the platform's
`get_logo_url_for_email()` prefers `LOGO_URL_PNG_FOR_EMAIL`, then `LOGO_URL_PNG`, and only then
`DEFAULT_EMAIL_LOGO_URL`. The plugin therefore sets all of them, plus the frozen
`NOTIFICATION_DIGEST_LOGO`, in the production patch (rendered last). On Tutor 21.0.9 and 22.0.2
the *common* patch also renders after Tutor's assignment; details in
[docs/VERIFICATION.md](docs/VERIFICATION.md).

## What needs a rebuild vs a restart

| Change | Action |
|---|---|
| Any URL setting for legacy LMS / email / `MFE_CONFIG` | `tutor local restart` (settings are read at process start) |
| `BRANDKIT_COLOR_*` | `tutor images build openedx` (build-time template edit), then restart |
| `BRANDKIT_BAKE_STATIC_ASSETS` and its URLs | `tutor images build openedx`, then restart |
| MFE keys | Restart; whether a given MFE also needs `tutor images build mfe` is **unverified**, see the MFE audit |

## Known limits and gotchas

- **DB site configuration wins.** A Django-admin Site Configuration value such as `logo_image_url`
  overrides the `LOGO_URL` setting for that site. Check it if a logo does not change.
- **Two plugins, one key.** If another plugin also writes `MFE_CONFIG` logo/favicon keys, the one applied last wins.
  Give each key one owner; set `BRANDKIT_ENABLE_MFE=false` to defer.
- **Build-time steps skip bind mounts.** With `tutor mounts` on `edx-platform`, the colour/baking edits do not apply.
- **Only `#005686` is substituted.** If a future release changes that colour, the image build **fails** on purpose
  (never silently un-branded). Run `scripts/check-platform-assumptions.sh <edx-platform checkout>` on each new release.
- **SVG fonts.** SVGs used via `<img>` cannot load web fonts. Outline the text in your logo files.
- **Footer.** The "Powered by Open edX" badge is a separate setting and is left untouched.

## Repository layout

```
src/tutorlegacybrandkit/
  plugin.py                                    settings, validators, hook wiring
  patches/openedx-lms-production-settings      Tier 2: header, footer, favicon, email
  patches/openedx-cms-production-settings      Tier 2: email only
  patches/mfe-lms-common-settings              Tier 2: MFE_CONFIG keys
  patches/openedx-dockerfile-post-git-checkout Tier 3 colours + opt-in Tier 1 baking
  templates/legacy-brandkit/partials/         shared email-logo snippet
scripts/  audit-mfe-branding.sh  check-platform-assumptions.sh
docs/     VERIFICATION.md  THIRD_PARTY_MFE_AUDIT.md
tests/    test_integration.py
```

## Development

```bash
pip install -e '.[test]'
pytest -q                                                        # real Tutor CLI, stubbed platform base
BRANDKIT_PLATFORM_CHECKOUT=/path/to/openedx-platform pytest -q   # also runs the recolour step on real templates
```

## License

MIT. See [LICENSE](LICENSE). Provided "as is", with no warranty — test in a non-production
environment first, and see [docs/VERIFICATION.md](docs/VERIFICATION.md) for what has and has
not been verified.
