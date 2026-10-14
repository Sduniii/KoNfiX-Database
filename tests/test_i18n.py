import json
import re
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_i18n_static_file_served(client):
    """Test that /static/i18n.js is served with correct headers and content."""
    response = client.get("/static/i18n.js")
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "").lower()
    content = response.text
    assert "const I18N_TRANSLATIONS" in content
    assert "const I18n =" in content
    assert "window.I18n = I18n" in content


def test_css_contains_language_switcher_styles(client):
    """Test that style.css contains styles for the language switch component."""
    response = client.get("/static/style.css")
    assert response.status_code == 200
    css = response.text
    assert ".lang-switch" in css
    assert ".lang-btn" in css
    assert ".lang-btn.active" in css


def test_index_html_includes_i18n_and_language_switch(client):
    """Test that index.html contains language switch UI and i18n script inclusion."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # Script tag ordering: i18n.js must be included before app.js
    i18n_idx = html.find('src="/static/i18n.js"')
    app_idx = html.find('src="/static/app.js"')
    assert i18n_idx != -1, "i18n.js is not included in index.html"
    assert app_idx != -1, "app.js is not included in index.html"
    assert i18n_idx < app_idx, "i18n.js must be included before app.js"

    # Language switcher markup
    assert 'id="langSwitch"' in html
    assert 'data-lang="de"' in html
    assert 'data-lang="en"' in html

    # data-i18n attributes present in template
    assert "data-i18n=" in html
    assert "data-i18n-placeholder=" in html


def test_csp_header_strict_no_unsafe_inline(client):
    """Verify that Content-Security-Policy remains strict without unsafe-inline in script-src."""
    response = client.get("/")
    assert response.status_code == 200
    csp = response.headers.get("content-security-policy", "")
    assert csp, "Content-Security-Policy header is missing"

    directives = [d.strip() for d in csp.split(";") if d.strip()]
    script_src = [d for d in directives if d.startswith("script-src")]
    assert script_src, "script-src directive not found in CSP header"
    assert "script-src 'self'" in script_src[0]
    assert "'unsafe-inline'" not in script_src[0]


def _load_translations_via_node():
    """Extract I18N_TRANSLATIONS dictionary from i18n.js using Node."""
    js_cmd = (
        "const { I18N_TRANSLATIONS } = require('./app/static/i18n.js');"
        "console.log(JSON.stringify(I18N_TRANSLATIONS));"
    )
    result = subprocess.run(
        ["node", "-e", js_cmd],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).parent.parent
    )
    return json.loads(result.stdout)


def _get_all_keys(d, prefix=""):
    """Recursively collect dotted key paths and their values."""
    keys = {}
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(_get_all_keys(v, full_key))
        else:
            keys[full_key] = v
    return keys


def test_translation_symmetry_between_de_and_en():
    """Verify 100% symmetrical dictionary coverage between German and English."""
    translations = _load_translations_via_node()
    assert "de" in translations
    assert "en" in translations

    de_keys = _get_all_keys(translations["de"])
    en_keys = _get_all_keys(translations["en"])

    missing_in_en = set(de_keys.keys()) - set(en_keys.keys())
    missing_in_de = set(en_keys.keys()) - set(de_keys.keys())

    assert not missing_in_en, f"Keys present in DE but missing in EN: {missing_in_en}"
    assert not missing_in_de, f"Keys present in EN but missing in DE: {missing_in_de}"

    # Verify no empty translation strings
    for k, v in de_keys.items():
        assert isinstance(v, str) and len(v.strip()) > 0, f"Empty DE translation for key '{k}'"
    for k, v in en_keys.items():
        assert isinstance(v, str) and len(v.strip()) > 0, f"Empty EN translation for key '{k}'"

    # Verify matching interpolation placeholders (e.g., {count}, {order})
    placeholder_pattern = re.compile(r"\{([a-zA-Z0-9_]+)\}")
    for k in de_keys:
        de_placeholders = set(placeholder_pattern.findall(de_keys[k]))
        en_placeholders = set(placeholder_pattern.findall(en_keys[k]))
        assert de_placeholders == en_placeholders, (
            f"Placeholder mismatch for '{k}': DE has {de_placeholders}, EN has {en_placeholders}"
        )


def test_all_html_data_i18n_keys_exist_in_dictionaries():
    """Verify that every data-i18n* attribute used in index.html exists in both DE and EN."""
    translations = _load_translations_via_node()
    de_keys = _get_all_keys(translations["de"])
    en_keys = _get_all_keys(translations["en"])

    html_path = Path(__file__).parent.parent / "app" / "templates" / "index.html"
    html_content = html_path.read_text(encoding="utf-8")

    # Match data-i18n, data-i18n-placeholder, data-i18n-title, data-i18n-aria (exclude data-i18n-html boolean flag)
    attr_pattern = re.compile(r'data-i18n(?:-placeholder|-title|-aria)?="([^"]+)"')
    found_keys = set(attr_pattern.findall(html_content))

    assert len(found_keys) > 0, "No data-i18n attributes found in index.html"

    for key in found_keys:
        assert key in de_keys, f"Attribute key '{key}' in index.html not found in DE translations"
        assert key in en_keys, f"Attribute key '{key}' in index.html not found in EN translations"


def test_i18n_runtime_methods_via_node():
    """Test I18n runtime methods (t, interpolation, setLanguage) in Node environment."""
    test_script = """
    const { I18n } = require('./app/static/i18n.js');
    const assert = require('assert');

    // Test default language
    assert.strictEqual(I18n.getLanguage(), 'de');

    // Test basic translation
    assert.strictEqual(I18n.t('nav.yamlEditor'), '🛠️ YAML-Editor');

    // Test parameter interpolation
    const interpolatedDe = I18n.t('results.count', { count: 42 });
    assert.strictEqual(interpolatedDe, '42 Einträge');

    // Test switching to English
    I18n.currentLang = 'en';
    assert.strictEqual(I18n.t('nav.yamlEditor'), '🛠️ YAML Editor');
    const interpolatedEn = I18n.t('results.count', { count: 42 });
    assert.strictEqual(interpolatedEn, '42 entries');

    // Test fallback for non-existent key
    assert.strictEqual(I18n.t('non.existent.key'), 'non.existent.key');

    console.log('OK');
    """
    result = subprocess.run(
        ["node", "-e", test_script],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).parent.parent
    )
    assert "OK" in result.stdout


def test_branding_and_navbar_elements(client):
    """Verify that hero headline is 'für KoNfiX' (without ETS) and navbar responsive classes exist."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # Verify hero branding
    assert "für KoNfiX" in html
    assert "für KoNfiX &amp; ETS" not in html
    assert "für KoNfiX & ETS" not in html
    assert 'data-i18n="hero.titleAccent"' in html
    assert 'data-i18n="hero.subtitle"' in html

    # Verify navbar responsive classes
    assert "hidden-md" in html
    assert "hidden-sm" in html
    assert "nav-btn-text" in html

    # Verify CSS navbar fixes
    css_res = client.get("/static/style.css")
    assert css_res.status_code == 200
    css = css_res.text
    assert "min-height: 4rem" in css
    assert "flex-wrap: nowrap" in css
