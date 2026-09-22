"""
Integration tests for tutor-legacy-brandkit.

These drive the *real* Tutor CLI (whatever `tutor` is installed alongside this
interpreter) against a throw-away TUTOR_ROOT, then inspect the files Tutor renders.

What they DO verify:  plugin discovery, config defaults, patch rendering, input
validation, and (by exec'ing the fully rendered LMS settings file against a stub of
`lms.envs.production`) the resulting Django setting values and patch ordering.

What they can NOT verify (no edx-platform runtime here): that Mako/Django templates
render, that the LMS actually serves the logo, that ACE emails contain it. See
docs/VERIFICATION.md.
"""
from __future__ import annotations

import builtins
import os
import re
import subprocess
import sys
import tempfile
import types
from unittest import mock
from pathlib import Path

import pytest

TUTOR = str(Path(sys.executable).parent / "tutor")
CDN = "https://assets.example.org/brand"
LMS_ROOT = "https://lms.example.org"
# What Tutor itself sets (partials/common_lms.py) when the operator configures nothing.
TUTOR_STOCK_EMAIL_LOGO = LMS_ROOT + "/theming/asset/images/logo.png"
FULL = {
    "BRANDKIT_LOGO_PNG_URL": f"{CDN}/logo.png",
    "BRANDKIT_LOGO_SVG_URL": f"{CDN}/logo.svg",
    "BRANDKIT_LOGO_WHITE_SVG_URL": f"{CDN}/logo-white.svg",
    "BRANDKIT_LOGO_TRADEMARK_SVG_URL": f"{CDN}/logo-tm.svg",
    "BRANDKIT_FAVICON_URL": f"{CDN}/favicon.ico",
    "BRANDKIT_COLOR_PRIMARY": "#112233",
    "BRANDKIT_COLOR_SECONDARY": "#445566",
    "BRANDKIT_COLOR_ACCENT": "#778899",
}


def tutor(root: Path, *args: str, check: bool = True):
    env = dict(os.environ, TUTOR_ROOT=str(root), TUTOR_PLUGINS_ROOT=str(root / "plugins"))
    proc = subprocess.run([TUTOR, *args], env=env, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"tutor {' '.join(args)} failed:\n{proc.stdout}\n{proc.stderr}")
    return proc


def configure(root: Path, **settings: str):
    tutor(root, "plugins", "enable", "legacy-brandkit")
    args = ["config", "save"]
    for key, value in settings.items():
        args += ["--set", f"{key}={value}"]
    return tutor(root, *args)


@pytest.fixture()
def root(tmp_path):
    (tmp_path / "plugins").mkdir()
    return tmp_path


def block(text: str) -> str:
    """Concatenate every brandkit-managed block of a rendered file."""
    return "\n".join(re.findall(r">>> tutor-legacy-brandkit >>>.*?<<< tutor-legacy-brandkit <<<", text, re.S))


class _Platform(dict):
    """
    Module-level namespace for exec'ing the rendered settings file.

    Names the real platform base (`lms.envs.production`) would have defined are unknown
    here, so any name that is neither assigned nor a builtin resolves to a permissive
    mock. Everything the plugin (or Tutor/tutor-mfe) assigns is a REAL value, and that is
    all the assertions below look at.
    """

    def __missing__(self, key):
        if hasattr(builtins, key):
            raise KeyError(key)
        return mock.MagicMock(name=key)


