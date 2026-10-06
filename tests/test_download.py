import pytest

def test_download_post_octet_stream(client, sample_knxprod_bytes):
    # 1. Upload device first
    client.post(
        "/api/v1/upload",
        content=sample_knxprod_bytes,
        headers={"Content-Type": "application/octet-stream", "X-File-Name": "MDT_AKS.knxprod"}
    )

    # 2. Download via POST with JSON body requesting order_number
    payload = {"order_number": "AKS-0816.04"}
    res = client.post("/api/v1/download", json=payload)

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/octet-stream"
    assert "attachment" in res.headers["content-disposition"]
    assert "MDT_AKS.knxprod" in res.headers["content-disposition"]
    assert res.headers["x-knx-order-number"] == "AKS-0816.04"
    assert "x-checksum-sha256" in res.headers

    # Verify binary content matches
    assert res.content == sample_knxprod_bytes

def test_download_post_not_found(client):
    res = client.post("/api/v1/download", json={"order_number": "NON-EXISTENT-9999"})
    assert res.status_code == 404
    assert "Kein Gerät" in res.json()["detail"]

def test_download_get_octet_stream(client, sample_knxprod_bytes):
    # Upload first
    client.post(
        "/api/v1/upload",
        content=sample_knxprod_bytes,
        headers={"Content-Type": "application/octet-stream", "X-File-Name": "MDT_AKS.knxprod"}
    )

    # GET download
    res = client.get("/api/v1/download/AKS-0816.04")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/octet-stream"
    assert res.content == sample_knxprod_bytes


def test_download_get_redirect(client, sample_knxprod_bytes):
    # Upload with X-Source-URL
    source_link = "https://www.mdt.de/downloads/knx/MDT_AKS.knxprod"
    res_up = client.post(
        "/api/v1/upload",
        content=sample_knxprod_bytes,
        headers={
            "Content-Type": "application/octet-stream",
            "X-File-Name": "MDT_AKS.knxprod",
            "X-Source-URL": source_link
        }
    )
    assert res_up.status_code == 201
    assert res_up.json()["source_url"] == source_link

    # GET download with redirect=true
    res = client.get("/api/v1/download/AKS-0816.04?redirect=true", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == source_link

    # Verify device query returns source_url
    res_dev = client.get("/api/v1/devices?q=AKS-0816.04")
    assert res_dev.status_code == 200
    devices = res_dev.json()["devices"]
    assert len(devices) > 0
    assert devices[0]["knxprod_file"]["source_url"] == source_link


def test_download_fallback_redirect_when_file_missing(client, sample_knxprod_bytes, tmp_path):
    import os
    source_link = "https://partner.knx.org/download/test.knxprod"
    client.post(
        "/api/v1/upload?source_url=" + source_link,
        content=sample_knxprod_bytes,
        headers={"Content-Type": "application/octet-stream", "X-File-Name": "fallback.knxprod"}
    )

    # Delete storage file to simulate missing local binary
    from app.database import get_db
    from app.models import KnxprodFile
    from app.main import app

    db = next(app.dependency_overrides[get_db]()) if get_db in app.dependency_overrides else None
    if db:
        file_rec = db.query(KnxprodFile).first()
        if file_rec and file_rec.storage_path and os.path.exists(file_rec.storage_path):
            os.remove(file_rec.storage_path)

    # Calling download without redirect flag should fallback to 302 redirect
    res = client.get("/api/v1/download/AKS-0816.04", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == source_link

