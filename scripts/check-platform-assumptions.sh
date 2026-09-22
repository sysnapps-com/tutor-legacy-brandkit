#!/usr/bin/env bash
# check-platform-assumptions.sh -- verify the upstream facts this plugin relies on.
#
# Usage:  scripts/check-platform-assumptions.sh /path/to/openedx-platform
#         (a full or sparse checkout of the release tag you are about to run)
#
# Run it for each new Open edX release BEFORE trusting the plugin there. Every line prints
# PASS / FAIL. It reads source only; it cannot prove runtime behaviour.
set -u
root="${1:-}"; [ -d "${root:-/nonexistent}" ] || { echo "usage: $0 /path/to/openedx-platform" >&2; exit 2; }
cd "$root" || exit 2
fail=0
check() { # description, command...
  local d="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "PASS  $d"; else echo "FAIL  $d"; fail=1; fi
}
# Settings live in openedx/envs/common.py on recent releases and lms/envs/common.py on older ones.
SETTINGS="openedx/envs/common.py lms/envs/common.py"
API=lms/djangoapps/branding/api.py
ACE=openedx/core/djangoapps/ace_common/templates/ace_common/edx_ace/common

echo "== Tier 2 settings the plugin writes"
check "LOGO_URL setting exists"                     grep -qE "^LOGO_URL *=" $SETTINGS
check "LOGO_TRADEMARK_URL setting exists"           grep -qE "^LOGO_TRADEMARK_URL *=" $SETTINGS
check "FAVICON_URL setting exists"                  grep -qE "^FAVICON_URL *=" $SETTINGS
check "DEFAULT_EMAIL_LOGO_URL setting exists"       grep -qE "^DEFAULT_EMAIL_LOGO_URL *=" $SETTINGS
check "NOTIFICATION_DIGEST_LOGO frozen copy exists (plugin must set it explicitly)" \
      grep -qE "^NOTIFICATION_DIGEST_LOGO *= *DEFAULT_EMAIL_LOGO_URL" $SETTINGS

echo "== How they are consumed"
check "header logo reads settings.LOGO_URL"         grep -q "brand_logo_url = settings.LOGO_URL" $API
check "footer logo reads settings.LOGO_TRADEMARK_URL" grep -q "settings.LOGO_TRADEMARK_URL" $API
check "favicon reads settings.FAVICON_URL"          grep -q "settings.FAVICON_URL" $API
check "email logo precedence FOR_EMAIL -> LOGO_URL_PNG -> DEFAULT (in that order)" \
      bash -c "sed -n '/def get_logo_url_for_email/,/^def /p' $API | tr -d '\n' | grep -qE \"LOGO_URL_PNG_FOR_EMAIL.*LOGO_URL_PNG'.*default_logo_url\""
check "legacy dashboard has no logo of its own (inherits main.html)" \
      bash -c "! grep -qiE 'logo' lms/templates/dashboard.html"

echo "== Tier 3 (email colours): stock colour the build-time recolour needs"
check "return_to_course_cta.html still contains #005686" grep -qi "#005686" $ACE/return_to_course_cta.html
check "base_body.html still contains #005686"            grep -qi "#005686" $ACE/base_body.html
check "base_body.html still reads {{ logo_url }}"         grep -q "{{ *logo_url *}}" $ACE/base_body.html

echo "== Tier 1 (opt-in baking): static paths"
check "FAVICON_PATH default is images/favicon.ico"  grep -qE "^FAVICON_PATH *= *'images/favicon.ico'" $SETTINGS
check "lms/static/images/logo.png exists"           test -f lms/static/images/logo.png
check "/theming/asset/<path> route exists (themed_asset view)" grep -q "themed_asset" openedx/core/djangoapps/theming/urls.py
check "themed_asset redirects (302), it does not serve bytes"   grep -q "HttpResponseRedirect\|redirect(" openedx/core/djangoapps/theming/views.py

[ $fail -eq 0 ] && echo && echo "All assumptions hold for this checkout." || { echo; echo "One or more assumptions FAILED: review the plugin for this release before use."; }
exit $fail