def exec_lms_settings(root: Path, stock: dict | None = None) -> dict:
    """Exec the fully rendered LMS production settings against a stub platform base."""
    path = root / "env/apps/openedx/settings/lms/production.py"
    src = path.read_text().replace("from lms.envs.production import *", "")
    scratch = tempfile.mkdtemp()
    ns = _Platform(
        __file__=str(path), DATA_DIR=scratch, MEDIA_ROOT=scratch, LOG_DIR=scratch, STATIC_ROOT=scratch,
        ORA2_FILEUPLOAD_ROOT=scratch,
        LMS_ROOT_URL=LMS_ROOT,
        # Simulate the platform's frozen import-time copy (NOTIFICATION_DIGEST_LOGO = DEFAULT_EMAIL_LOGO_URL).
        # DEFAULT_EMAIL_LOGO_URL itself is reassigned by Tutor's own common_lms.py.
        NOTIFICATION_DIGEST_LOGO="https://stock.example/logo.png",
        LOGO_URL=None, LOGO_URL_PNG=None, LOGO_TRADEMARK_URL=None, FAVICON_URL=None,
    )
    ns.update(stock or {})
    with mock.patch.dict(sys.modules, _platform_module_stubs()):
        exec(compile(src, "rendered-lms-production.py", "exec"), {"__name__": "rendered"}, ns)  # noqa: S102
    return ns


def _platform_module_stubs() -> dict:
    """Stand-ins for platform/Django modules the rendered settings import at top level."""
    def mod(name, **attrs):
        m = types.ModuleType(name)
        m.__dict__.update(attrs)
        return m

    class _W(DeprecationWarning):
        pass

    jail_code = mod("codejail.jail_code", configure=lambda *a, **k: None, COMMANDS={})
    codejail = mod("codejail", jail_code=jail_code)  # `import codejail.jail_code` binds `codejail`
    return {
        "xmodule": mod("xmodule"),
        "xmodule.modulestore": mod("xmodule.modulestore"),
        "xmodule.modulestore.modulestore_settings": mod(
            "xmodule.modulestore.modulestore_settings", update_module_store_settings=lambda *a, **k: None
        ),
        "codejail": codejail,
        "codejail.jail_code": jail_code,
        "django": mod("django"),
        "django.utils": mod("django.utils"),
        "django.utils.deprecation": mod(
            "django.utils.deprecation", RemovedInDjango50Warning=_W, RemovedInDjango51Warning=_W
        ),
    }


# ---------------------------------------------------------------- discovery & defaults
def test_plugin_discovered_and_enabled(root):
    assert "legacy-brandkit" in tutor(root, "plugins", "list").stdout
    tutor(root, "plugins", "enable", "legacy-brandkit")
    listing = tutor(root, "plugins", "list").stdout
    assert re.search(r"legacy-brandkit\s+\S*\s*enabled", listing)


def test_defaults_are_unset_and_generic(root):
    configure(root)
    assert tutor(root, "config", "printvalue", "BRANDKIT_ENABLE_LMS").stdout.strip() == "true"
    assert tutor(root, "config", "printvalue", "BRANDKIT_LOGO_PNG_URL").stdout.strip() == ""
    assert tutor(root, "config", "printvalue", "BRANDKIT_BAKE_STATIC_ASSETS").stdout.strip() == "false"


def test_unset_emits_nothing(root):
    configure(root)
    rendered = block((root / "env/apps/openedx/settings/lms/production.py").read_text())
    assert not re.search(r"^(LOGO_URL|LOGO_TRADEMARK_URL|FAVICON_URL|MFE_CONFIG|DEFAULT_EMAIL|LOGO_URL_PNG)", rendered, re.M)
    assert "brandkit" not in (root / "env/build/openedx/Dockerfile").read_text().lower()


def test_no_hardcoded_brand_values_in_package():
    """Generic guard: the only hex colour allowed in shipped code is the *stock* upstream one we replace,
    and no shipped file may contain a concrete asset URL (patches take everything from settings)."""
    pkg = Path(__file__).parents[1] / "src"
    files = [p for p in pkg.rglob("*") if p.is_file() and p.suffix != ".pyc"]
    text = "\n".join(p.read_text() for p in files)
    colours = {c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}\b", text)}
    assert colours <= {"#005686"}, f"unexpected hard-coded colours: {colours}"
    urls = re.findall(r"https?://[^\s\"'`)>]+", text)
    assert not urls, f"unexpected hard-coded URLs: {urls}"


