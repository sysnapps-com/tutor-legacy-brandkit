{#-
  TIER 2 (settings only): ACE email logo. Shared by the LMS and CMS production patches.

  Why three settings (verified by reading openedx-platform release/ulmo.4 and
  release/verawood.1; NOT exercised in a running LMS, see docs/VERIFICATION.md):

  * lms.djangoapps.branding.api.get_logo_url_for_email() resolves, in order:
      LOGO_URL_PNG_FOR_EMAIL -> LOGO_URL_PNG -> DEFAULT_EMAIL_LOGO_URL
    so DEFAULT_EMAIL_LOGO_URL alone LOSES to any LOGO_URL_PNG set elsewhere.
    We set the highest-precedence one, and DEFAULT_EMAIL_LOGO_URL as a fallback
    for releases/consumers that read it directly.
  * NOTIFICATION_DIGEST_LOGO is assigned `= DEFAULT_EMAIL_LOGO_URL` at import time in
    the platform's common settings, so overriding DEFAULT_EMAIL_LOGO_URL later does not
    reach notification digest emails. It must be set explicitly.
  * A per-site `email_logo_url`-style value in the DB SiteConfiguration is not consulted
    by get_logo_url_for_email() in the tags we read, but treat DB site configuration as a
    possible override for anything else.
-#}
{%- set _brandkit_email_logo = BRANDKIT_EMAIL_LOGO_URL or BRANDKIT_LOGO_PNG_URL %}
{%- if BRANDKIT_ENABLE_EMAIL and _brandkit_email_logo %}
LOGO_URL_PNG_FOR_EMAIL = {{ _brandkit_email_logo | brandkit_url }}
DEFAULT_EMAIL_LOGO_URL = {{ _brandkit_email_logo | brandkit_url }}
NOTIFICATION_DIGEST_LOGO = {{ _brandkit_email_logo | brandkit_url }}
{%- endif %}
