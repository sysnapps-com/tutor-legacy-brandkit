#!/usr/bin/env bash
# audit-mfe-branding.sh -- READ-ONLY audit of one MFE source tree for branding surfaces.
#
# Usage:  scripts/audit-mfe-branding.sh /path/to/frontend-app-something
#
# It does NOT change anything and does NOT decide for you. It gathers evidence for the
# checklist in docs/THIRD_PARTY_MFE_AUDIT.md and prints a *hint* classification. Read the
# hits: grep proves a string exists, not that the code path is live.
set -u

root="${1:-}"
if [ -z "$root" ] || [ ! -d "$root" ]; then
  echo "usage: $0 /path/to/mfe-source-tree" >&2
  exit 2
fi
cd "$root" || exit 2

EXCL=(--exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.git --exclude-dir=coverage \
      --exclude-dir=transifex_input --exclude-dir=__mocks__ --exclude=package-lock.json --exclude='*.map' \
      --exclude='*.snap' --exclude='*.test.*' --exclude='*.spec.*')
g() { grep -rInE "${EXCL[@]}" "$@" 2>/dev/null; }
section() { printf '\n=== %s\n' "$1"; }
count() { local n; n=$(printf '%s' "$1" | grep -c .); echo "$n"; }

echo "MFE audit: $(pwd)"
[ -f package.json ] && grep -E '"(name|version)"' package.json | head -2

section "A. Standard runtime config consumption (GOOD: operator can brand via MFE_CONFIG)"
A=$(g "(getConfig\(\)|from '@(edx|openedx)/frontend-platform)" src | head -200)
A_KEYS=$(g "\b(LOGO_URL|LOGO_WHITE_URL|LOGO_TRADEMARK_URL|FAVICON_URL|headerLogoImageUrl|SITE_NAME)\b" src public .env* 2>/dev/null | head -60)
echo "frontend-platform imports / getConfig() usages: $(count "$A")"
echo "$A_KEYS"

section "B. Shared header/footer components (they read LOGO_URL etc. themselves)"
B=$(g "@(edx|openedx)/(frontend-component-(header|footer)|frontend-base)" package.json src | head -40)
echo "$B"

section "C. Brand package (build-time; needs an MFE image rebuild to change)"
C=$(g "@(edx|openedx)/brand|brand-openedx|brand/paragon|@edx/brand" package.json src webpack*.js .env* 2>/dev/null | head -40)
echo "$C"

section "D. Hardcoded logo / image assets inside src or public"
D1=$(find src public -type f \( -iname '*logo*' -o -iname '*brand*' -o -iname 'favicon*' \) \
      -not -path '*/node_modules/*' 2>/dev/null | head -40)
echo "files named like logo/brand/favicon:"; echo "$D1"
D2=$(g "(import [^;]*(logo|brand)[^;]*\.(svg|png|jpe?g|ico)['\"]|<img[^>]*(logo|brand)|url\([^)]*(logo|brand))" src | head -40)
echo "imports/uses of image assets that look like branding:"; echo "$D2"

section "E. Hardcoded remote branding (edx.org / openedx.org / CDN URLs)"
echo "(.env.development / .env.test values are dev/test-only defaults and not shipped to production; judge only src/, public/ and .env)"
E=$(g "(edx-cdn\.org|edx\.org|openedx\.org|edx\.readthedocs)" src public .env 2>/dev/null | grep -v "^src/i18n" | head -40)
echo "$E"

section "F. Browser-tab surfaces: <title>, favicon links, manifest"
F=$(g "(<title>|rel=\"(shortcut )?icon\"|rel=\"apple-touch-icon\"|favicon|manifest)" public webpack*.js 2>/dev/null | head -20)
echo "$F"

section "G. .env* defaults that carry branding keys"
G=$(g "^(LOGO|FAVICON|SITE_NAME|APP_ID|MARKETING_SITE_BASE_URL|TERMS_OF_SERVICE_URL|PRIVACY_POLICY_URL)" .env .env.development .env.test 2>/dev/null | head -20)
echo "$G"

section "H. Brand name inside translatable strings (needs an i18n/message override to change)"
H=$(g "(Open edX|edX|edx\.org)" src --include=messages.js --include=messages.jsx --include=messages.ts 2>/dev/null | head -20)
echo "$H"

section "HINT classification (verify manually)"
if [ -n "$B" ] || [ -n "$A_KEYS" ]; then
  echo "* Reads standard config or uses shared header/footer -> LIKELY brandable via MFE_CONFIG (LOGO_URL, LOGO_WHITE_URL, LOGO_TRADEMARK_URL, FAVICON_URL). Confirm at runtime."
fi
if [ -n "$C" ]; then
  echo "* References a brand package -> parts of the look are BUILD-TIME; changing them means an MFE image rebuild."
fi
if [ -n "$D1$D2$E" ]; then
  echo "* Has hardcoded logo files / remote URLs -> those spots are NOT reachable by any plugin setting; they need a source patch or fork."
fi
if [ -z "$B$A_KEYS$C$D1$D2$E" ]; then
  echo "* No branding signals found. Confirm you pointed at the MFE root (src/, public/, package.json)."
fi
echo
echo "Next: open docs/THIRD_PARTY_MFE_AUDIT.md and answer the runtime checks (step 4-5) in a browser; static grep alone is not proof."