# ---------------------------------------------------------------- settings semantics
def test_full_config_sets_expected_django_settings(root):
    configure(root, **FULL)
    ns = exec_lms_settings(root)
    assert ns["LOGO_URL"] == FULL["BRANDKIT_LOGO_PNG_URL"]  # PNG preferred for legacy header
    assert ns["LOGO_TRADEMARK_URL"] == FULL["BRANDKIT_LOGO_TRADEMARK_SVG_URL"]
    assert ns["FAVICON_URL"] == FULL["BRANDKIT_FAVICON_URL"]
    for name in ("LOGO_URL_PNG_FOR_EMAIL", "DEFAULT_EMAIL_LOGO_URL", "NOTIFICATION_DIGEST_LOGO"):
        assert ns[name] == FULL["BRANDKIT_LOGO_PNG_URL"], name


def test_frozen_notification_digest_logo_is_overridden(root):
    """The stock NOTIFICATION_DIGEST_LOGO is a frozen copy; the plugin must replace it explicitly."""
    configure(root, **FULL)
    assert exec_lms_settings(root)["NOTIFICATION_DIGEST_LOGO"] != "https://stock.example/logo.png"


def test_svg_only_falls_back_for_header_but_leaves_email_stock(root):
    configure(root, BRANDKIT_LOGO_SVG_URL=f"{CDN}/logo.svg")
    ns = exec_lms_settings(root)
    assert ns["LOGO_URL"] == f"{CDN}/logo.svg"
    assert ns["LOGO_TRADEMARK_URL"] == f"{CDN}/logo.svg"
    assert ns["DEFAULT_EMAIL_LOGO_URL"] == TUTOR_STOCK_EMAIL_LOGO  # untouched: no PNG supplied
    assert "LOGO_URL_PNG_FOR_EMAIL" not in ns


def test_email_logo_override_wins_over_png(root):
    configure(root, BRANDKIT_LOGO_PNG_URL=f"{CDN}/logo.png", BRANDKIT_EMAIL_LOGO_URL=f"{CDN}/email.png")
    ns = exec_lms_settings(root)
    assert ns["LOGO_URL"] == f"{CDN}/logo.png"
    assert ns["LOGO_URL_PNG_FOR_EMAIL"] == f"{CDN}/email.png"


def test_mfe_config_keys_written_after_tutor_mfe_defaults(root):
    pytest.importorskip("tutormfe")
    configure(root, **FULL)
    cfg = exec_lms_settings(root)["MFE_CONFIG"]
    assert cfg["LOGO_URL"] == FULL["BRANDKIT_LOGO_SVG_URL"]
    assert cfg["LOGO_WHITE_URL"] == FULL["BRANDKIT_LOGO_WHITE_SVG_URL"]
    assert cfg["LOGO_TRADEMARK_URL"] == FULL["BRANDKIT_LOGO_TRADEMARK_SVG_URL"]
    assert cfg["FAVICON_URL"] == FULL["BRANDKIT_FAVICON_URL"]
    assert "LOGOUT_URL" in cfg  # tutor-mfe's own keys are preserved


def test_per_surface_switches(root):
    configure(root, BRANDKIT_ENABLE_LMS="false", BRANDKIT_ENABLE_EMAIL="false", BRANDKIT_ENABLE_MFE="false", **FULL)
    ns = exec_lms_settings(root)
    assert ns["LOGO_URL"] is None and ns["FAVICON_URL"] is None
    assert ns["DEFAULT_EMAIL_LOGO_URL"] == TUTOR_STOCK_EMAIL_LOGO
    if "MFE_CONFIG" in ns:
        assert ns["MFE_CONFIG"]["LOGO_URL"] != FULL["BRANDKIT_LOGO_SVG_URL"]
    assert "brandkit" not in (root / "env/build/openedx/Dockerfile").read_text().lower()


