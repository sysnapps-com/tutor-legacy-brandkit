# Quick start: install & enable on a Verawood Tutor instance

For a production/staging instance already running Tutor on the Verawood release line.
Assumes `tutor` is on `$PATH` and `TUTOR_ROOT` is already set up for this instance.

## 1. Install the plugin

```bash
pip install /path/to/tutor_legacy_brandkit-0.1.0-py3-none-any.whl
tutor plugins list | grep brandkit        # confirm it's discovered
tutor plugins enable legacy-brandkit
```

## 2. Set the branding (HGI/IDLT values)

```bash
bash heritage-operator-config.sh
```

This sets the logo (PNG + SVG variants), favicon, and the three brand colors. It prints a
reminder of the next steps (below). If you'd rather set values by hand, see the settings
table in `README.md`.

## 3. Rebuild the openedx image

Required because the email colors are applied at build time (a hex substitution in the ACE
email templates):

```bash
tutor images build openedx
```

This step needs network access to `cdn.jsdelivr.net` from wherever the image builds (your
Tutor host, or your CI runner) — the build downloads nothing by default, but do verify the
CDN URLs are reachable from that network:

```bash
curl -I https://cdn.jsdelivr.net/gh/HeritageGlobal/oedxh-theme@v1.2.0/dist/paragon/images/logo.png
curl -I https://cdn.jsdelivr.net/gh/HeritageGlobal/oedxh-theme@v1.2.0/dist/favicon.ico
```

If the build fails with `stock colour #005686 not found`, upstream changed the ACE template;
see `docs/VERIFICATION.md` and run `scripts/check-platform-assumptions.sh` against your
platform checkout before proceeding.

## 4. Restart

```bash
tutor local restart
```

(Use `tutor k8s restart` instead if this is a Kubernetes deployment — the plugin's settings
patches apply the same way either way, but rebuild/restart commands differ.)

## 5. Verify

- **Legacy LMS header/footer/favicon**: open the LMS home page and the dashboard in a
  private/incognito window (to avoid a cached favicon). Confirm the new logo and favicon.
- **ACE email**: trigger a password-reset email (or any ACE-based transactional email) and
  check the logo and the button/link colors.
- **MFE logo** (if you run tutor-mfe): open an MFE (e.g. the learning app) and check the
  header logo. Then confirm the LMS is actually serving your values:
  ```bash
  curl -s "https://<your-lms-host>/api/mfe_config/v1" | python3 -m json.tool | grep -i logo
  ```
- **Site Configuration override**: if any of the above still shows the stock logo, check
  Django admin → Site Configuration for that site — a `logo_image_url` (or similar) value
  there overrides the `LOGO_URL` setting this plugin sets.

## 6. If something doesn't look right

- Check `tutor config printvalue BRANDKIT_LOGO_PNG_URL` (and the other `BRANDKIT_*` keys) to
  confirm they saved as expected.
- Re-run `tutor images build openedx` — a stale image is the most common cause of "nothing
  changed."
- See `docs/VERIFICATION.md` for what was and wasn't actually tested before you got this
  package, and `docs/THIRD_PARTY_MFE_AUDIT.md` if a specific MFE isn't picking up the branding.

## Rollback

```bash
tutor config save --unset BRANDKIT_LOGO_PNG_URL --unset BRANDKIT_LOGO_SVG_URL \
  --unset BRANDKIT_LOGO_WHITE_SVG_URL --unset BRANDKIT_LOGO_TRADEMARK_SVG_URL \
  --unset BRANDKIT_FAVICON_URL --unset BRANDKIT_COLOR_PRIMARY \
  --unset BRANDKIT_COLOR_SECONDARY --unset BRANDKIT_COLOR_ACCENT
tutor images build openedx    # only needed if colors were set
tutor local restart
```

Or simply `tutor plugins disable legacy-brandkit` and rebuild/restart — every setting this
plugin touches falls back to stock Open edX values.
