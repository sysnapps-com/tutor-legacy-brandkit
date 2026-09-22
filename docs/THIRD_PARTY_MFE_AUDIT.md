# Third-party MFE branding audit

**Purpose.** Decide, per MFE, whether an operator can brand it with configuration alone, or
whether some part of it needs a source patch. This plugin deliberately does **not** try to
solve that programmatically: no single mechanism reaches arbitrary third-party MFE code.
What the plugin *does* do is write the standard `MFE_CONFIG` keys (`LOGO_URL`,
`LOGO_WHITE_URL`, `LOGO_TRADEMARK_URL`, `FAVICON_URL`). This audit tells you which MFEs
actually read them.

**Honesty note.** Static grep proves a string exists, not that the code path runs. Steps 1-3
are static evidence; steps 4-5 are the only real proof. Record which you did.

## Step 0 - Inventory

List every MFE you serve, and mark which are first-party Open edX (`learning`, `profile`,
`authn`, ...) and which are third-party or forked. Audit only the third-party/forked ones
in depth; first-party ones follow the standard conventions but still deserve a step-4 check.

## Step 1 - Run the read-only scan

```bash
git clone <mfe-repo> && cd <mfe-repo> && git checkout <the tag you deploy>
/path/to/tutor-legacy-brandkit/scripts/audit-mfe-branding.sh .
```

Audit the exact tag you deploy, not `master`. The script changes nothing.

## Step 2 - Read the hits (what each section means)

| Section | Look for | Meaning |
|---|---|---|
| A | `getConfig().LOGO_URL`, `.FAVICON_URL`, `.SITE_NAME`, `headerLogoImageUrl` | Reads the standard runtime config. **Good**: configuration can brand it. |
| B | `@edx/frontend-component-header` / `-footer`, `@openedx/frontend-base` | Shared components read the logo keys themselves. **Good**, if the MFE renders them. |
| C | `@edx/brand` -> `npm:@openedx/brand-openedx`, `brand/paragon` | **Build-time** brand package. Changing it requires an MFE image rebuild. Colours/fonts live here, not in `MFE_CONFIG`. |
| D | Files named `*logo*`, `*brand*`, `favicon*`; `<img ... logo>`; `import logo from ...` | **Hardcoded** asset. No setting reaches it. |
| E | `edx-cdn.org`, `edx.org`, `openedx.org` in `src/`, `public/`, `.env` | **Hardcoded remote** branding. Ignore `.env.development` / `.env.test`; they are not shipped. |
| F | `<title>`, `rel="icon"` in `public/index.html` or webpack config | Tab surface. Good if it interpolates `SITE_NAME` / `FAVICON_URL`; hardcoded otherwise. |
| G | `LOGO_URL=` etc. in `.env` | Build-time defaults. Non-empty values in `.env` (not dev/test) are a red flag: they may win over runtime config depending on how the MFE merges config. |
| H | "Open edX" / "edX" inside `messages.js` | Brand *name* in translatable copy. Not a logo problem; needs a translation/message override or a patch. |

## Step 3 - Classify

| Class | Evidence | Outcome |
|---|---|---|
| **A. Config-driven** | A and/or B present; D, E, F clean | Configuration is enough. |
| **B. Config + brand package** | A/B plus C | Logos via config; colours/fonts need the brand package/theme (out of scope here; a Paragon token plugin handles that). |
| **C. Hardcoded** | D or E hits in live code (not tests/mocks) | Needs a source patch or fork for those spots. |
| **D. Unknown** | Minified/vendored, or the scan is inconclusive | Do step 4 and treat as C until proven otherwise. |

## Step 4 - Runtime proof (required before you call anything "done")

1. Confirm what the LMS serves to that MFE (Verawood/Ulmo platform: `GET /api/mfe_config/v1?mfe=<app>`):
   ```bash
   curl -s "https://<lms-host>/api/mfe_config/v1?mfe=<app>" | python -m json.tool | grep -iE "logo|favicon|site_name"
   ```
   Your configured URLs must appear. If not, the setting is not reaching the MFE at all.
2. Use **sentinel values**: temporarily point `BRANDKIT_LOGO_SVG_URL` and `BRANDKIT_FAVICON_URL` at
   two obviously different images. Then open the MFE in a private window and check the header
   logo, footer logo, browser-tab icon, and tab title. Anything still showing stock branding is
   hardcoded or build-time.
3. DevTools, Network tab: filter on `logo`, `favicon`, `edx`. Any request to a stock host
   (`edx-cdn.org`, `openedx.org`) is a hardcoded reference. Note which request and which page.
4. Check the pages that are easy to forget: login/register, error pages, logout, a loading
   state, and any print/PDF view.
5. Force a cold load (hard refresh) and note whether the logo flashes stock branding first. A flash means
   the default is baked into the build and the runtime config arrives late.

## Step 5 - Remedy ladder (escalate only if the previous rung fails)

1. **Configuration.** `MFE_CONFIG` keys (this plugin), or per-MFE `MFE_CONFIG_OVERRIDES` if only
   one MFE needs different values (the platform's `mfe_config_api` merges it).
2. **Upstream.** If the MFE ignores standard config, the durable fix is a small PR making it
   read `getConfig()`. It benefits everyone and removes your maintenance cost.
3. **Build-time patch.** Apply a small, assertion-guarded patch in the MFE image build using
   tutor-mfe's Dockerfile patch points (for example `mfe-dockerfile-post-npm-install`;
   confirm the exact per-app patch names for your tutor-mfe version). Fail the build if the
   pattern you patch is missing, the same way this plugin does for email colours.
4. **Fork.** Last resort. Record why, and pin the upstream tag you diverged from.

## Step 6 - Record the result

Keep one row per MFE, so the next upgrade starts from evidence, not memory.

| MFE / repo @ tag | Class | Static evidence (sections) | Runtime proof done? (step 4) | Gaps | Remedy used |
|---|---|---|---|---|---|
| e.g. `frontend-app-profile @ <tag>` | A/B | A, B, C | yes / no | brand name in a message string | none / rung # |

## Worked example (evidence, not a recommendation)

The scan was run against `openedx/frontend-app-profile` (default branch, 2026-09-21). It found:
`getConfig().FAVICON_URL` and `SITE_NAME` in `src/head/Head.jsx`; the shared header and footer
components; a build-time brand package (`@edx/brand` aliased to `@openedx/brand-openedx`);
empty logo keys in `.env`; no hardcoded logo files; and one brand-name string in
`ProfilePage.messages.jsx`. By the table above that is Class B with a message-string gap.
It is a *static* result; step 4 was not performed on a running deployment.