def test_cms_gets_email_logo_only(root):
    configure(root, **FULL)
    rendered = block((root / "env/apps/openedx/settings/cms/production.py").read_text())
    assert f'DEFAULT_EMAIL_LOGO_URL = "{FULL["BRANDKIT_LOGO_PNG_URL"]}"' in rendered
    assert "LOGO_URL =" not in rendered.replace("EMAIL_LOGO_URL", "").replace("LOGO_URL_PNG_FOR_EMAIL", "")


# ---------------------------------------------------------------- validation
@pytest.mark.parametrize(
    "key,value",
    [
        ("BRANDKIT_LOGO_PNG_URL", "javascript:alert(1)"),
        ("BRANDKIT_LOGO_PNG_URL", 'https://x.example/a"; import os #'),
        ("BRANDKIT_LOGO_PNG_URL", "https://x.example/a b.png"),
        ("BRANDKIT_LOGO_PNG_URL", "https://x.example/$(id).png"),
        ("BRANDKIT_LOGO_PNG_URL", "/relative/logo.png"),
        ("BRANDKIT_COLOR_PRIMARY", "red"),
        ("BRANDKIT_COLOR_PRIMARY", "#12345"),
        ("BRANDKIT_COLOR_PRIMARY", "#123456|;rm -rf /"),
    ],
)
def test_invalid_values_are_rejected_loudly(root, key, value):
    tutor(root, "plugins", "enable", "legacy-brandkit")
    proc = tutor(root, "config", "save", "--set", f"{key}={value}", check=False)
    assert proc.returncode != 0
    assert "legacy-brandkit" in (proc.stdout + proc.stderr)


def test_invalid_value_can_be_fixed_afterwards(root):
    tutor(root, "plugins", "enable", "legacy-brandkit")
    assert tutor(root, "config", "save", "--set", "BRANDKIT_COLOR_PRIMARY=red", check=False).returncode != 0
    assert tutor(root, "config", "save", "--set", "BRANDKIT_COLOR_PRIMARY=#112233", check=False).returncode == 0


# ---------------------------------------------------------------- Dockerfile (Tier 1 / 3)
def _brandkit_run_blocks(dockerfile: str) -> list[str]:
    """Return each brandkit RUN instruction, joined into one shell line."""
    out = []
    for m in re.finditer(r"^# tutor-legacy-brandkit:[^\n]*\n(?:#[^\n]*\n)*(RUN .*?)(?=\n\n|\n#)", dockerfile, re.S | re.M):
        out.append(re.sub(r"\\\n\s*", " ", m.group(1))[len("RUN "):])
    return out


def test_dockerfile_colour_step_only_when_colours_set(root):
    configure(root, BRANDKIT_LOGO_PNG_URL=f"{CDN}/logo.png")
    assert "recolor" not in (root / "env/build/openedx/Dockerfile").read_text()
    configure(root, BRANDKIT_COLOR_PRIMARY="#112233")
    df = (root / "env/build/openedx/Dockerfile").read_text()
    assert "return_to_course_cta.html" in df and "#112233" in df and "base_body.html" not in df.split("recolor()")[1]


def test_bake_is_opt_in(root):
    configure(root, **FULL)
    assert "curl" not in (root / "env/build/openedx/Dockerfile").read_text().split("tutor-legacy-brandkit")[1]
    configure(root, BRANDKIT_BAKE_STATIC_ASSETS="true")
    df = (root / "env/build/openedx/Dockerfile").read_text()
    assert "lms/static/images/logo.png" in df and "lms/static/images/favicon.ico" in df


PLATFORM = os.environ.get("BRANDKIT_PLATFORM_CHECKOUT")


