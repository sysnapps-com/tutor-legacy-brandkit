"""
tutor-legacy-brandkit: brand-agnostic branding for Open edX surfaces that
Paragon design tokens do not reach.

Design rule (see README "Escalation hierarchy"): asset-first, settings-first,
exception-driven. Nothing in this module names a brand; every value comes from
`BRANDKIT_*` Tutor settings and defaults to "unset", which emits nothing and so
leaves stock Open edX behaviour untouched.

Tier 2 (settings only)  -> patches/openedx-{lms,cms}-production-settings,
                           patches/mfe-lms-common-settings
Tier 1 (opt-in, baked)  -> patches/openedx-dockerfile-post-git-checkout
                           (BRANDKIT_BAKE_STATIC_ASSETS)
Tier 3 (shared ACE)     -> same Dockerfile patch (build-time recolour of the
                           shared ACE templates, with a fail-loud assertion)
Tier 4 (page/message)   -> intentionally NOT implemented; see README.
"""
from __future__ import annotations

import json
import re
import shlex
from glob import glob
from importlib import resources
from pathlib import Path

from tutor import hooks
from tutor.exceptions import TutorError

from .__about__ import __version__

PREFIX = "BRANDKIT_"

# Settings (unprefixed). Every URL/colour defaults to "" == unset == stock Open edX.
CONFIG_DEFAULTS = {
    "VERSION": __version__,
    # Per-surface switches.
    "ENABLE_LMS": True,  # legacy LMS header/footer/dashboard logo + favicon
    "ENABLE_EMAIL": True,  # ACE email logo (+ colours, if set)
    "ENABLE_MFE": True,  # MFE_CONFIG logo/favicon keys (needs tutor-mfe)
    # Assets (absolute http(s) URLs; https strongly recommended, required in practice for email).
    "LOGO_PNG_URL": "",
    "LOGO_SVG_URL": "",
    "LOGO_WHITE_SVG_URL": "",
    "LOGO_TRADEMARK_SVG_URL": "",
    "FAVICON_URL": "",
    "EMAIL_LOGO_URL": "",  # optional override of the email logo (default: LOGO_PNG_URL)
    # Colours (#RRGGBB). Consumed only by the ACE email templates (Tier 3).
    "COLOR_PRIMARY": "",
    "COLOR_SECONDARY": "",
    "COLOR_ACCENT": "",  # accepted and validated, but no v1 surface consumes it
    # Tier 1, opt-in: download LOGO_PNG_URL / FAVICON_URL into the openedx image at build time.
    "BAKE_STATIC_ASSETS": False,
}

# No whitespace, quotes, backslashes, angle brackets, backticks or '$': values end up
# inside Python string literals *and* (for baking) shell commands in a Dockerfile.
_URL_RE = re.compile(r"^https?://[^\s'\"\\<>`$]+$")
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _check_url(value: str) -> str:
    value = str(value).strip()
    if not _URL_RE.match(value):
        raise TutorError(
            f"legacy-brandkit: invalid URL {value!r}. Expected an absolute http(s) URL "
            "without whitespace, quotes, backslashes, '<', '>', backticks or '$'."
        )
    return value


def brandkit_url(value: str) -> str:
    """Validated URL rendered as a Python string literal (for settings patches)."""
    return json.dumps(_check_url(value))


def brandkit_shell_url(value: str) -> str:
    """Validated URL rendered as a single shell word (for Dockerfile RUN lines)."""
    return shlex.quote(_check_url(value))


def brandkit_color(value: str) -> str:
    """Validated '#RRGGBB' colour, upper-cased."""
    value = str(value).strip()
    if not _COLOR_RE.match(value):
        raise TutorError(f"legacy-brandkit: invalid colour {value!r}; expected '#RRGGBB'.")
    return value.upper()


hooks.Filters.CONFIG_DEFAULTS.add_items(
    [(f"{PREFIX}{key}", value) for key, value in CONFIG_DEFAULTS.items()]
)

hooks.Filters.ENV_TEMPLATE_FILTERS.add_items(
    [
        ("brandkit_url", brandkit_url),
        ("brandkit_shell_url", brandkit_shell_url),
        ("brandkit_color", brandkit_color),
    ]
)

# Template root only so patches can {% include %} shared partials. We ship no
# build-context files, so no ENV_TEMPLATE_TARGETS entry is needed.
hooks.Filters.ENV_TEMPLATE_ROOTS.add_item(
    str(resources.files("tutorlegacybrandkit") / "templates")
)

# Patches: one file per Tutor patch name, content is a Jinja template.
_patches_dir = Path(str(resources.files("tutorlegacybrandkit") / "patches"))
for _path in sorted(glob(str(_patches_dir / "*"))):
    with open(_path, encoding="utf-8") as _f:
        hooks.Filters.ENV_PATCHES.add_item((Path(_path).name, _f.read()))
