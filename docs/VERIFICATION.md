# Verification status

Last verified: 2026-09-21. Environment: Python 3.12.3, Linux sandbox **without Docker and without a
running LMS**.

| Component | Version |
|---|---|
| Tutor / tutor-mfe | 22.0.2 / 22.1.0 (pins `release/verawood.1`) and 21.0.9 / 21.0.2 (pins `release/ulmo.4`) |
| openedx-platform read | tags `release/verawood.1` and `release/ulmo.4` |

Three levels are kept apart on purpose:

- **EXECUTED**: the code or shell ran here and the result was asserted.
- **SOURCE-READ**: read from upstream source at the tags above; not run.
- **UNVERIFIED**: not checked at all. Treat as a hypothesis.

## 1. EXECUTED (automated: `pytest`, 27 tests, all passing on Tutor 21.0.9 and 22.0.2)

| What | How |
|---|---|
| Plugin discovery, `plugins list`/`enable`, defaults | Real Tutor CLI, throw-away `TUTOR_ROOT`; also a **non-editable wheel** installed in a clean venv |
| Unset config renders nothing (no `LOGO_URL`, no Dockerfile lines) | Rendered files inspected |
| Resulting Django setting values and patch order | The fully rendered LMS `production.py` (including tutor-mfe's real `MFE_CONFIG` block and Tutor's own `DEFAULT_EMAIL_LOGO_URL`) is `exec`'d against a **stubbed** platform base; assertions on `LOGO_URL`, `LOGO_TRADEMARK_URL`, `FAVICON_URL`, `LOGO_URL_PNG_FOR_EMAIL`, `DEFAULT_EMAIL_LOGO_URL`, `NOTIFICATION_DIGEST_LOGO`, `MFE_CONFIG[...]` |
| Per-surface switches, SVG-only fallback, email override | Same harness |
| Input validation (URLs and colours), including shell/Python-injection attempts; a bad value can be fixed afterwards | Real CLI |
| **Email recolour shell step** on the *real* upstream templates of both tags: every `#005686` replaced (5 in the CTA, 2 in `base_body.html` on both tags), and a second run fails loudly ("upstream template changed") | Rendered `RUN` line executed with `sh` |
| **Baking shell step**: downloads, checks PNG/ICO magic bytes, installs; fails on wrong content type and on HTTP 404 | Rendered `RUN` lines executed against a local HTTP server |
| `scripts/check-platform-assumptions.sh` passes on both tags and fails on a deliberately broken copy | Run on sparse checkouts |
| `scripts/audit-mfe-branding.sh` on a real MFE (`openedx/frontend-app-profile`) | Run; output reviewed |
| Asset URLs: the four files exist at tag `v1.1.1` of the operator's repo; favicon has ICO magic bytes | Fetched from GitHub |

The stubbed harness proves the *settings* and *ordering*. It does not prove the platform behaves as read below.

## 2. SOURCE-READ (verified in source at both tags, never executed)

- Legacy header logo = `branding_api.get_logo_url()` -> `settings.LOGO_URL`; a DB site-configuration `logo_image_url` overrides it.
- Legacy footer logo = `settings.LOGO_TRADEMARK_URL`. Legacy dashboard template has **no** logo reference (it inherits `main.html`).
- Favicon in `main.html` = `settings.FAVICON_URL`. Root `/favicon.ico` redirects to a *static* `FAVICON_PATH`.
- Email logo precedence: `LOGO_URL_PNG_FOR_EMAIL` -> `LOGO_URL_PNG` -> `DEFAULT_EMAIL_LOGO_URL`.
- `NOTIFICATION_DIGEST_LOGO = DEFAULT_EMAIL_LOGO_URL` at import time (frozen copy).
- ACE `base_body.html` renders `{{ logo_url }}` and hardcodes hex colours; `#005686` appears in `return_to_course_cta.html` and `base_body.html`. The two templates are byte-identical between tags for `base_body.html`.
- `/theming/asset/<path>` is a view that **redirects** to the static file URL.
- `mfe_config_api` (Verawood) translates legacy `MFE_CONFIG["LOGO_URL"]` to frontend-base `headerLogoImageUrl`; it has no mapping for the white/trademark/favicon keys. Endpoint: `/api/mfe_config/v1`.
- Tutor: `partials/common_lms.py` assigns `DEFAULT_EMAIL_LOGO_URL` at line 22, the `openedx-lms-common-settings` patch renders at line 50, and `openedx-lms-production-settings` renders later still (identical layout on 21.0.9 and 22.0.2). This is also *executed* (section 1).

