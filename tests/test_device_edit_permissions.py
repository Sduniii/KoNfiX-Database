import pytest

SAMPLE_DEV_YAML = """konfix_version: '1.0'
manufacturer:
  code: perftest
  name: Permission Test Mfg
  legacy_knx_id: M-0088
device:
  order_number: PERM-DEV-01
  name: Berechtigungs-Testgerät
  hardware:
    name: PERM-DEV
    version: '1.0'
application:
  id: perftest_app_v1
  name: Test App
  version: '1.0'
"""

def test_device_creation_returns_edit_code(client):
    """Uploading a new device must return an edit code."""
    res = client.post(
        "/api/v1/upload/yaml",
        content=SAMPLE_DEV_YAML,
        headers={"Content-Type": "text/yaml"}
    )
    assert res.status_code == 201
    data = res.json()
    assert "edit_code" in data
    assert data["edit_code"] is not None
    assert len(data["edit_code"]) >= 8

def test_patch_without_code_or_admin_returns_401(client, monkeypatch):
    """PATCH on device without code or admin credentials returns 401."""
    from app.config import settings
    monkeypatch.setattr(settings, "ADMIN_KEY", "test-admin-secret-key")
    # First upload device
    res_up = client.post(
        "/api/v1/upload/yaml",
        content=SAMPLE_DEV_YAML,
        headers={"Content-Type": "text/yaml"}
    )
    assert res_up.status_code == 201

    # Attempt unauthenticated PATCH
    patch_res = client.patch(
        "/api/v1/devices/PERM-DEV-01",
        json={"name": "Hacked Name"}
    )
    assert patch_res.status_code == 401

def test_patch_with_invalid_code_returns_403(client):
    """PATCH on device with invalid edit_code returns 403."""
    res_up = client.post(
        "/api/v1/upload/yaml",
        content=SAMPLE_DEV_YAML,
        headers={"Content-Type": "text/yaml"}
    )
    assert res_up.status_code == 201

    patch_res = client.patch(
        "/api/v1/devices/PERM-DEV-01",
        json={"name": "Hacked Name", "edit_code": "wrong-code-123"}
    )
    assert patch_res.status_code == 403
    assert "Ungültiger oder fehlender Bearbeitungs-Code" in patch_res.json()["detail"]

def test_patch_with_valid_code_succeeds(client):
    """PATCH on device with creator's edit_code succeeds."""
    res_up = client.post(
        "/api/v1/upload/yaml",
        content=SAMPLE_DEV_YAML,
        headers={"Content-Type": "text/yaml"}
    )
    assert res_up.status_code == 201
    edit_code = res_up.json()["edit_code"]

    # 1. Test code in body
    patch_res = client.patch(
        "/api/v1/devices/PERM-DEV-01",
        json={"name": "Aktualisierter Name 1", "edit_code": edit_code}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Aktualisierter Name 1"

    # 2. Test code in header X-Edit-Code
    patch_res2 = client.patch(
        "/api/v1/devices/PERM-DEV-01",
        headers={"X-Edit-Code": edit_code},
        json={"name": "Aktualisierter Name 2"}
    )
    assert patch_res2.status_code == 200
    assert patch_res2.json()["name"] == "Aktualisierter Name 2"

def test_reupload_overwrite_permission_checks(client):
    """Re-uploading an existing device requires creator's edit_code or admin."""
    res_up = client.post(
        "/api/v1/upload/yaml",
        content=SAMPLE_DEV_YAML,
        headers={"Content-Type": "text/yaml"}
    )
    assert res_up.status_code == 201
    edit_code = res_up.json()["edit_code"]

    updated_yaml = SAMPLE_DEV_YAML.replace("Berechtigungs-Testgerät", "Neuhochgeladener Name")

    # 1. Re-upload without code -> 403 Forbidden
    res_no_code = client.post(
        "/api/v1/upload/yaml",
        content=updated_yaml,
        headers={"Content-Type": "text/yaml"}
    )
    assert res_no_code.status_code == 403
    assert "Bearbeitungs-Code" in res_no_code.json()["detail"] or "Bearbeitungscode" in res_no_code.json()["detail"]

    # 2. Re-upload with invalid code -> 403 Forbidden
    res_bad_code = client.post(
        "/api/v1/upload/yaml",
        content=updated_yaml,
        headers={
            "Content-Type": "text/yaml",
            "X-Edit-Code": "invalid-token"
        }
    )
    assert res_bad_code.status_code == 403

    # 3. Re-upload with valid code -> 200 OK
    res_good_code = client.post(
        "/api/v1/upload/yaml",
        content=updated_yaml,
        headers={
            "Content-Type": "text/yaml",
            "X-Edit-Code": edit_code
        }
    )
    assert res_good_code.status_code in (200, 201)
    assert res_good_code.json()["status"] == "success"
    assert res_good_code.json()["devices_imported"][0]["name"] == "Neuhochgeladener Name"

def test_verify_edit_code_endpoint(client):
    """Test POST /api/v1/devices/{order_number}/verify-code."""
    res_up = client.post(
        "/api/v1/upload/yaml",
        content=SAMPLE_DEV_YAML,
        headers={"Content-Type": "text/yaml"}
    )
    assert res_up.status_code == 201
    edit_code = res_up.json()["edit_code"]

    # Valid code
    res_val = client.post(
        "/api/v1/devices/PERM-DEV-01/verify-code",
        json={"edit_code": edit_code}
    )
    assert res_val.status_code == 200
    assert res_val.json()["valid"] is True

    # Invalid code
    res_inval = client.post(
        "/api/v1/devices/PERM-DEV-01/verify-code",
        json={"edit_code": "wrong-code"}
    )
    assert res_inval.status_code == 200
    assert res_inval.json()["valid"] is False

    # Non-existent device
    res_404 = client.post(
        "/api/v1/devices/UNKNOWN-DEV-999/verify-code",
        json={"edit_code": edit_code}
    )
    assert res_404.status_code == 404
