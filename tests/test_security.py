import io
import zipfile
import pytest
from app.config import settings
from app.services.storage import storage_service, sanitize_filename
from app.services.knxprod_parser import parse_knxprod_bytes, extract_knxprods_from_zip
from scripts.create_sample_knxprod import create_sample_knxprod_archive


def test_security_headers_present(client):
    """Test that mandatory security headers are present on all HTTP responses."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in response.headers.get("Content-Security-Policy", "")
    assert response.headers.get("Permissions-Policy") == "geolocation=(), microphone=(), camera=()"


def test_docs_csp_allows_swagger_cdn(client):
    """Verify that Swagger UI and ReDoc receive CSP allowing necessary CDNs and inline scripts."""
    res_docs = client.get("/docs")
    assert res_docs.status_code == 200
    csp_docs = res_docs.headers.get("Content-Security-Policy", "")
    assert "https://cdn.jsdelivr.net" in csp_docs
    assert "'unsafe-inline'" in csp_docs

    res_redoc = client.get("/redoc")
    assert res_redoc.status_code == 200
    csp_redoc = res_redoc.headers.get("Content-Security-Policy", "")
    assert "https://cdn.jsdelivr.net" in csp_redoc

    # Regular endpoints still enforce strict script-src without cdn.jsdelivr.net
    res_home = client.get("/")
    assert "https://cdn.jsdelivr.net" not in res_home.headers.get("Content-Security-Policy", "")



def test_cors_credentials_safety():
    """Verify that wildcard origin prevents credential reflection."""
    assert "*" in settings.ALLOWED_ORIGINS
    assert settings.cors_credentials_safe is False


def test_sanitize_filename():
    """Verify filename sanitization eliminates traversal and illegal characters."""
    assert sanitize_filename("../../../../etc/passwd") == "passwd.knxprod"
    assert sanitize_filename(r"..\..\evil.knxprod") == "evil.knxprod"
    assert sanitize_filename("test file!@#$.knxprod") == "test_file____.knxprod"
    assert sanitize_filename(None) == "unnamed.knxprod"
    assert sanitize_filename("") == "unnamed.knxprod"
    assert sanitize_filename("valid_device.knxprod") == "valid_device.knxprod"


def test_upload_path_traversal_sanitized(client, sample_knxprod_bytes):
    """Verify that a path traversal in X-File-Name header is strictly sanitized."""
    headers = {
        "Content-Type": "application/octet-stream",
        "X-File-Name": "../../../etc/shadow.knxprod"
    }
    response = client.post("/api/v1/upload", content=sample_knxprod_bytes, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "shadow.knxprod"
    # Ensure file was saved inside storage_service.base_dir
    assert not (storage_service.base_dir / ".." / "etc" / "shadow.knxprod").exists()


def test_storage_service_path_traversal_blocked():
    """Verify get_file_path denies paths escaping base_dir."""
    with pytest.raises(ValueError, match="Zugriff verweigert"):
        storage_service.get_file_path("/etc/passwd")

    with pytest.raises(ValueError, match="Zugriff verweigert"):
        storage_service.get_file_path("../../../etc/shadow")


def test_upload_size_limit_enforced(client, monkeypatch):
    """Verify that uploading payloads exceeding MAX_UPLOAD_SIZE_BYTES returns 413."""
    # Temporarily set max upload to 1 KB for test
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 1024)

    large_payload = b"A" * 2048
    headers = {
        "Content-Type": "application/octet-stream",
        "X-File-Name": "large.knxprod"
    }
    response = client.post("/api/v1/upload", content=large_payload, headers=headers)
    assert response.status_code == 413
    assert "überschreitet das Limit" in response.json()["detail"]


def test_zip_slip_rejected():
    """Verify that a zip containing path traversal filename is rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("../../evil.xml", b"<xml></xml>")
    zip_bytes = buf.getvalue()

    with pytest.raises(ValueError, match="Unzulässiger Pfad im Archiv"):
        parse_knxprod_bytes(zip_bytes)

    with pytest.raises(ValueError, match="Unzulässiger Pfad im Archiv"):
        extract_knxprods_from_zip(zip_bytes)


def test_zip_bomb_too_many_files():
    """Verify that an archive with more entries than MAX_ZIP_FILES is rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(settings.MAX_ZIP_FILES + 5):
            zf.writestr(f"file_{i}.txt", b"x")
    zip_bytes = buf.getvalue()

    with pytest.raises(ValueError, match="Archiv enthält zu viele Einträge"):
        parse_knxprod_bytes(zip_bytes)


def test_zip_bomb_uncompressed_limit(monkeypatch):
    """Verify that decompressed size exceeding MAX_ZIP_EXTRACTED_BYTES is rejected."""
    monkeypatch.setattr(settings, "MAX_ZIP_EXTRACTED_BYTES", 500)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("test.xml", b"A" * 1000)
    zip_bytes = buf.getvalue()

    with pytest.raises(ValueError, match="überschreitet maximal zulässige Größe"):
        parse_knxprod_bytes(zip_bytes)


def test_api_key_auth(client, sample_knxprod_bytes, monkeypatch):
    """Verify API Key authentication with timing-safe check and Bearer format."""
    monkeypatch.setattr(settings, "API_KEY", "secret-key-12345")

    # 1. No key -> 401
    headers = {"Content-Type": "application/octet-stream"}
    res = client.post("/api/v1/upload", content=sample_knxprod_bytes, headers=headers)
    assert res.status_code == 401

    # 2. Wrong key -> 401
    headers["X-API-Key"] = "wrong-key"
    res = client.post("/api/v1/upload", content=sample_knxprod_bytes, headers=headers)
    assert res.status_code == 401

    # 3. Valid X-API-Key -> 201
    headers["X-API-Key"] = "secret-key-12345"
    res = client.post("/api/v1/upload", content=sample_knxprod_bytes, headers=headers)
    assert res.status_code == 201

    # 4. Valid Authorization: Bearer token -> 201
    headers_bearer = {
        "Content-Type": "application/octet-stream",
        "Authorization": "Bearer secret-key-12345"
    }
    res2 = client.post("/api/v1/upload", content=sample_knxprod_bytes, headers=headers_bearer)
    assert res2.status_code == 201
