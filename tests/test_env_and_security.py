import pytest
from app.config import Settings, settings

def test_config_defaults():
    """Verify that the new URL defaults are correctly configured."""
    s = Settings()
    assert s.PUBLIC_BASE_URL == "https://db.konfix.sduni.de"
    assert s.SCHEMA_URL == "https://db.konfix.sduni.de/schemas/konfix-device-v1.json"
    assert s.APP_NAME == "KoNfiX-Database"
    assert s.LEGAL_CONTACT_EMAIL == "legal@konfix.sduni.de"

def test_env_precedence_over_defaults(monkeypatch):
    """Verify that environment variables (.env / OS) override Settings defaults."""
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://staging.konfix.sduni.de")
    monkeypatch.setenv("ADMIN_KEY", "custom-super-secret-key-999")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "104857600")

    custom_settings = Settings()
    assert custom_settings.PUBLIC_BASE_URL == "https://staging.konfix.sduni.de"
    assert custom_settings.ADMIN_KEY == "custom-super-secret-key-999"
    assert custom_settings.MAX_UPLOAD_SIZE_BYTES == 104857600

def test_admin_protection_enforced_when_admin_key_set(client, monkeypatch):
    """
    Verify that when ADMIN_KEY is configured in .env / settings:
    - Destructive operations (DELETE, batch delete, unauthenticated PATCH) require authentication (401).
    - Operations succeed with valid X-API-Key or Bearer token.
    """
    secret = "production-admin-key-xyz"
    monkeypatch.setattr(settings, "ADMIN_KEY", secret)

    # 1. Setup a dummy device
    yaml_payload = """konfix_version: '1.0'
manufacturer:
  code: mdttest
  name: MDT Test
device:
  order_number: SEC-DEV-01
  name: Sicherheits-Aktor
application:
  id: mdttest_sec_v1
  name: Sec App
"""
    res_up = client.post(
        "/api/v1/upload/yaml",
        content=yaml_payload,
        headers={"Content-Type": "text/yaml"}
    )
    assert res_up.status_code == 201

    # 2. DELETE without key must return 401
    del_fail = client.delete("/api/v1/devices/SEC-DEV-01")
    assert del_fail.status_code == 401

    # 3. Batch delete without key must return 401
    batch_fail = client.post(
        "/api/v1/devices/batch-delete",
        json={"order_numbers": ["SEC-DEV-01"]}
    )
    assert batch_fail.status_code == 401

    # 4. PATCH without edit_code or admin key must return 401
    patch_fail = client.patch(
        "/api/v1/devices/SEC-DEV-01",
        json={"name": "Geänderter Name"}
    )
    assert patch_fail.status_code == 401

    # 5. Operations succeed with X-API-Key
    patch_ok = client.patch(
        "/api/v1/devices/SEC-DEV-01",
        json={"name": "Admin Name"},
        headers={"X-API-Key": secret}
    )
    assert patch_ok.status_code == 200
    assert patch_ok.json()["name"] == "Admin Name"

    # 6. DELETE with Authorization: Bearer succeeds
    del_ok = client.delete(
        "/api/v1/devices/SEC-DEV-01",
        headers={"Authorization": f"Bearer {secret}"}
    )
    assert del_ok.status_code == 200

def test_private_upload_mode_requires_admin_key(client, monkeypatch):
    """
    Verify that when ALLOW_PUBLIC_UPLOAD=false is set in .env / settings:
    - Upload without admin key is rejected (401).
    - Upload with admin key succeeds (201).
    """
    secret = "admin-secret-777"
    monkeypatch.setattr(settings, "ADMIN_KEY", secret)
    monkeypatch.setattr(settings, "ALLOW_PUBLIC_UPLOAD", False)

    yaml_payload = """konfix_version: '1.0'
manufacturer:
  code: mdttest
  name: MDT Test
device:
  order_number: PRIV-DEV-01
  name: Privater Aktor
application:
  id: mdttest_priv_v1
  name: Priv App
"""
    # Without admin key -> 401
    res_fail = client.post(
        "/api/v1/upload/yaml",
        content=yaml_payload,
        headers={"Content-Type": "text/yaml"}
    )
    assert res_fail.status_code == 401

    # With admin key -> 201
    res_ok = client.post(
        "/api/v1/upload/yaml",
        content=yaml_payload,
        headers={"Content-Type": "text/yaml", "X-API-Key": secret}
    )
    assert res_ok.status_code == 201


def test_admin_mode_default_off_when_key_empty(client, monkeypatch):
    """
    Verify that when ADMIN_KEY is empty / not configured:
    - Admin mode is strictly OFF by default (is_admin=False).
    - GET /api/v1/auth/verify returns status='unconfigured' and is_admin=False.
    - Calling DELETE on any device returns 401 Unauthorized.
    """
    monkeypatch.setattr(settings, "ADMIN_KEY", "")
    monkeypatch.setattr(settings, "API_KEY", "")

    from app.api.v1.auth import is_admin_authenticated
    assert is_admin_authenticated() is False
    assert is_admin_authenticated(x_api_key="any-random-key") is False

    res = client.get("/api/v1/auth/verify")
    assert res.status_code == 200
    data = res.json()
    assert data["is_admin"] is False
    assert data["status"] == "unconfigured"

    # Attempt delete -> 401
    res_del = client.delete("/api/v1/devices/NONEXISTENT-99")
    assert res_del.status_code == 401

