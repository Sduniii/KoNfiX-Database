import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.config import settings
from app.models import Device, KnxprodFile


def test_auth_verify_open_mode(client):
    """When API_KEY is empty, anyone can verify."""
    res = client.get("/api/v1/auth/verify")
    assert res.status_code == 200
    assert res.json()["status"] == "authenticated"
    assert res.json()["auth_required"] is False


def test_auth_verify_with_key(client, monkeypatch):
    """When API_KEY is set, must supply correct key."""
    monkeypatch.setattr(settings, "API_KEY", "super_secret_admin_key")

    # Without key
    res_no = client.get("/api/v1/auth/verify")
    assert res_no.status_code == 401

    # With invalid key
    res_bad = client.get("/api/v1/auth/verify", headers={"X-API-Key": "wrong"})
    assert res_bad.status_code == 401

    # With valid key
    res_ok = client.get("/api/v1/auth/verify", headers={"X-API-Key": "super_secret_admin_key"})
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == "authenticated"
    assert res_ok.json()["auth_required"] is True


def test_update_device_metadata_and_source_url(client, sample_knxprod_bytes):
    # Upload first
    client.post(
        "/api/v1/upload",
        content=sample_knxprod_bytes,
        headers={"Content-Type": "application/octet-stream", "X-File-Name": "update_test.knxprod"}
    )

    update_payload = {
        "name": "Updated Device Name",
        "description": "Neue Beschreibung vom Admin",
        "hardware_version": "v2.5",
        "bus_current_ma": 15.5,
        "source_url": "https://www.mdt.de/download/MDT_AKS_new.knxprod"
    }

    res = client.patch("/api/v1/devices/AKS-0816.04", json=update_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Updated Device Name"
    assert data["description"] == "Neue Beschreibung vom Admin"
    assert data["hardware_version"] == "v2.5"
    assert data["bus_current_ma"] == 15.5
    assert data["knxprod_file"]["source_url"] == "https://www.mdt.de/download/MDT_AKS_new.knxprod"


def test_delete_device(client, sample_knxprod_bytes):
    # Upload first
    client.post(
        "/api/v1/upload",
        content=sample_knxprod_bytes,
        headers={"Content-Type": "application/octet-stream", "X-File-Name": "to_delete.knxprod"}
    )

    # Verify exists
    res_check = client.get("/api/v1/devices/AKS-0816.04")
    assert res_check.status_code == 200

    # Delete device
    res_del = client.delete("/api/v1/devices/AKS-0816.04?delete_file=true")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "success"

    # Verify 404 now
    res_check2 = client.get("/api/v1/devices/AKS-0816.04")
    assert res_check2.status_code == 404


def test_upload_from_url_ssrf_blocked(client):
    # Attempting to fetch loopback or private ranges must fail with 400
    bad_urls = [
        "http://127.0.0.1/evil.knxprod",
        "http://localhost/test.knxprod",
        "ftp://example.com/test.knxprod",
        "http://192.168.1.1/router.knxprod"
    ]
    for u in bad_urls:
        res = client.post("/api/v1/upload/url", json={"url": u})
        assert res.status_code == 400
        assert "nicht gestattet" in res.json()["detail"] or "Nur HTTP" in res.json()["detail"]


@pytest.mark.anyio
async def test_upload_from_url_metadata_only_mode(client, sample_knxprod_bytes):
    """Test importing from URL with store_binary=False (pure metadata & 302 redirect)."""
    # Mock httpx streaming response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-disposition": 'attachment; filename="remote_device.knxprod"'}
    
    async def mock_aiter_bytes(chunk_size=64*1024):
        yield sample_knxprod_bytes

    mock_resp.aiter_bytes = mock_aiter_bytes

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_client_instance = MagicMock()
    mock_client_instance.stream.return_value = mock_stream_ctx
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=None)

    fake_url = "https://downloads.mdt.de/knx/remote_device.knxprod"

    with patch("app.api.v1.upload._validate_safe_url", return_value=fake_url):
        with patch("httpx.AsyncClient", return_value=mock_client_instance):
            res = client.post(
                "/api/v1/upload/url",
                json={
                    "url": fake_url,
                    "store_binary": False
                }
            )

    assert res.status_code == 201
    data = res.json()
    assert data["source_url"] == fake_url
    assert len(data["devices_imported"]) > 0

    # Device must be queryable
    res_dev = client.get("/api/v1/devices/AKS-0816.04")
    assert res_dev.status_code == 200
    assert res_dev.json()["knxprod_file"]["source_url"] == fake_url

    # Downloading the device must redirect per 302 to the remote URL since storage_path is None
    res_dl = client.get("/api/v1/download/AKS-0816.04", follow_redirects=False)
    assert res_dl.status_code == 302
    assert res_dl.headers["location"] == fake_url