## 3. UNVERIFIED (do this before relying on it)

| Gap | Why | How to close it |
|---|---|---|
| **The Docker image build itself** (`tutor images build openedx`) | No Docker daemon here. The `RUN` lines were run with `sh`, not inside BuildKit / the Tutor `code` stage. | Build once; the build fails loudly if the stock colour is missing. |
| Header/footer/favicon actually display in a running LMS; emails contain the logo and recoloured buttons/links | No running LMS, no SMTP/ACE pipeline. Only settings values and template text were checked. | Sentinel-URL check in a browser; send a test ACE email (e.g. password reset) and a notification digest. |
| Mako compilation of any template | No platform runtime. The plugin overrides **no** Mako template. | n/a unless a Tier 4 override is ever added. |
| Site-configuration (DB) overrides in practice | Read in code, not exercised. | Check Django admin -> Site configuration for `logo_image_url` and similar keys on each site. |
| MFE side: which MFEs read the keys; whether any change needs `tutor images build mfe` | Tutor enables the runtime config API, but no MFE was run. The research doc's "usually rebuild" claim looks overstated but is **not** disproven. | `docs/THIRD_PARTY_MFE_AUDIT.md` step 4. |
| frontend-base use of `LOGO_WHITE_URL`, `LOGO_TRADEMARK_URL`, `FAVICON_URL` | Not in the platform's translation map. | Inspect the frontend-base app you deploy. |
| `{% favicon_path %}` implementation (used by `main_django.html`) | Tag definition was outside the sparse checkout. | Read `common/djangoapps` in a full checkout. |
| SVG rendering fidelity of the operator's logos | SVGs loaded through `<img>` cannot fetch web fonts. SVGs that name fonts without embedding or outlining them (as the initial test set for this project does) will likely render with fallback fonts. Not rendered here. | Load the SVG in an `<img>` on a machine without those fonts, or convert text to outlines. |
| CDN URLs reachable from the public internet | The development sandbox got HTTP 403 from the CDN serving the initial test assets (egress policy). | `curl -I` each URL from your network. |
| Email-client rendering of the recoloured CTA (contrast, dark mode) | Not tested. | Test in your target clients. |
| `bind-mounted` edx-platform (`tutor mounts`), Kubernetes, `tutor dev` | Build-time steps do not apply to mounted source. | Rebuild without mounts, or apply the changes to your mounted checkout. |
| Python 3.9-3.11 and Tutor >= 23 | Only Python 3.12 and Tutor 21/22 were run. | Run `pytest` in your environment. |

## 4. Where the research document was corrected

| Research-doc claim | Finding |
|---|---|
| `DEFAULT_EMAIL_LOGO_URL` is the setting that controls the email logo | It is the **last** fallback after `LOGO_URL_PNG_FOR_EMAIL` and `LOGO_URL_PNG`. Digest emails use a separate frozen `NOTIFICATION_DIGEST_LOGO`. |
| Putting it in `openedx-lms-common-settings` lets the platform default silently win | **Not reproducible** on Tutor 21.0.9 / 22.0.2: the common patch renders after Tutor's own assignment. The production patch is still used (last, harmless). The claim may reflect a different Tutor layout. |
| `/theming/asset/images/logo.png` is a canonical, directly-served asset (`curl -I` -> 200) | It is a redirect to the static file, and it can only show a custom logo if a file is baked into the image or an active theme supplies one. It cannot point at an operator URL. |
| Header/footer need `header.html` / `footer.html` or file replacement | Not needed: `LOGO_URL` / `LOGO_TRADEMARK_URL` settings drive them. `header/brand.html` hardcodes `images/logo.png` but nothing in stock LMS includes it. |
| The theme path `lms/templates/ace_common/...` overrides the ACE base | Only with an active comprehensive theme. This plugin avoids the need: hex colours are substituted at build time with a failing assertion. |
| `BRANDING_` as a settings prefix | Collides with the existing `tutor-contrib-branding` plugin (`BRANDING_MFE_LOGO_URL` etc.). This plugin uses `BRANDKIT_`. |