@pytest.mark.skipif(not PLATFORM, reason="set BRANDKIT_PLATFORM_CHECKOUT to a real edx-platform checkout")
def test_recolor_step_against_real_platform_templates(root, tmp_path):
    """Run the rendered Dockerfile shell against real upstream templates."""
    import shutil

    work = tmp_path / "platform"
    ace = "openedx/core/djangoapps/ace_common/templates/ace_common/edx_ace/common"
    (work / ace).mkdir(parents=True)
    for name in ("base_body.html", "return_to_course_cta.html"):
        shutil.copy(Path(PLATFORM) / ace / name, work / ace / name)
    configure(root, BRANDKIT_COLOR_PRIMARY="#AA1122", BRANDKIT_COLOR_SECONDARY="#2233BB")
    (cmd,) = _brandkit_run_blocks((root / "env/build/openedx/Dockerfile").read_text())
    proc = subprocess.run(["sh", "-c", cmd], cwd=work, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    cta = (work / ace / "return_to_course_cta.html").read_text().lower()
    body = (work / ace / "base_body.html").read_text().lower()
    assert "#005686" not in cta and "#005686" not in body
    assert cta.count("#aa1122") == 5 and body.count("#2233bb") == 2
    # Upstream drift must fail loudly: run again on already-recoloured files.
    proc = subprocess.run(["sh", "-c", cmd], cwd=work, capture_output=True, text=True)
    assert proc.returncode != 0 and "upstream template changed" in proc.stderr


# ---------------------------------------------------------------- Tier 1 baking, run for real
@pytest.fixture()
def asset_server(tmp_path):
    """Serve tiny but genuine PNG / ICO / SVG payloads on localhost."""
    import http.server
    import threading

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    ico = b"\x00\x00\x01\x00" + b"\x00" * 32
    svg = b"<svg xmlns='http://www.w3.org/2000/svg'/>"
    served = tmp_path / "www"
    served.mkdir()
    (served / "logo.png").write_bytes(png)
    (served / "favicon.ico").write_bytes(ico)
    (served / "not-a-png.png").write_bytes(svg)
    (served / "not-an-ico.ico").write_bytes(svg)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(served), **k)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", png, ico
    srv.shutdown()


def _run_bake(root, tmp_path, **settings):
    work = tmp_path / "checkout"
    work.mkdir(exist_ok=True)
    configure(root, BRANDKIT_BAKE_STATIC_ASSETS="true", **settings)
    cmds = _brandkit_run_blocks((root / "env/build/openedx/Dockerfile").read_text())
    return work, [subprocess.run(["sh", "-c", c], cwd=work, capture_output=True, text=True) for c in cmds]


def test_bake_downloads_and_installs_assets(root, tmp_path, asset_server):
    base, png, ico = asset_server
    work, results = _run_bake(root, tmp_path, BRANDKIT_LOGO_PNG_URL=f"{base}/logo.png", BRANDKIT_FAVICON_URL=f"{base}/favicon.ico")
    assert len(results) == 2 and all(r.returncode == 0 for r in results), [r.stderr for r in results]
    assert (work / "lms/static/images/logo.png").read_bytes() == png
    assert (work / "lms/static/images/favicon.ico").read_bytes() == ico


@pytest.mark.parametrize(
    "key,path,msg",
    [
        ("BRANDKIT_LOGO_PNG_URL", "not-a-png.png", "did not return a PNG"),
        ("BRANDKIT_LOGO_PNG_URL", "missing.png", None),  # HTTP 404 -> curl -f fails
        ("BRANDKIT_FAVICON_URL", "not-an-ico.ico", "did not return an .ico"),
    ],
)
def test_bake_fails_the_build_on_wrong_content(root, tmp_path, asset_server, key, path, msg):
    base, *_ = asset_server
    work, results = _run_bake(root, tmp_path, **{key: f"{base}/{path}"})
    assert results and results[0].returncode != 0
    if msg:
        assert msg in results[0].stderr
    assert not (work / "lms/static/images/logo.png").exists() and not (work / "lms/static/images/favicon.ico").exists()