def test_batch_delete_devices(client, sample_knxprod_bytes):
    # Upload first
    client.post(
        "/api/v1/upload",
        content=sample_knxprod_bytes,
        headers={"Content-Type": "application/octet-stream", "X-File-Name": "batch_delete.knxprod"}
    )

    # Verify device exists
    res_dev = client.get("/api/v1/devices/AKS-0816.04")
    assert res_dev.status_code == 200

    # Batch delete with nonexistent and existent items
    res_del = client.post(
        "/api/v1/devices/batch-delete",
        json={
            "order_numbers": ["AKS-0816.04", "NON-EXISTENT-999"],
            "delete_files": True
        }
    )
    assert res_del.status_code == 200
    data = res_del.json()
    assert data["deleted_count"] == 1
    assert "AKS-0816.04" in data["deleted_order_numbers"]
    assert len(data["errors"]) == 1
    assert "NON-EXISTENT-999" in data["errors"][0]

    # Verify device was deleted
    res_check = client.get("/api/v1/devices/AKS-0816.04")
    assert res_check.status_code == 404


def test_public_upload_allowed_while_admin_actions_protected(client, sample_knxprod_bytes, monkeypatch):
    """Admin key is required for PATCH and DELETE, but public upload is allowed without key."""
    monkeypatch.setattr(settings, "ADMIN_KEY", "admin-super-key")
    monkeypatch.setattr(settings, "ALLOW_PUBLIC_UPLOAD", True)

    # 1. Public upload without any key -> SUCCESS 201
    res_up = client.post(
        "/api/v1/upload",
        content=sample_knxprod_bytes,
        headers={"Content-Type": "application/octet-stream"}
    )
    assert res_up.status_code == 201

    # 2. Patch without key -> 401 Unauthorized
    res_patch_no_key = client.patch(
        "/api/v1/devices/AKS-0816.04",
        json={"name": "Hacked Device"}
    )
    assert res_patch_no_key.status_code == 401

    # 3. Patch with valid key -> 200 OK
    res_patch_auth = client.patch(
        "/api/v1/devices/AKS-0816.04",
        json={"name": "Renamed By Admin"},
        headers={"X-API-Key": "admin-super-key"}
    )
    assert res_patch_auth.status_code == 200
    assert res_patch_auth.json()["name"] == "Renamed By Admin"

    # 4. Batch delete without key -> 401 Unauthorized
    res_batch_no_key = client.post(
        "/api/v1/devices/batch-delete",
        json={"order_numbers": ["AKS-0816.04"]}
    )
    assert res_batch_no_key.status_code == 401

    # 5. Batch delete with valid key -> 200 OK
    res_batch_auth = client.post(
        "/api/v1/devices/batch-delete",
        json={"order_numbers": ["AKS-0816.04"], "delete_files": True},
        headers={"X-API-Key": "admin-super-key"}
    )
    assert res_batch_auth.status_code == 200
    assert res_batch_auth.json()["deleted_count"] == 1

